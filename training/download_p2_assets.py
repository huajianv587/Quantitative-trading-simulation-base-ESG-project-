from __future__ import annotations

import argparse
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "training" / "p2_assets"

RECOMMENDED_ASSETS = {
    "graph": [
        {"artifact": "relationship-graph snapshots", "role": "company/event topology"},
        {"artifact": "sector peer maps", "role": "cluster concentration monitoring"},
    ],
    "tabular": [
        {"backend": "xgboost", "role": "priority regressor"},
        {"backend": "lightgbm", "role": "strategy classifier"},
        {"backend": "catboost", "role": "fallback ensemble"},
    ],
    "text": [
        {"model_id": "ProsusAI/finbert", "role": "news controversy features"},
        {"model_id": "BAAI/bge-m3", "role": "event and graph retrieval backbone"},
    ],
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare manifests and helper scripts for P2 model assets.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory for manifests.")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": Path(__file__).stat().st_mtime_ns,
        "recommended_assets": RECOMMENDED_ASSETS,
        "notes": [
            "Use training/prepare_p2_data.py to build graph-aware selector datasets.",
            "Use training/train_p2_selector.py to fit the strategy classifier and priority regressor.",
            "Pair P2 with stronger P1 checkpoints for better regime and return estimates.",
        ],
    }
    (output_dir / "p2_asset_manifest.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    helper = "\n".join(
        [
            "#!/usr/bin/env bash",
            "set -euo pipefail",
            "python training/prepare_p2_data.py",
            "python training/train_p2_selector.py --backend xgboost",
            "python training/evaluate_p2_selector.py",
        ]
    )
    (output_dir / "run_p2_pipeline.sh").write_text(helper, encoding="utf-8")
    print(json.dumps({"output_dir": str(output_dir), **payload}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
