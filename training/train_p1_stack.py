from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from training.p1_training_lib import fit_and_persist_suite, load_frame

DEFAULT_DATA_DIR = PROJECT_ROOT / "data" / "p1_stack"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "model-serving" / "checkpoint" / "p1_suite"


def main() -> int:
    parser = argparse.ArgumentParser(description="Train the P1 multi-model alpha + risk stack.")
    parser.add_argument("--train-csv", default=str(DEFAULT_DATA_DIR / "train.csv"), help="Training csv path.")
    parser.add_argument("--val-csv", default=str(DEFAULT_DATA_DIR / "val.csv"), help="Validation csv path.")
    parser.add_argument("--backend", default="auto", choices=["auto", "xgboost", "lightgbm", "catboost", "sklearn_gbdt"], help="Preferred backend.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Checkpoint suite output directory.")
    args = parser.parse_args()

    train = load_frame(args.train_csv)
    val = load_frame(args.val_csv)
    manifest = fit_and_persist_suite(train=train, val=val, output_dir=args.output_dir, backend=args.backend)
    print(json.dumps({"output_dir": str(Path(args.output_dir)), **manifest}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
