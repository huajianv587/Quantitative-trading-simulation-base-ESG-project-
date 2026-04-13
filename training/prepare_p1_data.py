from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]

import sys

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from gateway.quant.p1_stack import P1_FEATURE_COLUMNS
from training.prepare_alpha_data import (
    DEFAULT_SYMBOLS,
    build_dataset as build_alpha_dataset,
    split_dataset,
    synthetic_dataset,
)

DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "p1_stack"
P1_TARGET_COLUMNS = [
    "forward_return_1d",
    "forward_return_5d",
    "forward_return_20d",
    "future_volatility_10d",
    "future_max_drawdown_20d",
    "regime_label",
    "target_alpha_score",
]


def enrich_p1_features(frame: pd.DataFrame) -> pd.DataFrame:
    enriched = frame.copy()
    if "target_alpha_score" not in enriched.columns:
        enriched["target_alpha_score"] = (
            enriched.groupby("date")["forward_return_5d"].rank(pct=True).fillna(0.5)
        )
    enriched["alpha_baseline"] = ((enriched["overall_score"] - 25.0) / 75.0).clip(0.0, 1.0)
    enriched["fundamental_score"] = (
        0.40 * enriched["quality"]
        + 0.20 * enriched["value"]
        + 0.15 * enriched["g_score"]
        + 0.15 * enriched["s_score"]
        + 0.10 * enriched["regime_fit"]
    ).clip(35.0, 95.0)
    enriched["news_sentiment_score"] = (
        0.36 * enriched["momentum"]
        + 0.24 * enriched["alternative_data"]
        + 0.14 * enriched["esg_delta"]
        + 18.0 * enriched["confidence"]
        - 0.15 * enriched["risk_score"]
    ).clip(12.0, 96.0)
    enriched["trend_gap"] = ((enriched["momentum"] - 50.0) / 100.0).clip(-0.45, 0.45)
    enriched["relative_strength_20d"] = (
        enriched["expected_return"] * 2.2
        + enriched["trend_gap"] * 0.18
        + (enriched["regime_fit"] - 50.0) / 600.0
    ).clip(-0.35, 0.35)
    enriched["return_1d_proxy"] = (
        enriched["expected_return"] * 0.28
        + enriched["trend_gap"] / 12.0
    ).clip(-0.08, 0.08)
    enriched["return_5d_proxy"] = (
        enriched["expected_return"] + enriched["relative_strength_20d"] * 0.12
    ).clip(-0.12, 0.18)
    enriched["return_20d_proxy"] = (
        enriched["return_5d_proxy"] * 2.4
        + (enriched["fundamental_score"] - 60.0) / 500.0
    ).clip(-0.20, 0.30)
    enriched["volatility_5d"] = (
        0.08 + enriched["risk_score"] / 380.0 + enriched["trend_gap"].abs() / 4.0
    ).clip(0.04, 0.40)
    enriched["volatility_20d"] = (
        enriched["volatility_5d"] * 1.18 + (-enriched["return_5d_proxy"]).clip(lower=0.0) * 0.9
    ).clip(0.05, 0.55)
    enriched["drawdown_20d"] = (
        0.04 + enriched["volatility_20d"] * 0.55 + (58.0 - enriched["overall_score"]).clip(lower=0.0) / 260.0
    ).clip(0.03, 0.40)
    enriched["drawdown_60d"] = (enriched["drawdown_20d"] * 1.45).clip(0.04, 0.58)
    enriched["benchmark_return_5d"] = (0.002 + (enriched["regime_fit"] - 50.0) / 5000.0).clip(-0.04, 0.05)
    enriched["beta_proxy"] = (
        0.72
        + enriched["risk_score"] / 145.0
        - enriched["g_score"] / 380.0
        + enriched["trend_gap"].abs() * 0.35
    ).clip(0.35, 1.75)
    enriched["forward_return_1d"] = (
        enriched["forward_return_5d"] * 0.35 + (enriched["target_alpha_score"] - 0.5) / 50.0
    ).clip(-0.08, 0.08)
    enriched["future_volatility_10d"] = (
        0.08
        + enriched["forward_return_5d"].abs() * 1.8
        + enriched["risk_score"] / 400.0
        + (50.0 - enriched["momentum"]).clip(lower=0.0) / 500.0
    ).clip(0.06, 0.65)
    enriched["future_max_drawdown_20d"] = (
        0.04
        + enriched["future_volatility_10d"] * 0.55
        + (60.0 - enriched["overall_score"]).clip(lower=0.0) / 300.0
    ).clip(0.03, 0.55)
    regime = pd.Series("neutral", index=enriched.index, dtype="object")
    risk_on_mask = (
        (enriched["trend_gap"] > 0.04)
        & (enriched["future_volatility_10d"] < 0.22)
        & (enriched["forward_return_5d"] > 0)
    )
    risk_off_mask = (
        (enriched["trend_gap"] < -0.03)
        | (enriched["future_max_drawdown_20d"] > 0.22)
        | (enriched["future_volatility_10d"] > 0.30)
    )
    regime.loc[risk_on_mask] = "risk_on"
    regime.loc[risk_off_mask] = "risk_off"
    enriched["regime_label"] = regime
    for feature in P1_FEATURE_COLUMNS:
        if feature not in enriched.columns:
            enriched[feature] = 0.0
    return enriched


def synthetic_p1_dataset(symbols: list[str], rows_per_symbol: int = 140) -> pd.DataFrame:
    return enrich_p1_features(synthetic_dataset(symbols, rows_per_symbol=rows_per_symbol))


def build_p1_dataset(
    symbols: list[str],
    history_days: int,
    short_window: int,
    long_window: int,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    dataset, diagnostics = build_alpha_dataset(symbols, history_days, short_window, long_window)
    return enrich_p1_features(dataset), diagnostics


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare P1 alpha + risk stack datasets.")
    parser.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS), help="Comma-separated symbol list.")
    parser.add_argument("--history-days", type=int, default=420, help="Historical bars to request per symbol.")
    parser.add_argument("--short-window", type=int, default=20, help="Short moving-average window.")
    parser.add_argument("--long-window", type=int, default=60, help="Long moving-average window.")
    parser.add_argument("--val-fraction", type=float, default=0.2, help="Validation split fraction.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Output directory for csv artifacts.")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    symbols = [item.strip().upper() for item in args.symbols.split(",") if item.strip()]
    dataset, diagnostics = build_p1_dataset(symbols, args.history_days, args.short_window, args.long_window)
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
        "feature_columns": P1_FEATURE_COLUMNS,
        "target_columns": P1_TARGET_COLUMNS,
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
