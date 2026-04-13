from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "training" / "p0_assets"

P0_MODELS = [
    {
        "role": "llm_base",
        "repo_id": "Qwen/Qwen2.5-7B-Instruct",
        "local_dir": "models/qwen2.5-7b-instruct",
        "note": "Base model for ESG LoRA continuation training.",
        "download_policy": "colab_only",
    },
    {
        "role": "news_classifier_optional",
        "repo_id": "ProsusAI/finbert",
        "local_dir": "models/finbert",
        "note": "Optional finance/news classifier for controversy scoring.",
        "download_policy": "local_optional",
    },
    {
        "role": "news_classifier_alt_optional",
        "repo_id": "microsoft/deberta-v3-base",
        "local_dir": "models/deberta-v3-base",
        "note": "Optional stronger encoder backbone for ESG/news classification fine-tuning.",
        "download_policy": "local_optional",
    },
]


def _count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as handle:
        return sum(1 for _ in handle)


def _build_dataset_manifest() -> dict[str, object]:
    alpha_dir = PROJECT_ROOT / "data" / "alpha_ranker"
    rag_dir = PROJECT_ROOT / "data" / "rag_training_data"
    return {
        "datasets": [
            {
                "role": "alpha_ranker_tabular",
                "description": "Prepared tabular alpha dataset for LightGBM/XGBoost training.",
                "paths": {
                    "full_dataset": str(alpha_dir / "full_dataset.csv"),
                    "train_csv": str(alpha_dir / "train.csv"),
                    "val_csv": str(alpha_dir / "val.csv"),
                    "manifest": str(alpha_dir / "manifest.json"),
                },
            },
            {
                "role": "esg_lora_chatml",
                "description": "Existing ESG chat-style LoRA continuation corpus.",
                "paths": {
                    "train_jsonl": str(rag_dir / "train.jsonl"),
                    "val_jsonl": str(rag_dir / "val.jsonl"),
                },
                "line_counts": {
                    "train": _count_lines(rag_dir / "train.jsonl"),
                    "val": _count_lines(rag_dir / "val.jsonl"),
                },
            },
        ]
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare P0 model-download manifests and optional hf download commands.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Where to write bootstrap assets.")
    parser.add_argument("--download", action="store_true", help="Run hf download commands when hf CLI is available.")
    parser.add_argument(
        "--download-local-only",
        action="store_true",
        help="Only download models marked as local_optional, leaving large base models for Colab.",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    dataset_manifest = _build_dataset_manifest()
    manifest = {
        "models": P0_MODELS,
        **dataset_manifest,
        "colab_commands": [
            "pip install -r training/requirements.txt",
            "pip install huggingface_hub hf-transfer",
            "python training/prepare_alpha_data.py",
            "python training/train_alpha_ranker.py --backend xgboost",
        ],
    }
    (output_dir / "p0_model_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "p0_dataset_manifest.json").write_text(
        json.dumps(dataset_manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    bootstrap_lines = ["#!/usr/bin/env bash", "set -euo pipefail", "pip install -r training/requirements.txt", "pip install huggingface_hub hf-transfer"]
    for model in P0_MODELS:
        bootstrap_lines.append(f"hf download {model['repo_id']} --local-dir /content/{model['local_dir']}")
    (output_dir / "colab_download_p0_assets.sh").write_text("\n".join(bootstrap_lines) + "\n", encoding="utf-8")

    if args.download:
        for model in P0_MODELS:
            if args.download_local_only and model.get("download_policy") != "local_optional":
                continue
            local_dir = output_dir / model["local_dir"]
            local_dir.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                ["hf", "download", model["repo_id"], "--local-dir", str(local_dir)],
                cwd=PROJECT_ROOT,
                check=False,
            )

    print(json.dumps({"output_dir": str(output_dir), **manifest}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
