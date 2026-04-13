from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from training.p1_training_lib import fit_and_persist_suite, load_frame, predict_suite, score_p1_frame, summarize_rank_performance

DEFAULT_DATA_DIR = PROJECT_ROOT / "data" / "p1_stack"
DEFAULT_CKPT_DIR = PROJECT_ROOT / "model-serving" / "checkpoint" / "p1_suite"


def rolling_windows(dates: list[str], train_span: int, test_span: int, max_windows: int) -> list[tuple[list[str], list[str]]]:
    windows: list[tuple[list[str], list[str]]] = []
    cursor = 0
    while cursor + train_span + test_span <= len(dates) and len(windows) < max_windows:
        train_dates = dates[cursor:cursor + train_span]
        test_dates = dates[cursor + train_span:cursor + train_span + test_span]
        windows.append((train_dates, test_dates))
        cursor += test_span
    return windows


def main() -> int:
    parser = argparse.ArgumentParser(description="Run walk-forward evaluation for the P1 model suite.")
    parser.add_argument("--full-csv", default=str(DEFAULT_DATA_DIR / "full_dataset.csv"), help="Full dataset csv path.")
    parser.add_argument("--backend", default="sklearn_gbdt", choices=["auto", "xgboost", "lightgbm", "catboost", "sklearn_gbdt"], help="Backend for each walk-forward window.")
    parser.add_argument("--train-dates", type=int, default=60, help="Number of unique dates in each train window.")
    parser.add_argument("--test-dates", type=int, default=20, help="Number of unique dates in each test window.")
    parser.add_argument("--max-windows", type=int, default=4, help="Maximum walk-forward windows.")
    parser.add_argument("--output-dir", default=str(DEFAULT_CKPT_DIR), help="Directory to write walk-forward summary.")
    args = parser.parse_args()

    full = load_frame(args.full_csv)
    dates = sorted(full["date"].astype(str).unique().tolist())
    windows = rolling_windows(dates, train_span=args.train_dates, test_span=args.test_dates, max_windows=args.max_windows)
    results: list[dict[str, object]] = []
    for index, (train_dates, test_dates) in enumerate(windows):
        train = full[full["date"].isin(train_dates)].reset_index(drop=True)
        test = full[full["date"].isin(test_dates)].reset_index(drop=True)
        if train.empty or test.empty:
            continue
        with tempfile.TemporaryDirectory(prefix=f"p1_wf_{index}_") as tmp_dir:
            fit_and_persist_suite(train=train, val=test, output_dir=tmp_dir, backend=args.backend)
            predictions = predict_suite(tmp_dir, test)
            scored = pd.concat([test.reset_index(drop=True), predictions.reset_index(drop=True)], axis=1)
            scored["p1_stack_score"] = score_p1_frame(scored)
            metrics = summarize_rank_performance(scored, top_n=3)
            results.append(
                {
                    "window": index + 1,
                    "train_start": train_dates[0],
                    "train_end": train_dates[-1],
                    "test_start": test_dates[0],
                    "test_end": test_dates[-1],
                    **metrics,
                }
            )
    summary = {
        "generated_at": pd.Timestamp.utcnow().isoformat(),
        "backend": args.backend,
        "window_count": len(results),
        "results": results,
        "average_sharpe": round(float(pd.Series([item["sharpe"] for item in results]).mean() if results else 0.0), 6),
        "average_mean_return_5d": round(float(pd.Series([item["mean_return_5d"] for item in results]).mean() if results else 0.0), 6),
    }
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "walk_forward.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
