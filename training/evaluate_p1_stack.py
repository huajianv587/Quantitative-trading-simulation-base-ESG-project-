from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from training.p1_training_lib import load_frame, predict_suite, score_p1_frame, summarize_rank_performance

DEFAULT_DATA_DIR = PROJECT_ROOT / "data" / "p1_stack"
DEFAULT_CKPT_DIR = PROJECT_ROOT / "model-serving" / "checkpoint" / "p1_suite"


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate the P1 model suite on validation data.")
    parser.add_argument("--checkpoint-dir", default=str(DEFAULT_CKPT_DIR), help="P1 suite checkpoint directory.")
    parser.add_argument("--val-csv", default=str(DEFAULT_DATA_DIR / "val.csv"), help="Validation csv path.")
    args = parser.parse_args()

    val = load_frame(args.val_csv).rename(columns={"regime_label": "target_regime_label"})
    predictions = predict_suite(args.checkpoint_dir, val.rename(columns={"target_regime_label": "regime_label"}))
    scored = pd.concat([val.reset_index(drop=True), predictions.reset_index(drop=True)], axis=1)
    scored["p1_stack_score"] = score_p1_frame(scored)
    p1_metrics = summarize_rank_performance(scored, top_n=3)
    baseline = scored.copy()
    baseline["p1_stack_score"] = baseline["alpha_baseline"]
    baseline_metrics = summarize_rank_performance(baseline, top_n=3)
    payload = {
        "checkpoint_dir": str(Path(args.checkpoint_dir)),
        "rows": int(len(scored)),
        "p1_rank_performance": p1_metrics,
        "baseline_rank_performance": baseline_metrics,
        "preview": scored[
            [
                "date",
                "symbol",
                "forward_return_5d",
                "predicted_return_1d",
                "predicted_return_5d",
                "predicted_volatility_10d",
                "predicted_drawdown_20d",
                "target_regime_label",
                "regime_label",
                "regime_probability",
                "p1_stack_score",
            ]
        ].head(12).to_dict(orient="records"),
    }
    checkpoint_dir = Path(args.checkpoint_dir)
    (checkpoint_dir / "evaluation.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
