from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]

import sys

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from training.prepare_alpha_data import DEFAULT_SYMBOLS, split_dataset
from training.prepare_p2_data import build_p1_dataset, enrich_signal_frame

DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "event_classifier"
DEFAULT_INPUT_CSV = PROJECT_ROOT / "data" / "p2_stack" / "full_signal_dataset.csv"

SYMBOL_METADATA = {
    "AAPL": {"company_name": "Apple", "sector": "Technology"},
    "MSFT": {"company_name": "Microsoft", "sector": "Technology"},
    "TSLA": {"company_name": "Tesla", "sector": "Consumer Discretionary"},
    "NVDA": {"company_name": "NVIDIA", "sector": "Technology"},
    "JPM": {"company_name": "JPMorgan Chase", "sector": "Financials"},
    "NEE": {"company_name": "NextEra Energy", "sector": "Utilities"},
    "PG": {"company_name": "Procter & Gamble", "sector": "Consumer Staples"},
    "UNH": {"company_name": "UnitedHealth", "sector": "Healthcare"},
}

TASK_COLUMNS = [
    "sentiment_label",
    "controversy_label",
    "esg_axis_label",
    "impact_direction",
    "regime_label",
]


def _bounded(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _symbol_meta(symbol: str) -> dict[str, str]:
    payload = SYMBOL_METADATA.get(str(symbol).upper(), {})
    return {
        "company_name": payload.get("company_name", str(symbol).upper()),
        "sector": payload.get("sector", "Unknown"),
    }


def _ensure_source_frame(path: Path, symbols: list[str]) -> pd.DataFrame:
    if path.exists():
        return pd.read_csv(path)
    p1_frame, _ = build_p1_dataset(symbols, history_days=420, short_window=20, long_window=60)
    return enrich_signal_frame(p1_frame)


def _sentiment_label(row: pd.Series) -> str:
    predicted_return = float(row.get("predicted_return_5d", row.get("forward_return_5d", 0.0)))
    risk_score = float(row.get("risk_score", 50.0))
    if predicted_return >= 0.02 and risk_score <= 58:
        return "positive"
    if predicted_return <= -0.008 or risk_score >= 76:
        return "negative"
    return "neutral"


def _controversy_label(row: pd.Series) -> str:
    risk_component = float(row.get("risk_score", 50.0)) / 100.0
    drawdown_component = float(row.get("predicted_drawdown_20d", row.get("future_max_drawdown_20d", 0.12)))
    contagion_component = float(row.get("graph_contagion_risk", 0.22))
    composite = _bounded(
        0.38 * risk_component + 0.34 * drawdown_component + 0.28 * contagion_component,
        0.0,
        1.0,
    )
    if composite >= 0.68:
        return "critical"
    if composite >= 0.52:
        return "high"
    if composite >= 0.34:
        return "medium"
    return "low"


def _esg_axis_label(row: pd.Series) -> str:
    scores = {
        "environmental": float(row.get("e_score", 50.0)),
        "social": float(row.get("s_score", 50.0)),
        "governance": float(row.get("g_score", 50.0)),
    }
    return min(scores, key=scores.get)


def _impact_direction(row: pd.Series) -> str:
    sentiment = _sentiment_label(row)
    controversy = _controversy_label(row)
    if sentiment == "positive" and controversy in {"low", "medium"}:
        return "opportunity"
    if sentiment == "negative" and controversy in {"high", "critical"}:
        return "risk_event"
    return "watchlist"


def _regime_phrase(regime_label: str) -> str:
    return {
        "risk_on": "risk-on regime with supportive breadth",
        "risk_off": "risk-off regime with elevated caution",
        "neutral": "neutral regime with mixed follow-through",
    }.get(str(regime_label).lower(), "neutral regime with mixed follow-through")


def _render_text(row: pd.Series) -> str:
    symbol = str(row["symbol"]).upper()
    meta = _symbol_meta(symbol)
    sentiment = _sentiment_label(row)
    controversy = _controversy_label(row)
    esg_axis = _esg_axis_label(row)
    regime = str(row.get("regime_label", "neutral")).lower()
    expected_5d = float(row.get("predicted_return_5d", row.get("forward_return_5d", 0.0)))
    expected_1d = float(row.get("predicted_return_1d", row.get("forward_return_1d", 0.0)))
    drawdown = float(row.get("predicted_drawdown_20d", row.get("future_max_drawdown_20d", 0.12)))
    volatility = float(row.get("predicted_volatility_10d", row.get("future_volatility_10d", 0.15)))
    risk_score = float(row.get("risk_score", 50.0))
    momentum = float(row.get("momentum", 50.0))
    quality = float(row.get("quality", 50.0))
    value = float(row.get("value", 50.0))
    confidence = float(row.get("confidence", 0.6))

    headline = (
        f"{meta['company_name']} ({symbol}) sits in the {meta['sector']} sector with a "
        f"{sentiment} tone and {controversy} controversy pressure."
    )
    context = (
        f"The model sees a {_regime_phrase(regime)}. Expected 1-day return is {expected_1d:.2%}, "
        f"expected 5-day return is {expected_5d:.2%}, predicted 10-day volatility is {volatility:.2%}, "
        f"and predicted 20-day drawdown is {drawdown:.2%}."
    )
    esg = (
        f"Primary ESG pressure points to the {esg_axis} dimension. Scores are E {float(row.get('e_score', 50.0)):.1f}, "
        f"S {float(row.get('s_score', 50.0)):.1f}, G {float(row.get('g_score', 50.0)):.1f}. "
        f"Risk score is {risk_score:.1f}, momentum {momentum:.1f}, quality {quality:.1f}, value {value:.1f}, "
        f"and signal confidence {confidence:.2f}."
    )
    return " ".join([headline, context, esg])


def build_dataset(frame: pd.DataFrame) -> pd.DataFrame:
    dataset = frame.copy()
    if "symbol" not in dataset.columns:
        raise ValueError("Expected a signal frame with a symbol column.")
    dataset["text"] = dataset.apply(_render_text, axis=1)
    dataset["sentiment_label"] = dataset.apply(_sentiment_label, axis=1)
    dataset["controversy_label"] = dataset.apply(_controversy_label, axis=1)
    dataset["esg_axis_label"] = dataset.apply(_esg_axis_label, axis=1)
    dataset["impact_direction"] = dataset.apply(_impact_direction, axis=1)
    keep_columns = [
        "date",
        "symbol",
        "text",
        "sentiment_label",
        "controversy_label",
        "esg_axis_label",
        "impact_direction",
        "regime_label",
        "risk_score",
        "overall_score",
        "e_score",
        "s_score",
        "g_score",
        "predicted_return_1d",
        "predicted_return_5d",
        "predicted_volatility_10d",
        "predicted_drawdown_20d",
        "graph_contagion_risk",
    ]
    for column in keep_columns:
        if column not in dataset.columns:
            dataset[column] = 0.0 if column != "regime_label" else "neutral"
    return dataset[keep_columns].sort_values(["date", "symbol"]).reset_index(drop=True)


def _write_jsonl(frame: pd.DataFrame, label_column: str, path: Path) -> None:
    rows = [
        {"text": str(row["text"]), "label": str(row[label_column]), "symbol": str(row["symbol"]), "date": str(row["date"])}
        for _, row in frame.iterrows()
    ]
    with path.open("w", encoding="utf-8") as handle:
        for payload in rows:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare bootstrap news / controversy classifier datasets.")
    parser.add_argument("--input-csv", default=str(DEFAULT_INPUT_CSV), help="Source P2 signal dataset.")
    parser.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS), help="Fallback symbol list when input csv is missing.")
    parser.add_argument("--val-fraction", type=float, default=0.2, help="Validation split fraction.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Output directory for classifier assets.")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    symbols = [item.strip().upper() for item in args.symbols.split(",") if item.strip()]
    frame = _ensure_source_frame(Path(args.input_csv), symbols)
    dataset = build_dataset(frame)
    train, val = split_dataset(dataset, args.val_fraction)

    dataset.to_csv(output_dir / "full_dataset.csv", index=False)
    train.to_csv(output_dir / "train.csv", index=False)
    val.to_csv(output_dir / "val.csv", index=False)

    task_summary: dict[str, dict[str, object]] = {}
    for task in TASK_COLUMNS:
        task_dir = output_dir / task
        task_dir.mkdir(parents=True, exist_ok=True)
        _write_jsonl(train, task, task_dir / "train.jsonl")
        _write_jsonl(val, task, task_dir / "val.jsonl")
        task_summary[task] = {
            "train_counts": train[task].value_counts().to_dict(),
            "val_counts": val[task].value_counts().to_dict(),
        }

    manifest = {
        "generated_at": pd.Timestamp.utcnow().isoformat(),
        "input_csv": str(args.input_csv),
        "rows_total": int(len(dataset)),
        "rows_train": int(len(train)),
        "rows_val": int(len(val)),
        "tasks": task_summary,
        "files": {
            "full_dataset": str(output_dir / "full_dataset.csv"),
            "train_csv": str(output_dir / "train.csv"),
            "val_csv": str(output_dir / "val.csv"),
        },
        "base_models": [
            "ProsusAI/finbert",
            "microsoft/deberta-v3-base",
        ],
        "notes": [
            "This is a bootstrap text-classification corpus synthesized from P2 signal features.",
            "For production-grade event classification, replace or augment it with real news headlines and labeled controversy records.",
        ],
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
