from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "training" / "cloud_assets"
DEFAULT_HF_ENDPOINT = "https://hf-mirror.com"


OPTIONAL_PUBLIC_DOWNLOADS = [
    {
        "repo_id": "ProsusAI/finbert",
        "local_dir": "models/finbert",
        "include": ["config.json", "tokenizer*", "vocab.txt", "special_tokens_map.json", "*.bin", "*.safetensors"],
    },
    {
        "repo_id": "microsoft/deberta-v3-base",
        "local_dir": "models/deberta-v3-base",
        "include": ["config.json", "tokenizer*", "spm.model", "*.bin", "*.safetensors"],
    },
    {
        "repo_id": "BAAI/bge-m3",
        "local_dir": "models/bge-m3",
        "include": ["config.json", "tokenizer*", "sentencepiece*", "modules.json", "*.json", "*.bin", "*.safetensors", "1_Pooling/*"],
    },
    {
        "repo_id": "Alibaba-NLP/gte-Qwen2-1.5B-instruct",
        "local_dir": "models/gte-qwen2-1.5b-instruct",
        "include": ["config.json", "tokenizer*", "*.json", "*.model", "*.bin", "*.safetensors"],
    },
]


def _shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def _existing(relative_path: str) -> bool:
    return (PROJECT_ROOT / relative_path).exists()


def _existing_paths(paths: list[str]) -> list[str]:
    return [path for path in paths if _existing(path)]


