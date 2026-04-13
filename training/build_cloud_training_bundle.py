from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "delivery" / "cloud_training_bundle"

BUNDLE_FILES = [
    "training/requirements.txt",
    "training/finetune.py",
    "training/download_p0_assets.py",
    "training/download_p1_assets.py",
    "training/download_p2_assets.py",
    "training/prepare_alpha_data.py",
    "training/train_alpha_ranker.py",
    "training/evaluate_alpha_ranker.py",
    "training/prepare_p1_data.py",
    "training/p1_training_lib.py",
    "training/train_p1_stack.py",
    "training/evaluate_p1_stack.py",
    "training/run_p1_walk_forward.py",
    "training/train_sequence_forecaster.py",
    "training/prepare_event_classifier_data.py",
    "training/train_event_classifier.py",
    "training/train_event_classifier_suite.py",
    "training/evaluate_event_classifier.py",
    "training/prepare_p2_data.py",
    "training/p2_training_lib.py",
    "training/train_p2_selector.py",
    "training/evaluate_p2_selector.py",
    "training/prepare_advanced_decision_data.py",
    "training/train_contextual_bandit.py",
    "training/train_gnn_graph.py",
    "training/train_ppo_policy.py",
    "training/train_full_model_suite.py",
    "training/download_all_training_assets.py",
    "docs/P0_ALPHA_RANKER_COLAB_ZH.md",
    "docs/P1_STACK_DELIVERY_ZH.md",
    "docs/P2_DECISION_DELIVERY_ZH.md",
    "docs/CLOUD_TRAINING_ASSETS_ZH.md",
]

BUNDLE_DIRS = [
    "gateway",
    "data/alpha_ranker",
    "data/p1_stack",
    "data/p2_stack",
    "data/rag_training_data",
    "data/event_classifier",
    "data/advanced_decision",
    "training/cloud_assets",
]

OPTIONAL_DIRS = [
    "training/p0_assets/models/finbert",
    "training/p0_assets/models/deberta-v3-base",
]


def _copy_path(relative_path: str, target_root: Path) -> None:
    source = PROJECT_ROOT / relative_path
    if not source.exists():
        return
    destination = target_root / relative_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(
            source,
            destination,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".cache"),
        )
        return
    shutil.copy2(source, destination)


def main() -> int:
    parser = argparse.ArgumentParser(description="Assemble a copyable cloud-training bundle.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Bundle output directory.")
    parser.add_argument("--include-local-models", action="store_true", help="Include locally downloaded FinBERT / DeBERTa backbones.")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    copied_files: list[str] = []
    copied_dirs: list[str] = []
    for relative_path in BUNDLE_FILES:
        _copy_path(relative_path, output_dir)
        if (PROJECT_ROOT / relative_path).exists():
            copied_files.append(relative_path)
    for relative_path in BUNDLE_DIRS:
        _copy_path(relative_path, output_dir)
        if (PROJECT_ROOT / relative_path).exists():
            copied_dirs.append(relative_path)
    if args.include_local_models:
        for relative_path in OPTIONAL_DIRS:
            _copy_path(relative_path, output_dir)
            if (PROJECT_ROOT / relative_path).exists():
                copied_dirs.append(relative_path)

    readme = output_dir / "README.md"
    readme.write_text(
        "\n".join(
            [
                "# ESG Quant Cloud Training Bundle",
                "",
                "This bundle contains the prepared datasets, training scripts, and manifests required to continue training on a remote GPU machine.",
                "",
                "Recommended order:",
                "1. Qwen ESG LoRA v2",
                "2. Alpha ranker",
                "3. P1 risk stack + sequence forecaster",
                "4. Event classifier full suite",
                "5. P2 selector + contextual bandit",
                "6. Optional GNN graph refiner",
                "7. PPO research policy",
                "",
                "Start from `training/cloud_assets/master_training_manifest.json` and `training/cloud_assets/scripts/`.",
                "For a one-command 5090 launch, run `python training/train_full_model_suite.py`.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    manifest = {
        "generated_at": Path(__file__).stat().st_mtime_ns,
        "bundle_root": str(output_dir),
        "copied_files": copied_files,
        "copied_dirs": copied_dirs,
        "include_local_models": bool(args.include_local_models),
    }
    (output_dir / "bundle_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
