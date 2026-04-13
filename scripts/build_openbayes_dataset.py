from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "delivery" / "openbayes" / "esg_quant_p0_training_bundle"

CORE_PATHS = [
    "data/alpha_ranker",
    "data/rag_training_data/train.jsonl",
    "data/rag_training_data/val.jsonl",
    "training/requirements.txt",
    "training/prepare_data.py",
    "training/prepare_alpha_data.py",
    "training/train_alpha_ranker.py",
    "training/evaluate_alpha_ranker.py",
    "training/finetune.py",
    "training/download_p0_assets.py",
    "training/p0_assets/colab_download_p0_assets.sh",
    "training/p0_assets/p0_model_manifest.json",
    "training/p0_assets/p0_dataset_manifest.json",
    "docs/P0_ALPHA_RANKER_COLAB_ZH.md",
    "model-serving/checkpoint/alpha_ranker",
]

OPTIONAL_MODEL_PATHS = [
    "training/p0_assets/models/finbert",
    "training/p0_assets/models/deberta-v3-base",
]


def copy_path(relative_path: str, output_dir: Path) -> dict[str, object]:
    source = PROJECT_ROOT / relative_path
    target = output_dir / relative_path
    if not source.exists():
        return {
            "path": relative_path,
            "exists": False,
            "bytes": 0,
        }

    target.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        shutil.copytree(source, target, dirs_exist_ok=True)
        size = sum(item.stat().st_size for item in target.rglob("*") if item.is_file())
        return {
            "path": relative_path,
            "exists": True,
            "bytes": int(size),
            "type": "directory",
        }

    shutil.copy2(source, target)
    return {
        "path": relative_path,
        "exists": True,
        "bytes": int(target.stat().st_size),
        "type": "file",
    }


def write_readme(output_dir: Path, include_local_models: bool) -> None:
    readme = f"""# ESG Quant P0 OpenBayes Training Bundle

This bundle is prepared for uploading to OpenBayes dataset `HucMvPZuFf0`.

## Included

- `data/alpha_ranker/`: LightGBM/XGBoost alpha ranker tabular dataset
- `data/rag_training_data/`: ESG LoRA chat-style corpus
- `training/*.py`: data prep, alpha training/eval, ESG LoRA training scripts
- `training/p0_assets/*.json|*.sh`: model and dataset manifests
- `model-serving/checkpoint/alpha_ranker/`: current baseline alpha ranker checkpoint
- `docs/P0_ALPHA_RANKER_COLAB_ZH.md`: Chinese training guide

Optional local classifier weights included: `{str(include_local_models).lower()}`

## Suggested next steps on OpenBayes / Colab

1. Train ESG LoRA with `training/finetune.py`
2. Train alpha ranker with `training/train_alpha_ranker.py --backend xgboost`
3. Evaluate with `training/evaluate_alpha_ranker.py`
4. Save new weights back into `model-serving/checkpoint/`

## Upload examples

```bash
bayes login $OPENBAYES_TOKEN
bayes data upload HucMvPZuFf0 --version 1 --path /your/bundle/path
```
"""
    (output_dir / "README_OPENBAYES.md").write_text(readme, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build an OpenBayes-ready training bundle for ESG Quant P0.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Bundle output directory.")
    parser.add_argument("--include-local-models", action="store_true", help="Copy downloaded optional local classifier models into the bundle.")
    parser.add_argument("--clean", action="store_true", help="Delete the existing bundle directory before rebuilding.")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    if args.clean and output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest_items: list[dict[str, object]] = []
    for relative_path in CORE_PATHS:
        manifest_items.append(copy_path(relative_path, output_dir))
    if args.include_local_models:
        for relative_path in OPTIONAL_MODEL_PATHS:
            manifest_items.append(copy_path(relative_path, output_dir))

    write_readme(output_dir, args.include_local_models)
    total_bytes = sum(int(item.get("bytes", 0) or 0) for item in manifest_items)
    file_count = sum(1 for item in output_dir.rglob("*") if item.is_file())
    manifest = {
        "bundle_root": str(output_dir),
        "include_local_models": bool(args.include_local_models),
        "file_count": int(file_count),
        "total_bytes": int(total_bytes),
        "items": manifest_items,
    }
    (output_dir / "bundle_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
