from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import joblib
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from training.train_alpha_ranker import FEATURE_COLUMNS, evaluate_model, infer_objective

DEFAULT_DATA_DIR = PROJECT_ROOT / "data" / "alpha_ranker"
DEFAULT_CKPT_DIR = PROJECT_ROOT / "model-serving" / "checkpoint" / "alpha_ranker"


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate a trained alpha ranker checkpoint on validation data.")
    parser.add_argument("--checkpoint-dir", default=str(DEFAULT_CKPT_DIR), help="Checkpoint directory containing model.joblib.")
    parser.add_argument("--val-csv", default=str(DEFAULT_DATA_DIR / "val.csv"), help="Validation csv path.")
    parser.add_argument("--target-column", default="forward_return_5d", help="Target column to evaluate.")
    args = parser.parse_args()

    checkpoint_dir = Path(args.checkpoint_dir)
    model = joblib.load(checkpoint_dir / "model.joblib")
    val = pd.read_csv(args.val_csv)
    objective = infer_objective(args.target_column)
    metrics, predictions = evaluate_model(model, objective, val[FEATURE_COLUMNS].fillna(0.0), val[args.target_column])
    payload = {
        "checkpoint_dir": str(checkpoint_dir),
        "target_column": args.target_column,
        "objective": objective,
        "metrics": metrics,
        "prediction_preview": predictions[:10],
    }
    (checkpoint_dir / "evaluation.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
