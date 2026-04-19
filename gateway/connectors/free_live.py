from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def today_key() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def stable_hash(payload: Any) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def redact_value(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 6:
        return "***"
    return f"{value[:3]}***{value[-3:]}"


@dataclass(frozen=True)
class ConnectorDefinition:
    provider_id: str
    display_name: str
    category: str
    env_keys: tuple[str, ...]
    capabilities: tuple[str, ...]
    daily_limit: int
    scan_budget: int
    manual_reserve: int
    credit_cost: int = 1
    priority: int = 50
    docs_url: str = ""
    free_tier_note: str = ""
    license_note: str = "free-tier research use; verify provider terms before production use"


@dataclass
class ConnectorResult:
    provider: str
    status: str
    configured: bool
    latency_ms: int = 0
    sample_count: int = 0
    normalized_items: list[dict[str, Any]] = field(default_factory=list)
    failure_reason: str = ""
    cache_status: str = "not_used"
    quota: dict[str, Any] = field(default_factory=dict)
    raw_preview: Any = None

    def payload(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "status": self.status,
            "configured": self.configured,
            "latency_ms": self.latency_ms,
            "sample_count": self.sample_count,
            "normalized_count": len(self.normalized_items),
            "normalized_items": self.normalized_items,
            "failure_reason": self.failure_reason,
            "cache_status": self.cache_status,
            "quota": self.quota,
            "raw_preview": self.raw_preview,
        }


class FreeQuotaLedger:
    def __init__(self, storage_root: Path) -> None:
        self.storage_root = storage_root
        self.quota_dir = storage_root / "intelligence" / "connector_quota"

    def _path(self) -> Path:
        return self.quota_dir / f"{today_key()}.json"

    def _read(self) -> dict[str, Any]:
        path = self._path()
        if not path.exists():
            return {"date": today_key(), "providers": {}}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {"date": today_key(), "providers": {}}

    def _write(self, payload: dict[str, Any]) -> None:
        self.quota_dir.mkdir(parents=True, exist_ok=True)
        self._path().write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def status(self, definition: ConnectorDefinition) -> dict[str, Any]:
        payload = self._read()
        row = payload.get("providers", {}).get(definition.provider_id, {})
        used = int(row.get("used_today", 0) or 0)
        return {
            "provider": definition.provider_id,
            "date_utc": today_key(),
            "daily_limit": definition.daily_limit,
            "scan_budget": definition.scan_budget,
            "manual_reserve": definition.manual_reserve,
            "used_today": used,
            "remaining_estimate": max(definition.daily_limit - used, 0),
            "reset_at_utc": f"{today_key()}T23:59:59+00:00",
            "quota_mode": "free_tier_guarded",
        }

    def reserve(self, definition: ConnectorDefinition, cost: int | None = None, *, scan: bool = True) -> tuple[bool, dict[str, Any]]:
        cost = int(cost if cost is not None else definition.credit_cost)
        payload = self._read()
        providers = payload.setdefault("providers", {})
        row = providers.setdefault(definition.provider_id, {"used_today": 0, "events": []})
        used = int(row.get("used_today", 0) or 0)
        limit = definition.scan_budget if scan else definition.daily_limit
        if used + cost > limit:
            status = self.status(definition)
            status["guard_status"] = "quota_protected"
            status["requested_cost"] = cost
            return False, status
        row["used_today"] = used + cost
        row.setdefault("events", []).append({"at": utc_now(), "cost": cost, "scan": scan})
        self._write(payload)
        status = self.status(definition)
        status["guard_status"] = "reserved"
        status["requested_cost"] = cost
        return True, status


class BaseFreeConnector:
    definition: ConnectorDefinition

    def __init__(self, storage_root: Path, quota: FreeQuotaLedger, timeout: float = 5.0) -> None:
        self.storage_root = storage_root
        self.quota = quota
        self.timeout = timeout

    @property
    def provider_id(self) -> str:
        return self.definition.provider_id

    def api_key(self) -> str:
        for name in self.definition.env_keys:
            value = os.getenv(name, "")
            if value:
                return value
        return ""

    def configured(self) -> bool:
        return not self.definition.env_keys or bool(self.api_key())

    def registry_row(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "display_name": self.definition.display_name,
            "category": self.definition.category,
            "configured": self.configured(),
            "env_keys": list(self.definition.env_keys),
            "env_status": {key: bool(os.getenv(key, "")) for key in self.definition.env_keys},
            "capabilities": list(self.definition.capabilities),
            "daily_limit": self.definition.daily_limit,
            "scan_budget": self.definition.scan_budget,
            "manual_reserve": self.definition.manual_reserve,
            "priority": self.definition.priority,
            "docs_url": self.definition.docs_url,
            "free_tier_note": self.definition.free_tier_note,
            "license_note": self.definition.license_note,
            "quota": self.quota.status(self.definition),
        }

    def health_check(self, *, live: bool = False) -> dict[str, Any]:
        configured = self.configured()
        status = "configured" if configured else "missing_key"
        failure = "" if configured else f"missing one of: {', '.join(self.definition.env_keys)}"
        if live and configured:
            sample = self.sample_request("AAPL", dry_run=False, quota_guard=False)
            status = sample.status
            failure = sample.failure_reason
        return {
            "provider": self.provider_id,
            "display_name": self.definition.display_name,
            "status": status,
            "configured": configured,
            "failure_reason": failure,
            "quota": self.quota.status(self.definition),
            "free_tier_note": self.definition.free_tier_note,
        }

    def sample_request(self, symbol: str, *, dry_run: bool = False, quota_guard: bool = True) -> ConnectorResult:
        symbol = str(symbol or "AAPL").upper().strip()
        if not self.configured():
            return ConnectorResult(
                provider=self.provider_id,
                status="missing_key",
                configured=False,
                failure_reason=f"missing one of: {', '.join(self.definition.env_keys)}",
                quota=self.quota.status(self.definition),
            )
        if dry_run:
            return ConnectorResult(
                provider=self.provider_id,
                status="dry_run_ready",
                configured=True,
                sample_count=0,
                failure_reason="dry run only; no external request was sent",
                quota=self.quota.status(self.definition),
            )
        if quota_guard:
            ok, quota_status = self.quota.reserve(self.definition, scan=True)
            if not ok:
                return ConnectorResult(
                    provider=self.provider_id,
                    status="quota_protected",
                    configured=True,
                    failure_reason="free-tier scan budget exhausted; use cached/local mode",
                    quota=quota_status,
                )
        else:
            quota_status = self.quota.status(self.definition)

        started = time.perf_counter()
        try:
            raw = self._fetch_live(symbol)
            latency = int((time.perf_counter() - started) * 1000)
            items = self.normalize(symbol, raw)
            return ConnectorResult(
                provider=self.provider_id,
                status="ok" if items else "empty",
                configured=True,
                latency_ms=latency,
                sample_count=len(items),
                normalized_items=items,
                quota=quota_status,
                raw_preview=self.preview(raw),
            )
        except requests.HTTPError as exc:
            code = getattr(exc.response, "status_code", None)
            status = "rate_limited" if code == 429 else "auth_failed" if code in {401, 403} else "http_error"
            return ConnectorResult(
                provider=self.provider_id,
                status=status,
                configured=True,
                latency_ms=int((time.perf_counter() - started) * 1000),
                failure_reason=f"HTTP {code}: {str(exc)[:180]}",
                quota=quota_status,
            )
        except Exception as exc:
            return ConnectorResult(
                provider=self.provider_id,
                status="failed",
                configured=True,
                latency_ms=int((time.perf_counter() - started) * 1000),
                failure_reason=str(exc)[:240],
                quota=quota_status,
            )

    def _fetch_live(self, symbol: str) -> Any:
        raise NotImplementedError

    def normalize(self, symbol: str, raw: Any) -> list[dict[str, Any]]:
        raise NotImplementedError

    def preview(self, raw: Any) -> Any:
        if isinstance(raw, dict):
            return {key: raw.get(key) for key in list(raw.keys())[:6]}
        if isinstance(raw, list):
            return raw[:2]
        return str(raw)[:240]

    def _get_json(self, url: str, *, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> Any:
        response = requests.get(url, params=params, headers=headers, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def _item(
        self,
        *,
        symbol: str,
        item_type: str,
        title: str,
        summary: str,
        source: str,
        url: str | None = None,
        published_at: str | None = None,
        confidence: float = 0.66,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "item_type": item_type,
            "provider": self.provider_id,
            "source": source,
            "url": url,
            "symbol": symbol.upper(),
            "title": title,
            "summary": summary,
            "published_at": published_at,
            "confidence": confidence,
            "license_note": self.definition.license_note,
            "metadata": metadata or {},
        }


class MarketauxConnector(BaseFreeConnector):
    definition = ConnectorDefinition(
        provider_id="marketaux",
        display_name="Marketaux Free",
        category="news_sentiment",
        env_keys=("MARKETAUX_API_KEY", "MARKETAUX_API", "Marketaux_API"),
        capabilities=("news", "sentiment", "events"),
        daily_limit=100,
        scan_budget=60,
        manual_reserve=40,
        priority=30,
        docs_url="https://www.marketaux.com/pricing",
        free_tier_note="Free tier: 100 requests/day, 3 articles per news request.",
    )

    def _fetch_live(self, symbol: str) -> Any:
        return self._get_json(
            "https://api.marketaux.com/v1/news/all",
            params={"api_token": self.api_key(), "symbols": symbol, "language": "en", "limit": 3},
        )

    def normalize(self, symbol: str, raw: Any) -> list[dict[str, Any]]:
        rows = raw.get("data", []) if isinstance(raw, dict) else []
        items: list[dict[str, Any]] = []
        for row in rows[:3]:
            entities = row.get("entities") or []
            sentiment = None
            if entities:
                sentiment = entities[0].get("sentiment_score")
            items.append(
                self._item(
                    symbol=symbol,
                    item_type="news",
                    title=str(row.get("title") or f"{symbol} Marketaux news"),
                    summary=str(row.get("description") or row.get("snippet") or row.get("title") or ""),
                    source=str(row.get("source") or "Marketaux"),
                    url=row.get("url"),
                    published_at=row.get("published_at"),
                    confidence=0.74,
                    metadata={"sentiment": sentiment, "entities": entities[:3]},
                )
            )
        return items


class TheNewsApiConnector(BaseFreeConnector):
    definition = ConnectorDefinition(
        provider_id="thenewsapi",
        display_name="TheNewsAPI Free",
        category="news",
        env_keys=("THENEWSAPI_KEY", "THE_NEWS_API_KEY", "THENEWSAPI", "TheNewsAPI"),
        capabilities=("news", "events"),
        daily_limit=100,
        scan_budget=40,
        manual_reserve=60,
        priority=55,
        docs_url="https://www.thenewsapi.com/pricing",
        free_tier_note="Free tier: 100 requests/day, 3 articles per news request.",
    )

    def _fetch_live(self, symbol: str) -> Any:
        return self._get_json(
            "https://api.thenewsapi.com/v1/news/all",
            params={"api_token": self.api_key(), "search": symbol, "language": "en", "limit": 3},
        )

    def normalize(self, symbol: str, raw: Any) -> list[dict[str, Any]]:
        rows = raw.get("data", []) if isinstance(raw, dict) else []
        return [
            self._item(
                symbol=symbol,
                item_type="news",
                title=str(row.get("title") or f"{symbol} news"),
                summary=str(row.get("description") or row.get("snippet") or row.get("title") or ""),
                source=str(row.get("source") or "TheNewsAPI"),
                url=row.get("url"),
                published_at=row.get("published_at"),
                confidence=0.67,
                metadata={"categories": row.get("categories") or []},
            )
            for row in rows[:3]
        ]


class TwelveDataConnector(BaseFreeConnector):
    definition = ConnectorDefinition(
        provider_id="twelvedata",
        display_name="Twelve Data Free",
        category="market_data",
        env_keys=("TWELVEDATA_API_KEY", "TWELVEDATA_API", "TWELVE_DATA_API", "Twelve_Data_API"),
        capabilities=("prices", "ohlcv", "technical_indicators"),
        daily_limit=800,
        scan_budget=500,
        manual_reserve=300,
        priority=40,
        docs_url="https://support.twelvedata.com/en/articles/5615854-credits",
        free_tier_note="Free/basic quota uses daily credits; plan assumes 800 credits/day.",
    )

    def _fetch_live(self, symbol: str) -> Any:
        return self._get_json(
            "https://api.twelvedata.com/time_series",
            params={"symbol": symbol, "interval": "1day", "outputsize": 5, "apikey": self.api_key()},
        )

    def normalize(self, symbol: str, raw: Any) -> list[dict[str, Any]]:
        values = raw.get("values", []) if isinstance(raw, dict) else []
        if not values:
            return []
        latest = values[0]
        title = f"{symbol} daily OHLCV from Twelve Data"
        summary = (
            f"close={latest.get('close')}, open={latest.get('open')}, "
            f"high={latest.get('high')}, low={latest.get('low')}"
        )
        return [
            self._item(
                symbol=symbol,
                item_type="market_signal",
                title=title,
                summary=summary,
                source="twelvedata.time_series",
                published_at=latest.get("datetime"),
                confidence=0.71,
                metadata={"bars": values[:5]},
            )
        ]


class AlphaVantageConnector(BaseFreeConnector):
    definition = ConnectorDefinition(
        provider_id="alpha_vantage",
        display_name="Alpha Vantage Free",
        category="market_data_fallback",
        env_keys=("ALPHA_VANTAGE_API_KEY", "ALPHA_VANTAGE_KEY"),
        capabilities=("prices", "technical_indicators"),
        daily_limit=25,
        scan_budget=10,
        manual_reserve=15,
        priority=75,
        docs_url="https://www.alphavantage.co/premium/",
        free_tier_note="Standard free tier is treated as 25 requests/day; use only as fallback.",
    )

    def _fetch_live(self, symbol: str) -> Any:
        return self._get_json(
            "https://www.alphavantage.co/query",
            params={"function": "TIME_SERIES_DAILY", "symbol": symbol, "apikey": self.api_key()},
        )

    def normalize(self, symbol: str, raw: Any) -> list[dict[str, Any]]:
        series = raw.get("Time Series (Daily)", {}) if isinstance(raw, dict) else {}
        if not series:
            return []
        date_key = sorted(series.keys(), reverse=True)[0]
        bar = series[date_key]
        return [
            self._item(
                symbol=symbol,
                item_type="market_signal",
                title=f"{symbol} Alpha Vantage fallback daily bar",
                summary=f"close={bar.get('4. close')}, volume={bar.get('5. volume')}",
                source="alpha_vantage.time_series_daily",
                published_at=date_key,
                confidence=0.61,
                metadata={"bar": bar},
            )
        ]


class AlpacaMarketConnector(BaseFreeConnector):
    definition = ConnectorDefinition(
        provider_id="alpaca_market",
        display_name="Alpaca Market/Paper Free",
        category="paper_execution_market_data",
        env_keys=("ALPACA_API_KEY", "ALPACA_API_SECRET"),
        capabilities=("iex_prices", "paper_trading_status"),
        daily_limit=5000,
        scan_budget=1000,
        manual_reserve=4000,
        priority=35,
        docs_url="https://docs.alpaca.markets/docs/market-data-faq",
        free_tier_note="Free market data is IEX-only; SIP/latest all-market data needs subscription.",
        license_note="Alpaca free IEX/paper data; shadow research use only",
    )

    def _fetch_live(self, symbol: str) -> Any:
        return self._get_json(
            f"https://data.alpaca.markets/v2/stocks/{symbol}/bars",
            params={"timeframe": "1Day", "limit": 3, "feed": os.getenv("MARKET_DATA_ALPACA_FEED", "iex")},
            headers={"APCA-API-KEY-ID": os.getenv("ALPACA_API_KEY", ""), "APCA-API-SECRET-KEY": os.getenv("ALPACA_API_SECRET", "")},
        )

    def normalize(self, symbol: str, raw: Any) -> list[dict[str, Any]]:
        bars = raw.get("bars", []) if isinstance(raw, dict) else []
        if not bars:
            return []
        latest = bars[-1]
        return [
            self._item(
                symbol=symbol,
                item_type="market_signal",
                title=f"{symbol} Alpaca IEX daily bar",
                summary=f"close={latest.get('c')}, volume={latest.get('v')}, feed=iex",
                source="alpaca_market.iex_bars",
                published_at=latest.get("t"),
                confidence=0.72,
                metadata={"feed": "iex", "bars": bars},
            )
        ]


class LocalEsgConnector(BaseFreeConnector):
    definition = ConnectorDefinition(
        provider_id="local_esg",
        display_name="Local ESG Corpus",
        category="local_paper_grade_evidence",
        env_keys=(),
        capabilities=("esg_reports", "local_evidence"),
        daily_limit=1_000_000,
        scan_budget=1_000_000,
        manual_reserve=0,
        priority=10,
        docs_url="storage/esg_corpus/manifest.json",
        free_tier_note="Local paper-grade ESG corpus and embeddings; no external request.",
        license_note="local corpus research use",
    )

    def _fetch_live(self, symbol: str) -> Any:
        report_dir = self.storage_root.parent / "esg_reports"
        paths = sorted(report_dir.glob(f"**/{symbol}_ESG_2025*.pdf"))[:3]
        if symbol.upper() == "AAPL":
            paths = sorted((report_dir / "Apple").glob("Apple * 2025*.pdf"))[:3]
        return [{"path": str(path), "size": path.stat().st_size} for path in paths]

    def normalize(self, symbol: str, raw: Any) -> list[dict[str, Any]]:
        rows = raw if isinstance(raw, list) else []
        return [
            self._item(
                symbol=symbol,
                item_type="esg_report",
                title=f"{symbol} local ESG report",
                summary=f"Local ESG report available: {Path(row.get('path', '')).name}",
                source=str(Path(row.get("path", "")).name),
                published_at="2025-12-31",
                confidence=0.88,
                metadata={"file_size": row.get("size"), "paper_grade_source": True},
            )
            for row in rows
        ]


class SecEdgarConnector(BaseFreeConnector):
    definition = ConnectorDefinition(
        provider_id="sec_edgar",
        display_name="SEC EDGAR",
        category="public_filings",
        env_keys=("SEC_EDGAR_EMAIL",),
        capabilities=("filings", "company_facts"),
        daily_limit=500,
        scan_budget=80,
        manual_reserve=420,
        priority=20,
        docs_url="https://www.sec.gov/os/accessing-edgar-data",
        free_tier_note="Public SEC EDGAR access; requires a responsible User-Agent email.",
        license_note="public SEC EDGAR data; comply with SEC fair access rules",
    )

    def _fetch_live(self, symbol: str) -> Any:
        return self._get_json(
            "https://www.sec.gov/files/company_tickers.json",
            headers={"User-Agent": f"esg-quant-research {self.api_key()}"},
        )

    def normalize(self, symbol: str, raw: Any) -> list[dict[str, Any]]:
        rows = raw.values() if isinstance(raw, dict) else []
        for row in rows:
            if str(row.get("ticker", "")).upper() == symbol.upper():
                return [
                    self._item(
                        symbol=symbol,
                        item_type="filing",
                        title=f"{symbol} SEC company registry match",
                        summary=f"CIK {row.get('cik_str')} / {row.get('title')}",
                        source="sec.company_tickers",
                        confidence=0.82,
                        metadata={"cik": row.get("cik_str"), "company_title": row.get("title")},
                    )
                ]
        return []


class FreeLiveConnectorRegistry:
    def __init__(self, storage_root: Path | None = None, timeout: float | None = None) -> None:
        self.repo_root = Path(__file__).resolve().parents[2]
        self.storage_root = storage_root or self.repo_root / "storage"
        self.quota = FreeQuotaLedger(self.storage_root)
        timeout = float(timeout or os.getenv("LIVE_CONNECTOR_TIMEOUT_SECONDS", "5") or 5)
        connector_types = [
            LocalEsgConnector,
            SecEdgarConnector,
            MarketauxConnector,
            TwelveDataConnector,
            TheNewsApiConnector,
            AlpacaMarketConnector,
            AlphaVantageConnector,
        ]
        self.connectors: dict[str, BaseFreeConnector] = {
            cls.definition.provider_id: cls(self.storage_root, self.quota, timeout=timeout) for cls in connector_types
        }

    def provider_ids(self, providers: list[str] | None = None, *, configured_only: bool = False) -> list[str]:
        requested = [str(item).strip().lower() for item in providers or [] if str(item).strip()]
        ids = requested or list(self.connectors)
        rows = [provider_id for provider_id in ids if provider_id in self.connectors]
        if configured_only:
            rows = [provider_id for provider_id in rows if self.connectors[provider_id].configured()]
        return rows

    def registry(self) -> dict[str, Any]:
        rows = [connector.registry_row() for connector in sorted(self.connectors.values(), key=lambda item: item.definition.priority)]
        return {
            "generated_at": utc_now(),
            "mode": "free_tier_first",
            "provider_count": len(rows),
            "providers": rows,
            "defaults": {
                "live_mode": "shadow_only",
                "quota_guard": True,
                "paper_inputs_protected": True,
                "alpaca_feed": os.getenv("MARKET_DATA_ALPACA_FEED", "iex"),
            },
        }

    def quota_status(self, providers: list[str] | None = None) -> dict[str, Any]:
        rows = [
            self.quota.status(self.connectors[provider_id].definition)
            for provider_id in self.provider_ids(providers)
        ]
        return {"generated_at": utc_now(), "quota_mode": "free_tier_guarded", "providers": rows}

    def health(self, providers: list[str] | None = None, *, live: bool = False) -> dict[str, Any]:
        rows = [self.connectors[provider_id].health_check(live=live) for provider_id in self.provider_ids(providers)]
        return {
            "generated_at": utc_now(),
            "mode": "live" if live else "configuration",
            "providers": rows,
            "summary": {
                "configured": sum(1 for row in rows if row.get("configured")),
                "ok": sum(1 for row in rows if row.get("status") in {"configured", "ok", "dry_run_ready"}),
                "failed": sum(1 for row in rows if row.get("status") not in {"configured", "ok", "dry_run_ready"}),
                "failure_isolation": "enabled",
            },
        }

    def test(self, providers: list[str] | None = None, *, symbol: str = "AAPL", dry_run: bool = True, quota_guard: bool = True) -> dict[str, Any]:
        results = [
            self.connectors[provider_id].sample_request(symbol, dry_run=dry_run, quota_guard=quota_guard).payload()
            for provider_id in self.provider_ids(providers)
        ]
        payload = {
            "run_id": f"connector-test-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{stable_hash([r['provider'] for r in results])[:8]}",
            "generated_at": utc_now(),
            "symbol": symbol.upper(),
            "dry_run": dry_run,
            "quota_guard": quota_guard,
            "results": results,
            "summary": self._summary(results),
        }
        self._persist_run(payload["run_id"], payload)
        return payload

    def live_scan(
        self,
        *,
        universe: list[str],
        providers: list[str] | None = None,
        decision_time: str | None = None,
        quota_guard: bool = True,
        persist: bool = True,
    ) -> dict[str, Any]:
        decision_time = decision_time or utc_now()
        symbols = [str(symbol).upper().strip() for symbol in universe if str(symbol).strip()] or ["AAPL"]
        results: list[dict[str, Any]] = []
        items: list[dict[str, Any]] = []
        for symbol in symbols:
            for provider_id in self.provider_ids(providers):
                result = self.connectors[provider_id].sample_request(symbol, dry_run=False, quota_guard=quota_guard)
                row = result.payload() | {"symbol": symbol}
                results.append(row)
                for item in result.normalized_items:
                    payload = dict(item)
                    payload["observed_at"] = decision_time
                    payload["dedup_source"] = f"{payload.get('provider')}:{payload.get('url') or payload.get('title')}"
                    payload["checksum"] = stable_hash(payload)
                    items.append(payload)
        run_id = f"connector-live-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{stable_hash([item.get('checksum') for item in items])[:8]}"
        payload = {
            "run_id": run_id,
            "generated_at": utc_now(),
            "decision_time": decision_time,
            "mode": "free_tier_live_shadow",
            "universe": symbols,
            "providers": self.provider_ids(providers),
            "quota_guard": quota_guard,
            "items": self._dedup_items(items),
            "results": results,
            "summary": self._summary(results),
            "lineage": [
                "free-tier connector registry",
                "provider-specific schema normalization",
                "quota guard and failure isolation",
                "shadow-mode evidence lake ingestion",
            ],
        }
        if persist:
            payload["storage"] = self._persist_run(run_id, payload)
        return payload

    def runs(self, *, limit: int = 20) -> dict[str, Any]:
        run_dir = self.storage_root / "intelligence" / "connector_runs"
        rows: list[dict[str, Any]] = []
        if run_dir.exists():
            for path in sorted(run_dir.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
                try:
                    rows.append(json.loads(path.read_text(encoding="utf-8")))
                except Exception:
                    continue
                if len(rows) >= max(1, int(limit)):
                    break
        return {"generated_at": utc_now(), "run_count": len(rows), "runs": rows}

    def _summary(self, results: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "provider_count": len({row.get("provider") for row in results}),
            "ok_count": sum(1 for row in results if row.get("status") in {"ok", "dry_run_ready", "configured"}),
            "failed_count": sum(1 for row in results if row.get("status") not in {"ok", "dry_run_ready", "configured", "empty"}),
            "normalized_count": sum(int(row.get("normalized_count", 0) or 0) for row in results),
            "quota_protected_count": sum(1 for row in results if row.get("status") == "quota_protected"),
            "failure_isolation": "enabled",
        }

    def _dedup_items(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        best: dict[str, dict[str, Any]] = {}
        for item in items:
            key = f"{item.get('symbol')}:{item.get('provider')}:{stable_hash([item.get('url'), item.get('title')])[:12]}"
            current = best.get(key)
            if current is None or float(item.get("confidence") or 0.0) > float(current.get("confidence") or 0.0):
                best[key] = item
        return list(best.values())

    def _persist_run(self, run_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        run_dir = self.storage_root / "intelligence" / "connector_runs"
        run_dir.mkdir(parents=True, exist_ok=True)
        path = run_dir / f"{run_id}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"local_path": str(path), "record_id": run_id, "record_type": "intelligence/connector_runs"}
