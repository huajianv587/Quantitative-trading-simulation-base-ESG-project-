from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from gateway.config import settings
from gateway.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class MarketBarsResult:
    symbol: str
    provider: str
    timeframe: str
    cache_hit: bool
    bars: pd.DataFrame
    cache_path: str


class MarketDataGateway:
    def __init__(self) -> None:
        self.provider_order = self._provider_order()
        self.cache_path = self._resolve_cache_path()
        self.cache_max_age_hours = int(getattr(settings, "MARKET_DATA_CACHE_MAX_AGE_HOURS", 24) or 24)
        self.alpaca_key = getattr(settings, "ALPACA_API_KEY", "")
        self.alpaca_secret = getattr(settings, "ALPACA_API_SECRET", "")
        self.alpaca_feed = getattr(settings, "MARKET_DATA_ALPACA_FEED", "iex") or "iex"
        self.twelvedata_key = (
            os.getenv("TWELVEDATA_API_KEY", "")
            or os.getenv("TWELVEDATA_API", "")
            or os.getenv("TWELVE_DATA_API", "")
            or os.getenv("Twelve_Data_API", "")
        )
        self.history_days = int(getattr(settings, "MARKET_DATA_HISTORY_DAYS", 240) or 240)
        self.timeout = int(getattr(settings, "ALPACA_API_TIMEOUT", 20) or 20)
        self._init_cache()

    def status(self) -> dict[str, Any]:
        return {
            "provider_order": list(self.provider_order),
            "cache_path": str(self.cache_path),
            "cache_ready": self.cache_path.exists(),
            "twelvedata_ready": bool(self.twelvedata_key),
            "alpaca_market_data_ready": bool(self.alpaca_key and self.alpaca_secret),
            "alpaca_feed": self.alpaca_feed,
            "history_days": self.history_days,
        }

    def get_daily_bars(
        self,
        symbol: str,
        *,
        limit: int = 180,
        force_refresh: bool = False,
        provider_order_override: list[str] | None = None,
        cache_only: bool = False,
        allow_stale_cache: bool = True,
    ) -> MarketBarsResult:
        normalized_symbol = str(symbol or "").upper().strip()
        if not normalized_symbol:
            raise ValueError("Symbol is required for market data lookup")

        cached = self._load_cached_bars(normalized_symbol, timeframe="1Day", limit=limit)
        cached_provider = str(cached["provider"].iloc[-1]) if not cached.empty else ""
        if cache_only:
            if cached.empty:
                raise RuntimeError(f"No cached market data for {normalized_symbol}")
            return MarketBarsResult(
                symbol=normalized_symbol,
                provider=str(cached["provider"].iloc[-1]),
                timeframe="1Day",
                cache_hit=True,
                bars=self._finalize_bars(cached.tail(limit)),
                cache_path=str(self.cache_path),
            )
        preferred_provider = (provider_order_override or [None])[0]
        if (
            not force_refresh
            and not cached.empty
            and self._is_cache_fresh(cached)
            and len(cached) >= limit
            and (not preferred_provider or cached_provider == preferred_provider)
        ):
            return MarketBarsResult(
                symbol=normalized_symbol,
                provider=cached_provider,
                timeframe="1Day",
                cache_hit=True,
                bars=self._finalize_bars(cached.tail(limit)),
                cache_path=str(self.cache_path),
            )

        errors: list[str] = []
        provider_order = provider_order_override or self.provider_order
        for provider in provider_order:
            try:
                if provider == "twelvedata":
                    bars = self._fetch_twelvedata_daily_bars(normalized_symbol, limit=max(limit, self.history_days))
                elif provider == "alpaca":
                    bars = self._fetch_alpaca_daily_bars(normalized_symbol, limit=max(limit, self.history_days))
                elif provider == "yfinance":
                    bars = self._fetch_yfinance_daily_bars(normalized_symbol, limit=max(limit, self.history_days))
                else:
                    continue
                if bars.empty:
                    continue
                bars["provider"] = provider
                bars["timeframe"] = "1Day"
                bars["symbol"] = normalized_symbol
                bars["fetched_at"] = datetime.now(timezone.utc).isoformat()
                self._store_bars(normalized_symbol, "1Day", provider, bars)
                stored = self._load_cached_bars(normalized_symbol, timeframe="1Day", limit=limit)
                return MarketBarsResult(
                    symbol=normalized_symbol,
                    provider=provider,
                    timeframe="1Day",
                    cache_hit=False,
                    bars=self._finalize_bars(stored.tail(limit)),
                    cache_path=str(self.cache_path),
                )
            except Exception as exc:
                errors.append(f"{provider}: {exc}")

        if allow_stale_cache and not cached.empty:
            logger.warning(f"Using stale cached bars for {normalized_symbol}: {'; '.join(errors)}")
            return MarketBarsResult(
                symbol=normalized_symbol,
                provider=str(cached["provider"].iloc[-1]),
                timeframe="1Day",
                cache_hit=True,
                bars=self._finalize_bars(cached.tail(limit)),
                cache_path=str(self.cache_path),
            )

        raise RuntimeError(f"Unable to load market data for {normalized_symbol}: {'; '.join(errors) or 'no provider available'}")

    def _provider_order(self) -> list[str]:
        configured = str(getattr(settings, "MARKET_DATA_PROVIDER", "twelvedata,alpaca,yfinance") or "twelvedata,alpaca,yfinance")
        values = [item.strip().lower() for item in configured.split(",") if item.strip()]
        return values or ["twelvedata", "alpaca", "yfinance"]

    def _resolve_cache_path(self) -> Path:
        configured = str(getattr(settings, "MARKET_DATA_CACHE_DB", "") or "").strip()
        if configured:
            path = Path(configured)
        else:
            path = Path(__file__).resolve().parents[2] / "storage" / "quant" / "market_data" / "bars.sqlite3"
        if not path.is_absolute():
            path = Path(__file__).resolve().parents[2] / path
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.cache_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_cache(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS bars (
                    provider TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    ts TEXT NOT NULL,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    volume REAL,
                    trade_count REAL,
                    vwap REAL,
                    fetched_at TEXT NOT NULL,
                    PRIMARY KEY (provider, symbol, timeframe, ts)
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_bars_symbol_timeframe_ts ON bars(symbol, timeframe, ts DESC)"
            )
            connection.commit()

    def _load_cached_bars(self, symbol: str, *, timeframe: str, limit: int) -> pd.DataFrame:
        with self._connect() as connection:
            frame = pd.read_sql_query(
                """
                SELECT provider, symbol, timeframe, ts, open, high, low, close, volume, trade_count, vwap, fetched_at
                FROM bars
                WHERE symbol = ? AND timeframe = ?
                ORDER BY ts DESC
                LIMIT ?
                """,
                connection,
                params=(symbol, timeframe, max(1, int(limit))),
            )
        if frame.empty:
            return frame
        return frame.sort_values("ts").reset_index(drop=True)

    def _is_cache_fresh(self, frame: pd.DataFrame) -> bool:
        if frame.empty or "fetched_at" not in frame:
            return False
        fetched_at_raw = str(frame["fetched_at"].iloc[-1] or "").strip()
        if not fetched_at_raw:
            return False
        try:
            fetched_at = datetime.fromisoformat(fetched_at_raw.replace("Z", "+00:00"))
        except ValueError:
            return False
        return fetched_at >= datetime.now(timezone.utc) - timedelta(hours=self.cache_max_age_hours)

    def _store_bars(self, symbol: str, timeframe: str, provider: str, frame: pd.DataFrame) -> None:
        rows = [
            (
                provider,
                symbol,
                timeframe,
                str(row["timestamp"]),
                float(row["open"]),
                float(row["high"]),
                float(row["low"]),
                float(row["close"]),
                float(row.get("volume") or 0.0),
                float(row.get("trade_count") or 0.0),
                float(row.get("vwap") or 0.0),
                str(row["fetched_at"]),
            )
            for _, row in frame.iterrows()
        ]
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT OR REPLACE INTO bars (
                    provider, symbol, timeframe, ts, open, high, low, close, volume, trade_count, vwap, fetched_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            connection.commit()

    def _fetch_alpaca_daily_bars(self, symbol: str, limit: int) -> pd.DataFrame:
        if not (self.alpaca_key and self.alpaca_secret):
            raise RuntimeError("Alpaca market data credentials are not configured")

        start = datetime.now(timezone.utc) - timedelta(days=max(self.history_days, limit * 3))
        headers = {
            "APCA-API-KEY-ID": self.alpaca_key,
            "APCA-API-SECRET-KEY": self.alpaca_secret,
            "accept": "application/json",
        }
        collected: list[dict[str, Any]] = []
        next_page_token = None
        while len(collected) < limit:
            params: dict[str, Any] = {
                "symbols": symbol,
                "timeframe": "1Day",
                "start": start.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                "limit": min(max(limit * 2, 200), 1000),
                "feed": self.alpaca_feed,
                "adjustment": "raw",
                "sort": "asc",
            }
            if next_page_token:
                params["page_token"] = next_page_token

            response = requests.get(
                "https://data.alpaca.markets/v2/stocks/bars",
                headers=headers,
                params=params,
                timeout=self.timeout,
            )
            if response.status_code >= 400:
                raise RuntimeError(f"Alpaca market data {response.status_code}: {response.text[:400]}")

            payload = response.json()
            items = ((payload.get("bars") or {}).get(symbol) or [])
            collected.extend(items)
            next_page_token = payload.get("next_page_token")
            if not next_page_token or not items:
                break

        if not collected:
            raise RuntimeError(f"Alpaca returned no daily bars for {symbol}")

        frame = pd.DataFrame(
            [
                {
                    "timestamp": item.get("t"),
                    "open": item.get("o"),
                    "high": item.get("h"),
                    "low": item.get("l"),
                    "close": item.get("c"),
                    "volume": item.get("v"),
                    "trade_count": item.get("n"),
                    "vwap": item.get("vw"),
                }
                for item in collected
            ]
        )
        return self._finalize_bars(frame).tail(limit)

    def _fetch_twelvedata_daily_bars(self, symbol: str, limit: int) -> pd.DataFrame:
        if not self.twelvedata_key:
            raise RuntimeError("Twelve Data API key is not configured")

        response = requests.get(
            "https://api.twelvedata.com/time_series",
            params={
                "symbol": symbol,
                "interval": "1day",
                "outputsize": min(max(limit, 30), 5000),
                "apikey": self.twelvedata_key,
            },
            timeout=self.timeout,
        )
        if response.status_code >= 400:
            raise RuntimeError(f"Twelve Data {response.status_code}: {response.text[:400]}")
        payload = response.json()
        if isinstance(payload, dict) and payload.get("status") == "error":
            raise RuntimeError(f"Twelve Data error: {payload.get('message') or payload.get('code')}")
        values = payload.get("values", []) if isinstance(payload, dict) else []
        if not values:
            raise RuntimeError(f"Twelve Data returned no daily bars for {symbol}")
        frame = pd.DataFrame(
            [
                {
                    "timestamp": item.get("datetime"),
                    "open": item.get("open"),
                    "high": item.get("high"),
                    "low": item.get("low"),
                    "close": item.get("close"),
                    "volume": item.get("volume", 0),
                    "trade_count": 0,
                    "vwap": item.get("close"),
                }
                for item in values
            ]
        )
        return self._finalize_bars(frame).tail(limit)

    @staticmethod
    def _fetch_yfinance_daily_bars(symbol: str, limit: int) -> pd.DataFrame:
        try:
            import yfinance as yf  # type: ignore
        except Exception as exc:
            raise RuntimeError(f"yfinance is not available: {exc}") from exc

        period = f"{max(limit * 3, 120)}d"
        history = yf.Ticker(symbol).history(period=period, interval="1d", auto_adjust=False)
        if history.empty:
            raise RuntimeError(f"yfinance returned no daily bars for {symbol}")
        history = history.reset_index()
        timestamp_col = "Date" if "Date" in history.columns else history.columns[0]
        frame = pd.DataFrame(
            {
                "timestamp": history[timestamp_col].astype(str),
                "open": history["Open"],
                "high": history["High"],
                "low": history["Low"],
                "close": history["Close"],
                "volume": history.get("Volume", 0),
                "trade_count": 0,
                "vwap": history["Close"],
            }
        )
        return MarketDataGateway._finalize_bars(frame).tail(limit)

    @staticmethod
    def _finalize_bars(frame: pd.DataFrame) -> pd.DataFrame:
        if frame.empty:
            return frame
        normalized = frame.copy()
        if "ts" in normalized.columns and "timestamp" not in normalized.columns:
            normalized["timestamp"] = normalized["ts"]
        normalized["timestamp"] = pd.to_datetime(normalized["timestamp"], utc=True)
        for column in ("open", "high", "low", "close", "volume", "trade_count", "vwap"):
            if column in normalized.columns:
                normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
        normalized = normalized.dropna(subset=["timestamp", "close"]).sort_values("timestamp").reset_index(drop=True)
        return normalized