def _build_manifest() -> dict[str, object]:
    tracks = {
        "qwen_esg_lora_v2": {
            "role": "deployable_llm_adapter",
            "checkpoint_dir": "model-serving/checkpoint",
            "base_models": ["Qwen/Qwen2.5-7B-Instruct"],
            "datasets": _existing_paths(["data/rag_training_data/train.jsonl", "data/rag_training_data/val.jsonl"]),
            "scripts": _existing_paths(["training/finetune.py"]),
            "cloud_command": [
                "python",
                "training/finetune.py",
                "--num_train_epochs",
                "3",
                "--max_length",
                "1536",
                "--per_device_train_batch_size",
                "6",
                "--per_device_eval_batch_size",
                "6",
                "--gradient_accumulation_steps",
                "4",
                "--gradient_checkpointing",
                "--precision",
                "auto",
            ],
        },
        "alpha_ranker": {
            "role": "deployable_tabular_regressor",
            "checkpoint_dir": "model-serving/checkpoint/alpha_ranker",
            "datasets": _existing_paths(
                [
                    "data/alpha_ranker/full_dataset.csv",
                    "data/alpha_ranker/train.csv",
                    "data/alpha_ranker/val.csv",
                ]
            ),
            "scripts": _existing_paths(
                [
                    "training/prepare_alpha_data.py",
                    "training/train_alpha_ranker.py",
                    "training/evaluate_alpha_ranker.py",
                ]
            ),
            "cloud_command": ["python", "training/train_alpha_ranker.py", "--backend", "auto"],
        },
        "p1_risk_stack": {
            "role": "deployable_tabular_suite",
            "checkpoint_dir": "model-serving/checkpoint/p1_suite",
            "datasets": _existing_paths(
                [
                    "data/p1_stack/full_dataset.csv",
                    "data/p1_stack/train.csv",
                    "data/p1_stack/val.csv",
                ]
            ),
            "scripts": _existing_paths(
                [
                    "training/prepare_p1_data.py",
                    "training/train_p1_stack.py",
                    "training/evaluate_p1_stack.py",
                    "training/run_p1_walk_forward.py",
                ]
            ),
            "cloud_command": ["python", "training/train_p1_stack.py", "--backend", "auto"],
        },
        "sequence_forecaster_full": {
            "role": "deployable_multi_target_sequence_suite",
            "checkpoint_dir": "model-serving/checkpoint/sequence_forecaster",
            "targets": [
                "forward_return_1d",
                "forward_return_5d",
                "future_volatility_10d",
                "future_max_drawdown_20d",
            ],
            "architecture": "lstm",
            "datasets": _existing_paths(
                [
                    "data/p1_stack/full_dataset.csv",
                    "data/p1_stack/train.csv",
                    "data/p1_stack/val.csv",
                ]
            ),
            "scripts": _existing_paths(["training/train_sequence_forecaster.py"]),
            "cloud_command": [
                "python",
                "training/train_sequence_forecaster.py",
                "--train-all-targets",
                "--architecture",
                "lstm",
                "--epochs",
                "8",
                "--hidden-size",
                "256",
                "--batch-size",
                "256",
            ],
        },
        "event_classifier_full": {
            "role": "deployable_multi_head_text_suite",
            "checkpoint_dir": "model-serving/checkpoint/event_classifier",
            "tasks": [
                {"task": "controversy_label", "model_name": "ProsusAI/finbert"},
                {"task": "sentiment_label", "model_name": "ProsusAI/finbert"},
                {"task": "esg_axis_label", "model_name": "microsoft/deberta-v3-base"},
                {"task": "impact_direction", "model_name": "microsoft/deberta-v3-base"},
                {"task": "regime_label", "model_name": "microsoft/deberta-v3-base"},
            ],
            "datasets": _existing_paths(
                [
                    "data/event_classifier/full_dataset.csv",
                    "data/event_classifier/train.csv",
                    "data/event_classifier/val.csv",
                    "data/event_classifier/manifest.json",
                ]
            ),
            "scripts": _existing_paths(
                [
                    "training/prepare_event_classifier_data.py",
                    "training/train_event_classifier.py",
                    "training/train_event_classifier_suite.py",
                    "training/evaluate_event_classifier.py",
                ]
            ),
            "cloud_command": [
                "python",
                "training/train_event_classifier_suite.py",
                "--num-train-epochs",
                "4",
                "--per-device-train-batch-size",
                "32",
                "--per-device-eval-batch-size",
                "64",
                "--learning-rate",
                "2e-5",
            ],
        },
        "p2_selector": {
            "role": "deployable_strategy_selector_suite",
            "checkpoint_dir": "model-serving/checkpoint/p2_selector",
            "datasets": _existing_paths(
                [
                    "data/p2_stack/full_signal_dataset.csv",
                    "data/p2_stack/full_snapshot_dataset.csv",
                    "data/p2_stack/train_signals.csv",
                    "data/p2_stack/val_signals.csv",
                    "data/p2_stack/train_snapshots.csv",
                    "data/p2_stack/val_snapshots.csv",
                ]
            ),
            "scripts": _existing_paths(
                [
                    "training/prepare_p2_data.py",
                    "training/train_p2_selector.py",
                    "training/evaluate_p2_selector.py",
                ]
            ),
            "cloud_command": ["python", "training/train_p2_selector.py", "--backend", "auto"],
        },
        "contextual_bandit": {
            "role": "deployable_bandit_router",
            "checkpoint_dir": "model-serving/checkpoint/contextual_bandit",
            "datasets": _existing_paths(
                [
                    "data/advanced_decision/bandit_contexts.csv",
                    "data/advanced_decision/bandit_contexts_train.csv",
                    "data/advanced_decision/bandit_contexts_val.csv",
                ]
            ),
            "scripts": _existing_paths(
                [
                    "training/prepare_advanced_decision_data.py",
                    "training/train_contextual_bandit.py",
                ]
            ),
            "cloud_command": ["python", "training/train_contextual_bandit.py"],
        },
        "gnn_graph": {
            "role": "deployable_optional_graph_refiner",
            "checkpoint_dir": "model-serving/checkpoint/gnn_graph",
            "datasets": _existing_paths(
                [
                    "data/advanced_decision/graph_nodes.csv",
                    "data/advanced_decision/graph_nodes_train.csv",
                    "data/advanced_decision/graph_nodes_val.csv",
                    "data/advanced_decision/graph_edges.csv",
                ]
            ),
            "scripts": _existing_paths(["training/train_gnn_graph.py"]),
            "cloud_command": [
                "python",
                "training/train_gnn_graph.py",
                "--epochs",
                "60",
                "--batch-size",
                "1024",
                "--hidden-size",
                "128",
            ],
        },
        "ppo_policy": {
            "role": "research_policy_checkpoint",
            "checkpoint_dir": "model-serving/checkpoint/ppo_policy",
            "datasets": _existing_paths(
                [
                    "data/advanced_decision/bandit_contexts_train.csv",
                    "data/advanced_decision/bandit_contexts_val.csv",
                    "data/advanced_decision/ppo_episodes.jsonl",
                ]
            ),
            "scripts": _existing_paths(["training/train_ppo_policy.py"]),
            "cloud_command": [
                "python",
                "training/train_ppo_policy.py",
                "--total-timesteps",
                "20000",
                "--n-steps",
                "512",
                "--batch-size",
                "512",
            ],
        },
        "retrieval_backbones": {
            "role": "download_only_public_backbones",
            "base_models": ["BAAI/bge-m3", "Alibaba-NLP/gte-Qwen2-1.5B-instruct"],
            "datasets": [],
            "scripts": [],
        },
    }
    return {
        "generated_at": Path(__file__).stat().st_mtime_ns,
        "upload_groups": {
            "required_dirs": [
                "training",
                "data/alpha_ranker",
                "data/p1_stack",
                "data/p2_stack",
                "data/event_classifier",
                "data/advanced_decision",
                "data/rag_training_data",
                "gateway",
            ],
            "optional_dirs": [
                "training/p0_assets/models/finbert",
                "training/p0_assets/models/deberta-v3-base",
            ],
        },
        "tracks": tracks,
        "notes": [
            "This manifest is aligned to full cloud training, not only the partially completed local checkpoints.",
            "The production-critical runtime checkpoints are LoRA, alpha_ranker, p1_suite, sequence_forecaster, event_classifier, p2_selector, contextual_bandit, and optionally gnn_graph.",
            "PPO remains a research policy artifact until you choose to wire it into the runtime.",
            "Large public base models are better downloaded directly on the 5090 cloud machine.",
        ],
    }


