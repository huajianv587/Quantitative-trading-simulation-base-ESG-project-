from __future__ import annotations

import argparse
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "training" / "p1_assets"

RECOMMENDED_MODELS = {
    "embeddings": [
        {"model_id": "BAAI/bge-m3", "role": "retrieval_backbone"},
        {"model_id": "Alibaba-NLP/gte-Qwen2-1.5B-instruct", "role": "retrieval_backbone"},
    ],
    "sentiment": [
        {"model_id": "ProsusAI/finbert", "role": "news_sentiment"},
        {"model_id": "microsoft/deberta-v3-base", "role": "esg_classifier_backbone"},
    ],
    "sequence": [
        {"architecture": "lstm", "role": "return_and_volatility_forecast"},
        {"architecture": "tcn", "role": "return_and_volatility_forecast"},
    ],
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare manifests and helper scripts for P1 model assets.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory for manifests.")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": Path(__file__).stat().st_mtime_ns,
        "recommended_assets": RECOMMENDED_MODELS,
        "notes": [
            "Use BAAI/bge-m3 or Alibaba-NLP/gte-Qwen2-1.5B-instruct for stronger ESG retrieval.",
            "Use FinBERT / DeBERTa for news and controversy classification.",
            "Use training/train_sequence_forecaster.py for GPU sequence-model experiments.",
        ],
    }
    (output_dir / "p1_asset_manifest.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    helper = "\n".join(
        [
            "#!/usr/bin/env bash",
            "set -euo pipefail",
            "python training/prepare_p1_data.py",
            "python training/train_p1_stack.py --backend xgboost",
            "python training/evaluate_p1_stack.py",
            "python training/run_p1_walk_forward.py",
            "python training/train_sequence_forecaster.py --architecture lstm --dry-run",
        ]
    )
    (output_dir / "run_p1_pipeline.sh").write_text(helper, encoding="utf-8")
    print(json.dumps({"output_dir": str(output_dir), **payload}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
