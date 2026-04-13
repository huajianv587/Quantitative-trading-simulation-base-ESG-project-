from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]

import sys

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from gateway.quant.p2_decision import P2_PRIORITY_FEATURE_COLUMNS, P2_STRATEGY_SNAPSHOT_COLUMNS
from training.prepare_alpha_data import DEFAULT_SYMBOLS, split_dataset
from training.prepare_p1_data import build_p1_dataset

DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "p2_stack"


def enrich_signal_frame(frame: pd.DataFrame) -> pd.DataFrame:
    enriched = frame.copy()
    enriched["p1_stack_score"] = (
        0.22 * enriched["alpha_baseline"]
        + 0.16 * ((enriched["forward_return_1d"] + 0.08) / 0.16).clip(0.0, 1.0)
        + 0.28 * ((enriched["forward_return_5d"] + 0.12) / 0.30).clip(0.0, 1.0)
        + 0.18 * (1.0 - (enriched["future_volatility_10d"] / 0.65).clip(0.0, 1.0))
        + 0.16 * (1.0 - (enriched["future_max_drawdown_20d"] / 0.55).clip(0.0, 1.0))
    ).clip(0.0, 1.0)
    enriched["graph_centrality"] = (
        0.18
        + enriched["beta_proxy"] / 4.0
        + (enriched["momentum"] - 50.0).abs() / 260.0
        + (enriched["regime_fit"] - 50.0).abs() / 320.0
    ).clip(0.0, 1.0)
    enriched["graph_contagion_risk"] = (
        0.20
        + enriched["future_volatility_10d"] * 0.55
        + enriched["future_max_drawdown_20d"] * 0.65
        + (enriched["risk_score"] / 220.0)
    ).clip(0.0, 1.0)
    enriched["graph_diversification_score"] = (
        1.02
        - enriched["graph_centrality"] * 0.55
        - (enriched["beta_proxy"] - 1.0).abs() * 0.22
    ).clip(0.0, 1.0)
    enriched["graph_influence_score"] = (
        0.42 * enriched["p1_stack_score"]
        + 0.28 * enriched["graph_centrality"]
        + 0.18 * enriched["confidence"]
        + 0.12 * ((enriched["forward_return_5d"] + 0.12) / 0.30).clip(0.0, 1.0)
    ).clip(0.0, 1.0)
    enriched["predicted_return_1d"] = enriched["forward_return_1d"]
    enriched["predicted_return_5d"] = enriched["forward_return_5d"]
    enriched["predicted_volatility_10d"] = enriched["future_volatility_10d"]
    enriched["predicted_drawdown_20d"] = enriched["future_max_drawdown_20d"]
    enriched["is_risk_on"] = (enriched["regime_label"] == "risk_on").astype(float)
    enriched["is_risk_off"] = (enriched["regime_label"] == "risk_off").astype(float)
    enriched["strategy_label"] = "balanced_quality_growth"
    drawdown_cut = float(enriched["future_max_drawdown_20d"].quantile(0.68))
    volatility_cut = float(enriched["future_volatility_10d"].quantile(0.62))
    momentum_cut = float(enriched["forward_return_5d"].quantile(0.72))
    centrality_cut = float(enriched["graph_centrality"].quantile(0.72))
    beta_cut = float(enriched["beta_proxy"].quantile(0.72))
    defensive_mask = (enriched["regime_label"] == "risk_off") | (
        (enriched["future_max_drawdown_20d"] >= drawdown_cut) & (enriched["future_volatility_10d"] >= volatility_cut)
    )
    momentum_mask = (
        (enriched["forward_return_5d"] >= momentum_cut)
        & (enriched["trend_gap"] >= enriched["trend_gap"].quantile(0.58))
        & (enriched["future_volatility_10d"] <= volatility_cut)
    )
    diversified_mask = (
        ((enriched["graph_centrality"] >= centrality_cut) | (enriched["beta_proxy"] >= beta_cut))
        & ~defensive_mask
        & ~momentum_mask
    )
    enriched.loc[defensive_mask, "strategy_label"] = "defensive_quality"
    enriched.loc[momentum_mask & ~defensive_mask, "strategy_label"] = "momentum_leaders"
    enriched.loc[diversified_mask, "strategy_label"] = "diversified_barbell"
    enriched["selector_priority_target"] = (
        0.34 * enriched["p1_stack_score"]
        + 0.22 * ((enriched["forward_return_5d"] + 0.12) / 0.30).clip(0.0, 1.0)
        + 0.16 * (enriched["fundamental_score"] / 100.0)
        + 0.14 * enriched["graph_diversification_score"]
        + 0.14 * (1.0 - enriched["graph_contagion_risk"])
    ).clip(0.0, 1.0)
    for feature in P2_PRIORITY_FEATURE_COLUMNS:
        if feature not in enriched.columns:
            enriched[feature] = 0.0
    return enriched