def _write_helpers(output_dir: Path) -> None:
    helper_dir = output_dir / "scripts"
    helper_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "requirements_cloud_extra.txt").write_text(
        "\n".join(
            [
                "huggingface_hub[cli]>=0.23.0",
                "networkx>=3.3",
                "sentence-transformers>=3.0.0",
                "gymnasium>=0.29.1",
                "stable-baselines3>=2.3.2",
                "tensorboard>=2.16.2",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    download_lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        f"export HF_ENDPOINT=\"${{HF_ENDPOINT:-{DEFAULT_HF_ENDPOINT}}}\"",
        "export HF_HOME=\"${HF_HOME:-$PWD/.cache/huggingface}\"",
        "export HUGGINGFACE_HUB_CACHE=\"${HUGGINGFACE_HUB_CACHE:-$HF_HOME/hub}\"",
        "export TRANSFORMERS_CACHE=\"${TRANSFORMERS_CACHE:-$HF_HOME/transformers}\"",
        "mkdir -p \"$HF_HOME\" \"$HUGGINGFACE_HUB_CACHE\" \"$TRANSFORMERS_CACHE\" \"$PWD/models\"",
        "pip install -U pip",
        "pip install -r training/requirements.txt",
        "pip install -r training/cloud_assets/requirements_cloud_extra.txt || true",
        "python training/download_all_training_assets.py",
    ]
    for item in OPTIONAL_PUBLIC_DOWNLOADS:
        include_args = " ".join(f"--include {_shell_quote(pattern)}" for pattern in item["include"])
        download_lines.append(
            f'hf download {item["repo_id"]} --local-dir "${{PWD}}/{item["local_dir"]}" {include_args}'
        )
    (helper_dir / "download_public_models.sh").write_text("\n".join(download_lines) + "\n", encoding="utf-8")

    scripts = {
        "run_sequence_full_suite.sh": [
            "python training/train_sequence_forecaster.py --train-all-targets --architecture lstm --epochs 8 --hidden-size 256 --batch-size 256",
        ],
        "run_event_classifier_full_suite.sh": [
            "python training/train_event_classifier_suite.py --num-train-epochs 4 --per-device-train-batch-size 32 --per-device-eval-batch-size 64 --learning-rate 2e-5",
        ],
        "run_gnn_graph_pipeline.sh": [
            "python training/train_gnn_graph.py --epochs 60 --batch-size 1024 --hidden-size 128",
        ],
        "run_ppo_policy_pipeline.sh": [
            "python training/train_ppo_policy.py --total-timesteps 20000 --n-steps 512 --batch-size 512",
        ],
        "run_full_5090_training.sh": [
            "python training/train_full_model_suite.py",
        ],
    }
    for filename, commands in scripts.items():
        payload = (
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            f"export HF_ENDPOINT=\"${{HF_ENDPOINT:-{DEFAULT_HF_ENDPOINT}}}\"\n"
            "export HF_HOME=\"${HF_HOME:-$PWD/.cache/huggingface}\"\n"
            "export HUGGINGFACE_HUB_CACHE=\"${HUGGINGFACE_HUB_CACHE:-$HF_HOME/hub}\"\n"
            "export TRANSFORMERS_CACHE=\"${TRANSFORMERS_CACHE:-$HF_HOME/transformers}\"\n"
            "mkdir -p \"$HF_HOME\" \"$HUGGINGFACE_HUB_CACHE\" \"$TRANSFORMERS_CACHE\"\n"
            + "\n".join(commands)
            + "\n"
        )
        (helper_dir / filename).write_text(payload, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a full cloud-training manifest for all deployable model assets.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory for manifests and helper scripts.")
    parser.add_argument(
        "--download-public-models",
        action="store_true",
        help="Optionally download public encoder/classifier models into the output directory.",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = _build_manifest()
    (output_dir / "master_training_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _write_helpers(output_dir)

    if args.download_public_models:
        models_dir = output_dir / "models"
        models_dir.mkdir(parents=True, exist_ok=True)
        for item in OPTIONAL_PUBLIC_DOWNLOADS:
            local_dir = models_dir / Path(item["local_dir"]).name
            command = ["hf", "download", item["repo_id"], "--local-dir", str(local_dir)]
            for pattern in item["include"]:
                command.extend(["--include", pattern])
            subprocess.run(command, cwd=PROJECT_ROOT, check=False)

    print(json.dumps({"output_dir": str(output_dir), **manifest}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
