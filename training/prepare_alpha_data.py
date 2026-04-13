from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]

import sys

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from gateway.quant.market_data import MarketBarsResult, MarketDataGateway


DEFAULT_SYMBOLS = ["AAPL", "MSFT", "TSLA", "NVDA", "JPM", "NEE", "PG", "UNH"]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "alpha_ranker"
FEATURE_COLUMNS = [
    "momentum",
    "quality",
    "value",
    "alternative_data",
    "regime_fit",
    "esg_delta",
    "confidence",
    "risk_score",
    "overall_score",
    "e_score",
    "s_score",
    "g_score",
    "expected_return",
    "is_long",
    "is_neutral",
]
TARGET_COLUMNS = ["forward_return_5d", "forward_return_20d", "label_up_5d", "target_alpha_score"]


def stable_seed(*parts: str) -> int:
    raw = "::".join(parts).encode("utf-8")
    return int(hashlib.sha256(raw).hexdigest()[:8], 16)


def bounded(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def enrich_symbol(symbol: str, bars_result: MarketBarsResult, short_window: int, long_window: int) -> pd.DataFrame:
    bars = bars_result.bars.copy().sort_values("timestamp").reset_index(drop=True)
    bars["short_ma"] = bars["close"].rolling(short_window).mean()
    bars["long_ma"] = bars["close"].rolling(long_window).mean()
    bars["forward_close_5d"] = bars["close"].shift(-5)
    bars["forward_close_20d"] = bars["close"].shift(-20)
    bars = bars.dropna(subset=["short_ma", "long_ma", "forward_close_5d", "forward_close_20d"]).reset_index(drop=True)
    rows: list[dict[str, Any]] = []
    for index in range(1, len(bars)):
        row = bars.iloc[index]
        prev = bars.iloc[index - 1]
        close = float(row["close"])
        short_ma = float(row["short_ma"])
        long_ma = float(row["long_ma"])
        prev_short = float(prev["short_ma"])
        prev_long = float(prev["long_ma"])
        trend_gap = (short_ma - long_ma) / long_ma if long_ma else 0.0
        price_vs_long = (close - long_ma) / long_ma if long_ma else 0.0
        crossover = "golden_cross" if prev_short <= prev_long and short_ma > long_ma else "bullish_trend" if short_ma > long_ma else "neutral"
        seed = stable_seed(symbol, str(row["timestamp"])[:10])
        quality = 52 + ((seed // 7) % 24)
        value = 48 + ((seed // 11) % 22)
        alternative_data = 50 + ((seed // 13) % 18)
        regime_fit = 49 + ((seed // 17) % 22)
        esg_delta = 54 + ((seed // 19) % 20)
        momentum = bounded(50 + trend_gap * 1400 + price_vs_long * 600, 8, 96)
        e_score = bounded(0.36 * alternative_data + 0.28 * esg_delta + 0.10 * momentum + 18, 45, 94)
        s_score = bounded(0.42 * quality + 0.12 * value + 18, 42, 90)
        g_score = bounded(0.33 * quality + 0.18 * regime_fit + 20, 44, 92)
        overall_score = bounded(
            0.34 * momentum
            + 0.16 * quality
            + 0.10 * value
            + 0.12 * alternative_data
            + 0.12 * regime_fit
            + 0.16 * esg_delta,
            25,
            96,
        )
        action = "long" if short_ma > long_ma else "neutral"
        expected_return = bounded(trend_gap * 1.6 + max(price_vs_long, 0.0) * 0.45 + (0.012 if crossover == "golden_cross" else 0.0), -0.04, 0.16)
        risk_score = bounded(64 - trend_gap * 900 - (quality - 60) * 0.35 + (0 if action == "long" else 8), 16, 84)
        confidence = bounded(0.56 + min(index + 1, 200) / 500 + abs(trend_gap) * 3 + (0.05 if "cross" in crossover else 0.0), 0.56, 0.96)
        forward_return_5d = float(row["forward_close_5d"] / close - 1)
        forward_return_20d = float(row["forward_close_20d"] / close - 1)
        rows.append(
            {
                "date": pd.Timestamp(row["timestamp"]).date().isoformat(),
                "symbol": symbol,
                "provider": bars_result.provider,
                "momentum": round(momentum, 4),
                "quality": float(quality),
                "value": float(value),
                "alternative_data": float(alternative_data),
                "regime_fit": float(regime_fit),
                "esg_delta": float(esg_delta),
                "confidence": round(confidence, 4),
                "risk_score": round(risk_score, 4),
                "overall_score": round(overall_score, 4),
                "e_score": round(e_score, 4),
                "s_score": round(s_score, 4),
                "g_score": round(g_score, 4),
                "expected_return": round(expected_return, 6),
                "is_long": 1.0 if action == "long" else 0.0,
                "is_neutral": 1.0 if action == "neutral" else 0.0,
                "forward_return_5d": round(forward_return_5d, 6),
                "forward_return_20d": round(forward_return_20d, 6),
                "label_up_5d": 1 if forward_return_5d > 0 else 0,
            }
        )
    return pd.DataFrame(rows)


def synthetic_dataset(symbols: list[str], rows_per_symbol: int = 120) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for symbol in symbols:
        for index in range(rows_per_symbol):
            seed = stable_seed(symbol, str(index))
            momentum = 40 + seed % 50
            quality = 45 + ((seed // 7) % 35)
            value = 42 + ((seed // 11) % 30)
            alternative_data = 40 + ((seed // 13) % 40)
            regime_fit = 45 + ((seed // 17) % 30)
            esg_delta = 48 + ((seed // 19) % 30)
            overall = 0.34 * momentum + 0.16 * quality + 0.10 * value + 0.12 * alternative_data + 0.12 * regime_fit + 0.16 * esg_delta
            forward_return_5d = round(((overall - 60) / 600) + (((seed % 21) - 10) / 1000), 6)
            rows.append(
                {
                    "date": (pd.Timestamp("2024-01-01") + pd.Timedelta(days=index)).date().isoformat(),
                    "symbol": symbol,
                    "provider": "synthetic",
                    "momentum": float(momentum),
                    "quality": float(quality),
                    "value": float(value),
                    "alternative_data": float(alternative_data),
                    "regime_fit": float(regime_fit),
                    "esg_delta": float(esg_delta),
                    "confidence": round(bounded(0.58 + (seed % 150) / 1000, 0.58, 0.92), 4),
                    "risk_score": round(bounded(82 - quality * 0.55 - regime_fit * 0.15, 18, 84), 4),
                    "overall_score": round(overall, 4),
                    "e_score": round(bounded(0.5 * alternative_data + 0.5 * esg_delta, 45, 94), 4),
                    "s_score": round(bounded(0.65 * quality + 16, 42, 90), 4),
                    "g_score": round(bounded(0.4 * quality + 0.3 * regime_fit + 12, 44, 92), 4),
                    "expected_return": round(bounded(forward_return_5d * 0.8, -0.04, 0.16), 6),
                    "is_long": 1.0 if overall >= 64 else 0.0,
                    "is_neutral": 1.0 if 54 <= overall < 64 else 0.0,
                    "forward_return_5d": forward_return_5d,
                    "forward_return_20d": round(forward_return_5d * 2.5, 6),
                    "label_up_5d": 1 if forward_return_5d > 0 else 0,
                }
            )
    return pd.DataFrame(rows)


def split_dataset(frame: pd.DataFrame, val_fraction: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    if frame.empty:
        return frame, frame
    ranked_dates = sorted(frame["date"].unique())
    split_index = max(1, int(len(ranked_dates) * (1 - val_fraction)))
    split_date = ranked_dates[min(split_index, len(ranked_dates) - 1)]
    train = frame[frame["date"] < split_date].reset_index(drop=True)
    val = frame[frame["date"] >= split_date].reset_index(drop=True)
    if train.empty:
        train = frame.iloc[:- max(1, len(frame) // 5)].reset_index(drop=True)
        val = frame.iloc[len(train):].reset_index(drop=True)
    return train, val


def build_dataset(symbols: list[str], history_days: int, short_window: int, long_window: int) -> tuple[pd.DataFrame, dict[str, Any]]:
    market_data = MarketDataGateway()
    rows: list[pd.DataFrame] = []
    materialized: list[str] = []
    failed: dict[str, str] = {}
    for symbol in symbols:
        try:
            bars = market_data.get_daily_bars(symbol, limit=max(history_days, long_window + 80))
            enriched = enrich_symbol(symbol, bars, short_window, long_window)
            if not enriched.empty:
                rows.append(enriched)
                materialized.append(symbol)
        except Exception as exc:
            failed[symbol] = str(exc)
    dataset = pd.concat(rows, ignore_index=True) if rows else synthetic_dataset(symbols)
    dataset["target_alpha_score"] = dataset.groupby("date")["forward_return_5d"].rank(pct=True).fillna(0.5)
    return dataset, {"materialized_symbols": materialized, "failed_symbols": failed}


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare tabular alpha-ranker datasets from market data and factor proxies.")
    parser.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS), help="Comma-separated symbol list.")
    parser.add_argument("--history-days", type=int, default=420, help="Historical bars to request per symbol.")
    parser.add_argument("--short-window", type=int, default=20, help="Short moving-average window.")
    parser.add_argument("--long-window", type=int, default=60, help="Long moving-average window.")
    parser.add_argument("--val-fraction", type=float, default=0.2, help="Validation split fraction based on dates.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory for train/val csv outputs.")
    args = parser.parse_args()

    symbols = [item.strip().upper() for item in args.symbols.split(",") if item.strip()]
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    dataset, diagnostics = build_dataset(symbols, args.history_days, args.short_window, args.long_window)
    train, val = split_dataset(dataset, args.val_fraction)

    full_path = output_dir / "full_dataset.csv"
    train_path = output_dir / "train.csv"
    val_path = output_dir / "val.csv"
    dataset.to_csv(full_path, index=False)
    train.to_csv(train_path, index=False)
    val.to_csv(val_path, index=False)

    manifest = {
        "generated_at": pd.Timestamp.utcnow().isoformat(),
        "symbols": symbols,
        "feature_columns": FEATURE_COLUMNS,
        "target_columns": TARGET_COLUMNS,
        "rows_total": int(len(dataset)),
        "rows_train": int(len(train)),
        "rows_val": int(len(val)),
        "full_dataset": str(full_path),
        "train_csv": str(train_path),
        "val_csv": str(val_path),
        "diagnostics": diagnostics,
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
