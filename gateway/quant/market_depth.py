from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from gateway.quant.intelligence_models import MarketDepthReplay, MarketDepthStatus, OrderBookLevel, OrderBookSnapshot
from gateway.quant.market_data import MarketDataGateway


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def _bounded(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, float(value)))


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


class MarketDepthGateway:
    """Vendor-agnostic L2 gateway with real BYO-file support and synthetic fallback."""

    def __init__(self, *, storage_root: Path | None = None, market_data: MarketDataGateway | None = None) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        self.storage_root = Path(storage_root or (repo_root / "storage"))
        self.market_data = market_data or MarketDataGateway()
        self.replay_root = self.storage_root / "quant" / "market_depth" / "replays"
        self.byo_root = self._resolve_byo_root()
        self.replay_root.mkdir(parents=True, exist_ok=True)
        self.byo_root.mkdir(parents=True, exist_ok=True)

    def status(self, *, symbols: list[str] | None = None, require_l2: bool = False) -> dict[str, Any]:
        normalized_symbols = self._normalize_symbols(symbols)
        configured = self._configured_providers()
        capabilities = self._provider_capabilities(configured, normalized_symbols)
        selected = self._selected_provider(configured, capabilities)
        selected_caps = capabilities.get(selected, {})
        latest = [
            self.latest(symbol, persist=False, provider_override=selected)
            for symbol in normalized_symbols[:5]
        ] if normalized_symbols else []
        is_real = bool(selected_caps.get("is_real_provider"))
        available = bool(selected_caps.get("available"))
        data_tier = "l2" if available and is_real else "l1"
        blocking_reasons: list[str] = []
        if require_l2 and data_tier != "l2":
            blocking_reasons.append("l2_required_but_unavailable")
        elif not available:
            blocking_reasons.append("market_depth_provider_unavailable")
        eligibility_status = "pass" if not blocking_reasons and available else "blocked" if blocking_reasons else "review"
        payload = MarketDepthStatus(
            generated_at=_iso_now(),
            symbols=normalized_symbols,
            selected_provider=selected,
            configured_providers=configured,
            provider_capabilities=capabilities,
            available=available,
            is_real_provider=is_real,
            history_ready=bool(selected_caps.get("history_ready")),
            realtime_ready=bool(selected_caps.get("realtime_ready")),
            data_tier=data_tier,  # type: ignore[arg-type]
            eligibility_status=eligibility_status,  # type: ignore[arg-type]
            blocking_reasons=blocking_reasons,
            latest=[OrderBookSnapshot.model_validate(item) for item in latest if item],
            lineage=[
                "market_depth_gateway",
                "provider_capabilities",
                "selected_provider_health_check",
                "eligibility_gate",
            ],
        )
        return payload.model_dump(mode="json")

    def latest(
        self,
        symbol: str,
        *,
        persist: bool = False,
        provider_override: str | None = None,
    ) -> dict[str, Any]:
        normalized = self._normalize_symbol(symbol)
        provider = provider_override or self._selected_provider(
            self._configured_providers(),
            self._provider_capabilities(self._configured_providers(), [normalized]),
        )
        snapshot = self._load_latest_snapshot(normalized, provider)
        payload = snapshot.model_dump(mode="json")
        if persist:
            path = self.replay_root / f"latest-{normalized}.json"
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return payload

    def replay(
        self,
        symbol: str,
        *,
        limit: int = 20,
        timestamps: list[str] | None = None,
        require_l2: bool = False,
        persist: bool = True,
    ) -> dict[str, Any]:
        normalized = self._normalize_symbol(symbol)
        configured = self._configured_providers()
        capabilities = self._provider_capabilities(configured, [normalized])
        provider = self._selected_provider(configured, capabilities)
        provider_caps = capabilities.get(provider, {})
        snapshots = self._load_replay_snapshots(normalized, provider, limit=limit, timestamps=timestamps)
        is_real = bool(provider_caps.get("is_real_provider"))
        data_tier = "l2" if snapshots and is_real else "l1"
        warnings: list[str] = []
        if data_tier != "l2":
            warnings.append("proxy_mode=l1")
        if require_l2 and data_tier != "l2":
            warnings.append("l2_required_but_unavailable")
        spreads = [float(item.spread_bps or 0.0) for item in snapshots]
        bid_depth = [float(item.total_bid_size or 0.0) for item in snapshots]
        ask_depth = [float(item.total_ask_size or 0.0) for item in snapshots]
        imbalance = [float(item.imbalance or 0.0) for item in snapshots]
        session_id = f"depth-{normalized.lower()}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        replay = MarketDepthReplay(
            session_id=session_id,
            generated_at=_iso_now(),
            symbol=normalized,
            provider=provider,
            data_tier=data_tier,  # type: ignore[arg-type]
            is_real_provider=is_real,
            snapshots=snapshots,
            summary={
                "snapshot_count": len(snapshots),
                "avg_spread_bps": round(_mean(spreads), 6),
                "avg_bid_depth": round(_mean(bid_depth), 4),
                "avg_ask_depth": round(_mean(ask_depth), 4),
                "avg_imbalance": round(_mean(imbalance), 6),
                "proxy_mode": "none" if data_tier == "l2" else "l1",
                "requires_real_l2": bool(require_l2),
            },
            warnings=warnings,
            lineage=[
                "market_depth_gateway",
                f"provider:{provider}",
                "historical_replay",
                "storage_session",
            ],
        )
        payload = replay.model_dump(mode="json")
        if persist:
            path = self.replay_root / f"{session_id}.json"
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return payload

    def load_replay(self, session_id: str) -> dict[str, Any] | None:
        path = self.replay_root / f"{session_id}.json"
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None

    def live_payload(self, *, symbols: list[str] | None = None, require_l2: bool = False) -> dict[str, Any]:
        status = self.status(symbols=symbols, require_l2=require_l2)
        status["event"] = "market_depth_tick"
        status["generated_at"] = _iso_now()
        status["snapshot_count"] = len(status.get("latest") or [])
        return status

    def _configured_providers(self) -> list[str]:
        raw = (
            os.getenv("MARKET_DEPTH_PROVIDERS", "")
            or os.getenv("MARKET_DEPTH_PROVIDER_ORDER", "")
            or "byo_file,fake_l2"
        )
        providers = [item.strip().lower() for item in raw.split(",") if item.strip()]
        return providers or ["byo_file", "fake_l2"]

    def _resolve_byo_root(self) -> Path:
        configured = (
            os.getenv("MARKET_DEPTH_BYO_DIR", "")
            or os.getenv("MARKET_DEPTH_STORAGE_DIR", "")
            or "storage/quant/market_depth/byo_file"
        )
        path = Path(configured)
        if not path.is_absolute():
            path = Path(__file__).resolve().parents[2] / path
        return path

    def _provider_capabilities(self, providers: list[str], symbols: list[str]) -> dict[str, dict[str, Any]]:
        capabilities: dict[str, dict[str, Any]] = {}
        for provider in providers:
            if provider == "byo_file":
                available = self._byo_available(symbols)
                capabilities[provider] = {
                    "available": available,
                    "history_ready": available,
                    "realtime_ready": available,
                    "is_real_provider": available,
                    "source": str(self.byo_root),
                    "mode": "bring_your_own_order_book",
                }
            elif provider == "fake_l2":
                capabilities[provider] = {
                    "available": True,
                    "history_ready": True,
                    "realtime_ready": True,
                    "is_real_provider": False,
                    "source": "synthetic_shadow_provider",
                    "mode": "fallback",
                }
        return capabilities

    def _selected_provider(self, providers: list[str], capabilities: dict[str, dict[str, Any]]) -> str:
        for provider in providers:
            if capabilities.get(provider, {}).get("available"):
                return provider
        return "unavailable"

    def _byo_available(self, symbols: list[str]) -> bool:
        if not self.byo_root.exists():
            return False
        if not symbols:
            return any(self.byo_root.rglob("*.json")) or any(self.byo_root.rglob("*.jsonl"))
        return any(self._candidate_paths(symbol) for symbol in symbols)

    def _candidate_paths(self, symbol: str) -> list[Path]:
        normalized = self._normalize_symbol(symbol)
        candidates = [
            self.byo_root / f"{normalized}.json",
            self.byo_root / f"{normalized}.jsonl",
            self.byo_root / "latest" / f"{normalized}.json",
            self.byo_root / "latest" / f"{normalized}.jsonl",
            self.byo_root / "history" / f"{normalized}.json",
            self.byo_root / "history" / f"{normalized}.jsonl",
        ]
        return [path for path in candidates if path.exists()]

    def _load_latest_snapshot(self, symbol: str, provider: str) -> OrderBookSnapshot:
        if provider == "byo_file":
            snapshot = self._read_byo_latest(symbol)
            if snapshot is not None:
                return snapshot
        return self._fake_snapshot(symbol)

    def _load_replay_snapshots(
        self,
        symbol: str,
        provider: str,
        *,
        limit: int,
        timestamps: list[str] | None = None,
    ) -> list[OrderBookSnapshot]:
        if provider == "byo_file":
            snapshots = self._read_byo_history(symbol, limit=limit, timestamps=timestamps)
            if snapshots:
                return snapshots
        return self._fake_replay(symbol, limit=limit)

    def _read_byo_latest(self, symbol: str) -> OrderBookSnapshot | None:
        records = self._read_byo_records(symbol)
        if not records:
            return None
        return self._normalize_snapshot_payload(records[-1], symbol=symbol, provider="byo_file", is_real=True)

    def _read_byo_history(
        self,
        symbol: str,
        *,
        limit: int,
        timestamps: list[str] | None = None,
    ) -> list[OrderBookSnapshot]:
        records = self._read_byo_records(symbol)
        if timestamps:
            wanted = {str(value) for value in timestamps if str(value).strip()}
            records = [row for row in records if str(row.get("timestamp") or row.get("ts") or "") in wanted]
        if not records:
            return []
        sliced = records[-max(1, int(limit)) :]
        return [
            self._normalize_snapshot_payload(row, symbol=symbol, provider="byo_file", is_real=True)
            for row in sliced
        ]

    def _read_byo_records(self, symbol: str) -> list[dict[str, Any]]:
        paths = self._candidate_paths(symbol)
        for path in paths:
            try:
                if path.suffix.lower() == ".jsonl":
                    records = [
                        json.loads(line)
                        for line in path.read_text(encoding="utf-8").splitlines()
                        if line.strip()
                    ]
                else:
                    raw = json.loads(path.read_text(encoding="utf-8"))
                    if isinstance(raw, list):
                        records = raw
                    elif isinstance(raw, dict) and isinstance(raw.get("snapshots"), list):
                        records = list(raw.get("snapshots") or [])
                    elif isinstance(raw, dict):
                        records = [raw]
                    else:
                        records = []
                if records:
                    return [row for row in records if isinstance(row, dict)]
            except (OSError, json.JSONDecodeError):
                continue
        return []

    def _fake_snapshot(self, symbol: str, *, timestamp: str | None = None, seed_offset: int = 0) -> OrderBookSnapshot:
        normalized = self._normalize_symbol(symbol)
        reference = self._reference_price(normalized)
        base_seed = (sum(ord(ch) for ch in normalized) + seed_offset * 17) % 11
        spread_bps = 4.5 + base_seed * 0.35
        spread_value = reference * (spread_bps / 10000.0)
        best_bid = round(max(reference - spread_value / 2.0, 0.01), 4)
        best_ask = round(max(reference + spread_value / 2.0, best_bid + 0.01), 4)
        bids: list[OrderBookLevel] = []
        asks: list[OrderBookLevel] = []
        total_bid_size = 0.0
        total_ask_size = 0.0
        for level in range(1, 6):
            bid_size = round(300 + base_seed * 25 + level * 40, 2)
            ask_size = round(280 + base_seed * 20 + level * 45, 2)
            bids.append(OrderBookLevel(level=level, price=round(best_bid - (level - 1) * 0.01, 4), size=bid_size, order_count=level + 1))
            asks.append(OrderBookLevel(level=level, price=round(best_ask + (level - 1) * 0.01, 4), size=ask_size, order_count=level + 1))
            total_bid_size += bid_size
            total_ask_size += ask_size
        imbalance = (total_bid_size - total_ask_size) / max(total_bid_size + total_ask_size, 1.0)
        if timestamp:
            snapshot_time = timestamp
        else:
            snapshot_time = _iso_now()
        return OrderBookSnapshot(
            snapshot_id=f"depth-{normalized.lower()}-{seed_offset}-{int(_parse_dt(snapshot_time).timestamp()) if _parse_dt(snapshot_time) else seed_offset}",
            symbol=normalized,
            provider="fake_l2",
            timestamp=snapshot_time,
            session=self._session_label(_parse_dt(snapshot_time)),
            is_real=False,
            bids=bids,
            asks=asks,
            best_bid=best_bid,
            best_ask=best_ask,
            mid_price=round((best_bid + best_ask) / 2.0, 4),
            spread_bps=round(spread_bps, 6),
            total_bid_size=round(total_bid_size, 4),
            total_ask_size=round(total_ask_size, 4),
            imbalance=round(imbalance, 6),
            metadata={"proxy_mode": "l1", "reference_price": reference},
        )

    def _fake_replay(self, symbol: str, *, limit: int) -> list[OrderBookSnapshot]:
        start = datetime.now(timezone.utc) - timedelta(minutes=max(1, limit))
        snapshots: list[OrderBookSnapshot] = []
        for offset in range(max(1, int(limit))):
            ts = (start + timedelta(minutes=offset)).isoformat()
            snapshots.append(self._fake_snapshot(symbol, timestamp=ts, seed_offset=offset))
        return snapshots

    def _normalize_snapshot_payload(
        self,
        payload: dict[str, Any],
        *,
        symbol: str,
        provider: str,
        is_real: bool,
    ) -> OrderBookSnapshot:
        normalized_symbol = self._normalize_symbol(payload.get("symbol") or symbol)
        bids_payload = payload.get("bids") or payload.get("bid_levels") or []
        asks_payload = payload.get("asks") or payload.get("ask_levels") or []
        bids = [self._normalize_level(item, level=index + 1) for index, item in enumerate(bids_payload[:10])]
        asks = [self._normalize_level(item, level=index + 1) for index, item in enumerate(asks_payload[:10])]
        best_bid = float(payload.get("best_bid") or (bids[0].price if bids else 0.0) or 0.0)
        best_ask = float(payload.get("best_ask") or (asks[0].price if asks else 0.0) or 0.0)
        mid_price = float(payload.get("mid_price") or ((best_bid + best_ask) / 2.0 if best_bid and best_ask else 0.0) or 0.0)
        spread_bps = float(payload.get("spread_bps") or (((best_ask - best_bid) / mid_price) * 10000.0 if mid_price and best_ask >= best_bid else 0.0))
        total_bid_size = float(payload.get("total_bid_size") or sum(level.size for level in bids))
        total_ask_size = float(payload.get("total_ask_size") or sum(level.size for level in asks))
        imbalance = float(payload.get("imbalance") or ((total_bid_size - total_ask_size) / max(total_bid_size + total_ask_size, 1.0)))
        timestamp = str(payload.get("timestamp") or payload.get("ts") or _iso_now())
        snapshot = OrderBookSnapshot(
            snapshot_id=str(payload.get("snapshot_id") or f"depth-{normalized_symbol.lower()}-{int(_parse_dt(timestamp).timestamp()) if _parse_dt(timestamp) else 0}"),
            symbol=normalized_symbol,
            provider=str(payload.get("provider") or provider),
            timestamp=timestamp,
            session=str(payload.get("session") or self._session_label(_parse_dt(timestamp))),
            is_real=bool(payload.get("is_real") if "is_real" in payload else is_real),
            bids=bids,
            asks=asks,
            best_bid=round(best_bid, 6),
            best_ask=round(best_ask, 6),
            mid_price=round(mid_price, 6),
            spread_bps=round(spread_bps, 6),
            total_bid_size=round(total_bid_size, 6),
            total_ask_size=round(total_ask_size, 6),
            imbalance=round(imbalance, 6),
            metadata=dict(payload.get("metadata") or {}),
        )
        return snapshot

    @staticmethod
    def _normalize_level(payload: Any, *, level: int) -> OrderBookLevel:
        if isinstance(payload, dict):
            return OrderBookLevel(
                level=int(payload.get("level") or level),
                price=float(payload.get("price") or 0.0),
                size=float(payload.get("size") or payload.get("qty") or payload.get("quantity") or 0.0),
                order_count=int(payload["order_count"]) if payload.get("order_count") is not None else None,
            )
        if isinstance(payload, (list, tuple)) and len(payload) >= 2:
            return OrderBookLevel(level=level, price=float(payload[0] or 0.0), size=float(payload[1] or 0.0))
        return OrderBookLevel(level=level, price=0.0, size=0.0)

    @staticmethod
    def _normalize_symbol(symbol: str | None) -> str:
        return str(symbol or "AAPL").upper().strip()

    def _normalize_symbols(self, symbols: list[str] | None) -> list[str]:
        return list(dict.fromkeys(self._normalize_symbol(symbol) for symbol in (symbols or []) if str(symbol or "").strip()))

    def _reference_price(self, symbol: str) -> float:
        try:
            bars = self.market_data.get_daily_bars(symbol, limit=2, allow_stale_cache=True)
            frame = bars.bars
            if not frame.empty:
                return float(frame["close"].iloc[-1])
        except Exception:
            pass
        return 100.0 + (sum(ord(ch) for ch in symbol) % 90)

    @staticmethod
    def _session_label(timestamp: datetime | None) -> str:
        if timestamp is None:
            return "regular"
        hour = int(timestamp.astimezone(timezone.utc).hour)
        if hour < 13:
            return "pre"
        if hour < 15:
            return "open"
        if hour < 19:
            return "midday"
        if hour < 21:
            return "close"
        return "post"