def build_snapshot_frame(signal_frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, float | str]] = []
    for current_date, day_slice in signal_frame.groupby("date"):
        row = {
            "date": current_date,
            "breadth_long_ratio": float((day_slice["forward_return_5d"] > 0).mean()),
            "risk_on_ratio": float((day_slice["regime_label"] == "risk_on").mean()),
            "risk_off_ratio": float((day_slice["regime_label"] == "risk_off").mean()),
            "avg_p1_score": float(day_slice["p1_stack_score"].mean()),
            "avg_expected_return": float(day_slice["expected_return"].mean()),
            "avg_return_5d": float(day_slice["forward_return_5d"].mean()),
            "avg_volatility_10d": float(day_slice["future_volatility_10d"].mean()),
            "avg_drawdown_20d": float(day_slice["future_max_drawdown_20d"].mean()),
            "avg_quality": float(day_slice["quality"].mean()),
            "avg_momentum": float(day_slice["momentum"].mean()),
            "avg_confidence": float(day_slice["confidence"].mean()),
            "avg_graph_centrality": float(day_slice["graph_centrality"].mean()),
            "avg_graph_contagion": float(day_slice["graph_contagion_risk"].mean()),
            "avg_diversification": float(day_slice["graph_diversification_score"].mean()),
            "sector_concentration": 0.5,
            "strategy_label": "balanced_quality_growth",
        }
        if row["risk_off_ratio"] >= 0.4 or row["avg_drawdown_20d"] >= float(signal_frame["future_max_drawdown_20d"].quantile(0.68)):
            row["strategy_label"] = "defensive_quality"
        elif row["risk_on_ratio"] >= 0.34 and row["avg_return_5d"] >= float(signal_frame["forward_return_5d"].quantile(0.60)):
            row["strategy_label"] = "momentum_leaders"
        elif row["avg_graph_centrality"] >= float(signal_frame["graph_centrality"].quantile(0.70)):
            row["strategy_label"] = "diversified_barbell"
        rows.append(row)
    snapshot_frame = pd.DataFrame(rows)
    for feature in P2_STRATEGY_SNAPSHOT_COLUMNS:
        if feature not in snapshot_frame.columns:
            snapshot_frame[feature] = 0.0
    return snapshot_frame.sort_values("date").reset_index(drop=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare P2 graph + strategy-selector datasets.")
    parser.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS), help="Comma-separated symbol list.")
    parser.add_argument("--history-days", type=int, default=420, help="Historical bars per symbol.")
    parser.add_argument("--short-window", type=int, default=20, help="Short moving-average window.")
    parser.add_argument("--long-window", type=int, default=60, help="Long moving-average window.")
    parser.add_argument("--val-fraction", type=float, default=0.2, help="Validation split fraction.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Output directory for csv artifacts.")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    symbols = [item.strip().upper() for item in args.symbols.split(",") if item.strip()]
    p1_frame, diagnostics = build_p1_dataset(symbols, args.history_days, args.short_window, args.long_window)
    signal_frame = enrich_signal_frame(p1_frame)
    snapshot_frame = build_snapshot_frame(signal_frame)
    train_signals, val_signals = split_dataset(signal_frame, args.val_fraction)
    train_snapshots, val_snapshots = split_dataset(snapshot_frame, args.val_fraction)

    signal_frame.to_csv(output_dir / "full_signal_dataset.csv", index=False)
    train_signals.to_csv(output_dir / "train_signals.csv", index=False)
    val_signals.to_csv(output_dir / "val_signals.csv", index=False)
    snapshot_frame.to_csv(output_dir / "full_snapshot_dataset.csv", index=False)
    train_snapshots.to_csv(output_dir / "train_snapshots.csv", index=False)
    val_snapshots.to_csv(output_dir / "val_snapshots.csv", index=False)

    manifest = {
        "generated_at": pd.Timestamp.utcnow().isoformat(),
        "symbols": symbols,
        "priority_feature_columns": P2_PRIORITY_FEATURE_COLUMNS,
        "snapshot_feature_columns": P2_STRATEGY_SNAPSHOT_COLUMNS,
        "rows_signal_total": int(len(signal_frame)),
        "rows_signal_train": int(len(train_signals)),
        "rows_signal_val": int(len(val_signals)),
        "rows_snapshot_total": int(len(snapshot_frame)),
        "rows_snapshot_train": int(len(train_snapshots)),
        "rows_snapshot_val": int(len(val_snapshots)),
        "diagnostics": diagnostics,
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
