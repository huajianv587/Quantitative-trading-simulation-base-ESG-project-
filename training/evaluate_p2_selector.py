from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from training.p2_training_lib import load_frame


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate the P2 selector suite from persisted metadata.")
    parser.add_argument("--checkpoint-dir", default=str(PROJECT_ROOT / "model-serving" / "checkpoint" / "p2_selector"))
    parser.add_argument("--val-snapshots", default=str(PROJECT_ROOT / "data" / "p2_stack" / "val_snapshots.csv"))
    parser.add_argument("--val-signals", default=str(PROJECT_ROOT / "data" / "p2_stack" / "val_signals.csv"))
    args = parser.parse_args()

    root = Path(args.checkpoint_dir)
    snapshot_rows = len(load_frame(args.val_snapshots))
    signal_rows = len(load_frame(args.val_signals))
    manifest_path = root / "suite_manifest.json"
    if not manifest_path.exists():
        raise SystemExit("suite_manifest.json not found in checkpoint dir")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload = {
        "checkpoint_dir": str(root),
        "validation_rows": {
            "snapshots": snapshot_rows,
            "signals": signal_rows,
        },
        "manifest": manifest,
        "models": [],
    }
    for model_item in manifest.get("models", []):
        metadata_path = root / model_item["key"] / "metadata.json"
        if metadata_path.exists():
            payload["models"].append(json.loads(metadata_path.read_text(encoding="utf-8")))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
