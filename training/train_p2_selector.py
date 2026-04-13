from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from training.p2_training_lib import fit_and_persist_suite, load_frame

DEFAULT_DATA_DIR = PROJECT_ROOT / "data" / "p2_stack"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "model-serving" / "checkpoint" / "p2_selector"


def main() -> int:
    parser = argparse.ArgumentParser(description="Train the P2 graph + strategy selector suite.")
    parser.add_argument("--train-snapshots", default=str(DEFAULT_DATA_DIR / "train_snapshots.csv"), help="Training snapshot csv path.")
    parser.add_argument("--val-snapshots", default=str(DEFAULT_DATA_DIR / "val_snapshots.csv"), help="Validation snapshot csv path.")
    parser.add_argument("--train-signals", default=str(DEFAULT_DATA_DIR / "train_signals.csv"), help="Training signal csv path.")
    parser.add_argument("--val-signals", default=str(DEFAULT_DATA_DIR / "val_signals.csv"), help="Validation signal csv path.")
    parser.add_argument("--backend", default="auto", choices=["auto", "xgboost", "lightgbm", "catboost", "sklearn_gbdt"], help="Preferred backend.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Checkpoint suite output directory.")
    args = parser.parse_args()

    manifest = fit_and_persist_suite(
        train_snapshots=load_frame(args.train_snapshots),
        val_snapshots=load_frame(args.val_snapshots),
        train_signals=load_frame(args.train_signals),
        val_signals=load_frame(args.val_signals),
        output_dir=args.output_dir,
        backend=args.backend,
    )
    print(json.dumps({"output_dir": str(Path(args.output_dir)), **manifest}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
