from __future__ import annotations

import asyncio
import json
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable

from gateway.config import settings
from gateway.trading.models import TradingMonitorStatus

TriggerCallback = Callable[[dict[str, Any]], Awaitable[None]]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class AlpacaMarketMonitor:
    def __init__(self, *, on_trigger: TriggerCallback, watchlist_supplier: Callable[[], list[str]]) -> None:
        self._on_trigger = on_trigger
        self._watchlist_supplier = watchlist_supplier
        self._task: asyncio.Task | None = None
        self._status = TradingMonitorStatus(
            running=False,
            mode="paper",
            stream_mode="idle",
            watchlist=[],
            warnings=[],
            connection={"provider": "alpaca_market_data"},
        )
        self._bars: dict[str, deque[dict[str, Any]]] = defaultdict(lambda: deque(maxlen=120))
        self._debounce: dict[tuple[str, str], datetime] = {}

    async def start(self) -> TradingMonitorStatus:
        if self._task and not self._task.done():
            return self.status()
        watchlist = self._watchlist_supplier()
        self._status.watchlist = watchlist
        self._status.running = True
        self._status.stream_mode = "websocket"
        self._task = asyncio.create_task(self._run_websocket_loop(watchlist))
        return self.status()

    async def stop(self) -> TradingMonitorStatus:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            except Exception as exc:
                self._status.warnings.append(str(exc))
        self._task = None
        self._status.running = False
        self._status.stream_mode = "idle"
        return self.status()

    def status(self) -> TradingMonitorStatus:
        return self._status.model_copy(deep=True)

    async def process_bar(
        self,
        *,
        symbol: str,
        close: float,
        volume: float,
        observed_at: datetime | None = None,
        provider: str = "alpaca_market_ws",
    ) -> None:
        symbol = str(symbol or "").upper().strip()
        observed = observed_at or datetime.now(timezone.utc)
        bars = self._bars[symbol]
        bars.append({"close": float(close), "volume": float(volume), "observed_at": observed})
        self._status.last_event_at = observed.isoformat()
        if len(bars) < 2:
            return

        cutoff = observed - timedelta(minutes=5)
        recent = [bar for bar in bars if bar["observed_at"] >= cutoff]
        if len(recent) < 2:
            return

        start_price = float(recent[0]["close"])
        end_price = float(recent[-1]["close"])
        price_move = ((end_price - start_price) / start_price) if start_price else 0.0
        prior_volumes = [float(bar["volume"]) for bar in list(bars)[:-1][-20:]]
        avg_volume = sum(prior_volumes) / max(len(prior_volumes), 1)
        latest_volume = float(recent[-1]["volume"])
        volume_ratio = latest_volume / max(avg_volume, 1.0)

        if abs(price_move) >= 0.02:
            await self._emit_trigger(
                symbol=symbol,
                trigger_type="price_move",
                trigger_value=round(price_move, 6),
                threshold=0.02,
                provider=provider,
                observed_at=observed,
                metadata={"window_minutes": 5, "close": end_price},
            )
        if volume_ratio >= 3.0:
            await self._emit_trigger(
                symbol=symbol,
                trigger_type="volume_spike",
                trigger_value=round(volume_ratio, 6),
                threshold=3.0,
                provider=provider,
                observed_at=observed,
                metadata={"window_minutes": 5, "latest_volume": latest_volume, "avg_volume": avg_volume},
            )

    async def _emit_trigger(
        self,
        *,
        symbol: str,
        trigger_type: str,
        trigger_value: float,
        threshold: float,
        provider: str,
        observed_at: datetime,
        metadata: dict[str, Any],
    ) -> None:
        key = (symbol, trigger_type)
        last = self._debounce.get(key)
        if last and (observed_at - last).total_seconds() < 300:
            return
        self._debounce[key] = observed_at
        self._status.trigger_count += 1
        self._status.last_trigger = {
            "symbol": symbol,
            "trigger_type": trigger_type,
            "trigger_value": trigger_value,
            "threshold": threshold,
            "observed_at": observed_at.isoformat(),
        }
        await self._on_trigger(
            {
                "symbol": symbol,
                "trigger_type": trigger_type,
                "trigger_value": trigger_value,
                "threshold": threshold,
                "provider": provider,
                "observed_at": observed_at.isoformat(),
                "metadata": metadata,
            }
        )

    async def _run_websocket_loop(self, watchlist: list[str]) -> None:
        try:
            import websockets  # type: ignore
        except Exception as exc:
            self._status.stream_mode = "idle"
            self._status.running = False
            self._status.warnings.append(f"websockets unavailable: {exc}")
            return

        key = getattr(settings, "ALPACA_API_KEY", "")
        secret = getattr(settings, "ALPACA_API_SECRET", "")
        if not (key and secret):
            self._status.stream_mode = "idle"
            self._status.running = False
            self._status.warnings.append("Alpaca credentials are not configured for market-data monitor.")
            return

        url = getattr(settings, "ALPACA_MARKET_DATA_WS_URL", "") or "wss://stream.data.alpaca.markets/v2/iex"
        try:
            async with websockets.connect(url, ping_interval=20, ping_timeout=20) as websocket:
                await websocket.send(json.dumps({"action": "auth", "key": key, "secret": secret}))
                await websocket.send(json.dumps({"action": "subscribe", "bars": watchlist}))
                self._status.connection = {"provider": "alpaca_market_data", "url": url, "subscribed": list(watchlist)}
                while True:
                    message = await websocket.recv()
                    payload = json.loads(message)
                    rows = payload if isinstance(payload, list) else [payload]
                    for row in rows:
                        if str(row.get("T", "")).lower() != "b":
                            continue
                        await self.process_bar(
                            symbol=row.get("S") or row.get("symbol"),
                            close=float(row.get("c") or 0.0),
                            volume=float(row.get("v") or 0.0),
                            observed_at=self._parse_bar_time(row.get("t")),
                        )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._status.warnings.append(f"monitor stream failed: {exc}")
            self._status.stream_mode = "idle"
            self._status.running = False

    @staticmethod
    def _parse_bar_time(value: Any) -> datetime:
        raw = str(value or "")
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(timezone.utc)
        except Exception:
            return datetime.now(timezone.utc)
