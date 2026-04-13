from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST_PATH = PROJECT_ROOT / "training" / "full_training_run_manifest.json"
DEFAULT_HF_ENDPOINT = "https://hf-mirror.com"


def _run_step(step_name: str, command: list[str], *, dry_run: bool, manifest: dict[str, object]) -> None:
    payload = {
        "step": step_name,
        "command": command,
        "status": "dry_run" if dry_run else "completed",
    }
    manifest.setdefault("steps", []).append(payload)
    if dry_run:
        print("[Dry Run]", step_name, "->", " ".join(command))
        return
    subprocess.run(command, cwd=PROJECT_ROOT, check=True)


def _selected_jobs(raw: str) -> list[str]:
    if not raw.strip():
        return [
            "lora",
            "alpha",
            "p1",
            "sequence",
            "event",
            "p2",
            "bandit",
            "gnn",
            "ppo",
        ]
    return [item.strip() for item in raw.split(",") if item.strip()]


def main() -> int:
    os.environ.setdefault("HF_ENDPOINT", DEFAULT_HF_ENDPOINT)
    hf_home = Path(os.environ.setdefault("HF_HOME", str(PROJECT_ROOT / ".cache" / "huggingface")))
    os.environ.setdefault("HUGGINGFACE_HUB_CACHE", str(hf_home / "hub"))
    os.environ.setdefault("TRANSFORMERS_CACHE", str(hf_home / "transformers"))
    hf_home.mkdir(parents=True, exist_ok=True)

    parser = argparse.ArgumentParser(description="Run the full cloud model-training suite sequentially.")
    parser.add_argument("--jobs", default="", help="Comma-separated subset of jobs.")
    parser.add_argument("--prepare-data", action="store_true", help="Rebuild prepared datasets before training.")
    parser.add_argument("--manifest-path", default=str(DEFAULT_MANIFEST_PATH), help="Where to write the run manifest.")
    parser.add_argument("--dry-run", action="store_true", help="Print commands without executing them.")

    parser.add_argument("--lora-epochs", type=int, default=3)
    parser.add_argument("--lora-max-length", type=int, default=1536)
    parser.add_argument("--lora-train-batch-size", type=int, default=6)
    parser.add_argument("--lora-eval-batch-size", type=int, default=6)
    parser.add_argument("--lora-gradient-accumulation", type=int, default=4)
    parser.add_argument("--lora-learning-rate", type=float, default=2e-4)

    parser.add_argument("--sequence-architecture", choices=["lstm", "tcn"], default="lstm")
    parser.add_argument("--sequence-epochs", type=int, default=8)
    parser.add_argument("--sequence-hidden-size", type=int, default=256)
    parser.add_argument("--sequence-batch-size", type=int, default=256)

    parser.add_argument("--event-epochs", type=int, default=4)
    parser.add_argument("--event-max-length", type=int, default=256)
    parser.add_argument("--event-train-batch-size", type=int, default=32)
    parser.add_argument("--event-eval-batch-size", type=int, default=64)
    parser.add_argument("--event-learning-rate", type=float, default=2e-5)

    parser.add_argument("--gnn-epochs", type=int, default=60)
    parser.add_argument("--gnn-batch-size", type=int, default=1024)
    parser.add_argument("--gnn-hidden-size", type=int, default=128)

    parser.add_argument("--ppo-total-timesteps", type=int, default=20000)
    parser.add_argument("--ppo-n-steps", type=int, default=512)
    parser.add_argument("--ppo-batch-size", type=int, default=512)
    args = parser.parse_args()

    jobs = _selected_jobs(args.jobs)
    manifest: dict[str, object] = {
        "generated_at": None,
        "project_root": str(PROJECT_ROOT),
        "jobs": jobs,
        "prepare_data": bool(args.prepare_data),
        "dry_run": bool(args.dry_run),
        "steps": [],
    }

    if args.prepare_data:
        prepare_steps = [
            ("prepare_alpha_data", [sys.executable, "training/prepare_alpha_data.py"]),
            ("prepare_p1_data", [sys.executable, "training/prepare_p1_data.py"]),
            ("prepare_event_classifier_data", [sys.executable, "training/prepare_event_classifier_data.py"]),
            ("prepare_p2_data", [sys.executable, "training/prepare_p2_data.py"]),
            ("prepare_advanced_decision_data", [sys.executable, "training/prepare_advanced_decision_data.py"]),
        ]
        for step_name, command in prepare_steps:
            _run_step(step_name, command, dry_run=args.dry_run, manifest=manifest)

    job_steps: list[tuple[str, list[str]]] = []
    if "lora" in jobs:
        job_steps.append(
            (
                "train_qwen_esg_lora",
                [
                    sys.executable,
                    "training/finetune.py",
                    "--num_train_epochs",
                    str(args.lora_epochs),
                    "--max_length",
                    str(args.lora_max_length),
                    "--per_device_train_batch_size",
                    str(args.lora_train_batch_size),
                    "--per_device_eval_batch_size",
                    str(args.lora_eval_batch_size),
                    "--gradient_accumulation_steps",
                    str(args.lora_gradient_accumulation),
                    "--learning_rate",
                    str(args.lora_learning_rate),
                    "--precision",
                    "auto",
                    "--gradient_checkpointing",
                ],
            )
        )
    if "alpha" in jobs:
        job_steps.extend(
            [
                ("train_alpha_ranker", [sys.executable, "training/train_alpha_ranker.py", "--backend", "auto"]),
                ("evaluate_alpha_ranker", [sys.executable, "training/evaluate_alpha_ranker.py"]),
            ]
        )
    if "p1" in jobs:
        job_steps.extend(
            [
                ("train_p1_suite", [sys.executable, "training/train_p1_stack.py", "--backend", "auto"]),
                ("evaluate_p1_suite", [sys.executable, "training/evaluate_p1_stack.py"]),
                ("run_p1_walk_forward", [sys.executable, "training/run_p1_walk_forward.py"]),
            ]
        )
    if "sequence" in jobs:
        job_steps.append(
            (
                "train_sequence_forecaster_full",
                [
                    sys.executable,
                    "training/train_sequence_forecaster.py",
                    "--train-all-targets",
                    "--architecture",
                    args.sequence_architecture,
                    "--epochs",
                    str(args.sequence_epochs),
                    "--hidden-size",
                    str(args.sequence_hidden_size),
                    "--batch-size",
                    str(args.sequence_batch_size),
                ],
            )
        )
    if "event" in jobs:
        job_steps.append(
            (
                "train_event_classifier_full_suite",
                [
                    sys.executable,
                    "training/train_event_classifier_suite.py",
                    "--num-train-epochs",
                    str(args.event_epochs),
                    "--max-length",
                    str(args.event_max_length),
                    "--per-device-train-batch-size",
                    str(args.event_train_batch_size),
                    "--per-device-eval-batch-size",
                    str(args.event_eval_batch_size),
                    "--learning-rate",
                    str(args.event_learning_rate),
                ],
            )
        )
    if "p2" in jobs:
        job_steps.extend(
            [
                ("train_p2_selector", [sys.executable, "training/train_p2_selector.py", "--backend", "auto"]),
                ("evaluate_p2_selector", [sys.executable, "training/evaluate_p2_selector.py"]),
            ]
        )
    if "bandit" in jobs:
        job_steps.append(("train_contextual_bandit", [sys.executable, "training/train_contextual_bandit.py"]))
    if "gnn" in jobs:
        job_steps.append(
            (
                "train_gnn_graph",
                [
                    sys.executable,
                    "training/train_gnn_graph.py",
                    "--epochs",
                    str(args.gnn_epochs),
                    "--batch-size",
                    str(args.gnn_batch_size),
                    "--hidden-size",
                    str(args.gnn_hidden_size),
                ],
            )
        )
    if "ppo" in jobs:
        job_steps.append(
            (
                "train_ppo_policy",
                [
                    sys.executable,
                    "training/train_ppo_policy.py",
                    "--total-timesteps",
                    str(args.ppo_total_timesteps),
                    "--n-steps",
                    str(args.ppo_n_steps),
                    "--batch-size",
                    str(args.ppo_batch_size),
                ],
            )
        )

    for step_name, command in job_steps:
        _run_step(step_name, command, dry_run=args.dry_run, manifest=manifest)

    manifest["generated_at"] = (
        "dry-run" if args.dry_run else datetime.now(timezone.utc).isoformat()
    )
    manifest_path = Path(args.manifest_path)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
