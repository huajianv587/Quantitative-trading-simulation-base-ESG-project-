from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUN_ROOT = PROJECT_ROOT / "storage" / "full-training-runs"
DEFAULT_CHECKPOINT_ROOT = PROJECT_ROOT / "model-serving" / "checkpoint" / "full_suite"
DEFAULT_HF_ENDPOINT = "https://hf-mirror.com"
STAGE1_LABEL = "stage1_baseline_checkpoint"

DEFAULT_JOBS = [
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

CANONICAL_CHECKPOINT_DIRS = {
    "lora": PROJECT_ROOT / "model-serving" / "checkpoint" / "qwen_esg_lora_v2",
    "alpha": PROJECT_ROOT / "model-serving" / "checkpoint" / "alpha_ranker",
    "p1": PROJECT_ROOT / "model-serving" / "checkpoint" / "p1_suite",
    "sequence": PROJECT_ROOT / "model-serving" / "checkpoint" / "sequence_forecaster",
    "event": PROJECT_ROOT / "model-serving" / "checkpoint" / "event_classifier",
    "p2": PROJECT_ROOT / "model-serving" / "checkpoint" / "p2_selector",
    "bandit": PROJECT_ROOT / "model-serving" / "checkpoint" / "contextual_bandit",
    "gnn": PROJECT_ROOT / "model-serving" / "checkpoint" / "gnn_graph",
    "ppo": PROJECT_ROOT / "model-serving" / "checkpoint" / "ppo_policy",
}

TRACK_DIR_NAMES = {
    "lora": "qwen_esg_lora_v2",
    "alpha": "alpha_ranker",
    "p1": "p1_suite",
    "sequence": "sequence_forecaster",
    "event": "event_classifier",
    "p2": "p2_selector",
    "bandit": "contextual_bandit",
    "gnn": "gnn_graph",
    "ppo": "ppo_policy",
}


@dataclass(frozen=True)
class SuiteStep:
    name: str
    job: str
    command: list[str]
    checkpoint_dir: Path | None = None
    stage1_label: str = STAGE1_LABEL


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _git_value(args: list[str]) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _git_snapshot() -> dict[str, Any]:
    return {
        "commit": _git_value(["rev-parse", "HEAD"]),
        "branch": _git_value(["branch", "--show-current"]),
        "status_short": _git_value(["status", "--short"]),
    }


def _gpu_snapshot() -> dict[str, Any]:
    payload: dict[str, Any] = {"torch_available": False, "cuda_available": False}
    try:
        import torch

        payload.update(
            {
                "torch_available": True,
                "torch_version": getattr(torch, "__version__", None),
                "torch_cuda_version": getattr(getattr(torch, "version", None), "cuda", None),
                "cuda_available": bool(torch.cuda.is_available()),
                "cuda_device_count": int(torch.cuda.device_count()) if torch.cuda.is_available() else 0,
            }
        )
        if torch.cuda.is_available():
            payload["cuda_device_name"] = torch.cuda.get_device_name(0)
    except Exception as exc:
        payload["error"] = str(exc)
    return payload


def _environment_snapshot() -> dict[str, Any]:
    return {
        "generated_at": _utc_now(),
        "project_root": str(PROJECT_ROOT),
        "python": sys.version,
        "platform": platform.platform(),
        "executable": sys.executable,
        "git": _git_snapshot(),
        "gpu": _gpu_snapshot(),
        "env": {
            key: os.environ.get(key)
            for key in [
                "CUDA_VISIBLE_DEVICES",
                "HF_ENDPOINT",
                "HF_HOME",
                "TOTAL_STEPS",
                "EPISODES",
                "SMOKE",
                "ALLOW_CPU_SMOKE",
            ]
            if os.environ.get(key) is not None
        },
    }


def _selected_jobs(raw: str) -> list[str]:
    if not raw.strip() or raw.strip().lower() == "all":
        return list(DEFAULT_JOBS)
    jobs = [item.strip().lower() for item in raw.split(",") if item.strip()]
    unknown = sorted(set(jobs) - set(DEFAULT_JOBS))
    if unknown:
        raise SystemExit(f"Unknown full-suite job(s): {', '.join(unknown)}")
    return jobs


def _checkpoint_nonempty(path: Path | None) -> bool:
    if path is None or not path.exists():
        return False
    return any(path.iterdir()) if path.is_dir() else path.stat().st_size > 0


def _status_path(status_dir: Path, step_name: str) -> Path:
    return status_dir / f"{step_name}.json"


def _step_completed(status_dir: Path, step_name: str) -> bool:
    return _read_json(_status_path(status_dir, step_name)).get("status") == "completed"


def _ensure_cuda_policy(*, require_cuda: bool, allow_cpu_smoke: bool, smoke: bool) -> None:
    gpu = _gpu_snapshot()
    if not require_cuda:
        return
    if gpu.get("cuda_available"):
        return
    if smoke and allow_cpu_smoke:
        print("[full-suite][warn] CUDA is not visible; CPU smoke was explicitly allowed.")
        return
    raise SystemExit("[full-suite][fatal] CUDA is not visible. Use --allow-cpu-smoke only with --smoke.")


def _apply_smoke_defaults(args: argparse.Namespace) -> None:
    if not args.smoke:
        return
    args.lora_epochs = min(args.lora_epochs, 1)
    args.lora_max_length = min(args.lora_max_length, 256)
    args.lora_train_batch_size = min(args.lora_train_batch_size, 1)
    args.lora_eval_batch_size = min(args.lora_eval_batch_size, 1)
    args.lora_gradient_accumulation = min(args.lora_gradient_accumulation, 1)
    args.sequence_epochs = min(args.sequence_epochs, 1)
    args.sequence_hidden_size = min(args.sequence_hidden_size, 64)
    args.sequence_batch_size = min(args.sequence_batch_size, 64)
    args.event_epochs = min(args.event_epochs, 1)
    args.event_train_batch_size = min(args.event_train_batch_size, 4)
    args.event_eval_batch_size = min(args.event_eval_batch_size, 8)
    args.gnn_epochs = min(args.gnn_epochs, 1)
    args.gnn_batch_size = min(args.gnn_batch_size, 128)
    args.ppo_total_timesteps = min(args.ppo_total_timesteps, 128)
    args.ppo_n_steps = min(args.ppo_n_steps, 32)
    args.ppo_batch_size = min(args.ppo_batch_size, 32)


def _track_checkpoint(checkpoint_run_root: Path, job: str) -> Path:
    return checkpoint_run_root / TRACK_DIR_NAMES[job]


def _build_prepare_steps() -> list[SuiteStep]:
    return [
        SuiteStep("prepare_alpha_data", "prepare", [sys.executable, "training/prepare_alpha_data.py"]),
        SuiteStep("prepare_p1_data", "prepare", [sys.executable, "training/prepare_p1_data.py"]),
        SuiteStep("prepare_event_classifier_data", "prepare", [sys.executable, "training/prepare_event_classifier_data.py"]),
        SuiteStep("prepare_p2_data", "prepare", [sys.executable, "training/prepare_p2_data.py"]),
        SuiteStep("prepare_advanced_decision_data", "prepare", [sys.executable, "training/prepare_advanced_decision_data.py"]),
    ]


def _build_job_steps(args: argparse.Namespace, jobs: list[str], checkpoint_run_root: Path) -> list[SuiteStep]:
    steps: list[SuiteStep] = []
    if "lora" in jobs:
        ckpt = _track_checkpoint(checkpoint_run_root, "lora")
        steps.append(
            SuiteStep(
                "train_qwen_esg_lora_v2",
                "lora",
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
                    "--output_dir",
                    str(ckpt),
                    "--precision",
                    "auto",
                    "--gradient_checkpointing",
                ],
                ckpt,
            )
        )
    if "alpha" in jobs:
        ckpt = _track_checkpoint(checkpoint_run_root, "alpha")
        steps.extend(
            [
                SuiteStep(
                    "train_alpha_ranker",
                    "alpha",
                    [
                        sys.executable,
                        "training/train_alpha_ranker.py",
                        "--backend",
                        "auto",
                        "--output-dir",
                        str(ckpt),
                    ],
                    ckpt,
                ),
                SuiteStep(
                    "evaluate_alpha_ranker",
                    "alpha",
                    [sys.executable, "training/evaluate_alpha_ranker.py", "--checkpoint-dir", str(ckpt)],
                    ckpt,
                ),
            ]
        )
    if "p1" in jobs:
        ckpt = _track_checkpoint(checkpoint_run_root, "p1")
        steps.extend(
            [
                SuiteStep(
                    "train_p1_suite",
                    "p1",
                    [sys.executable, "training/train_p1_stack.py", "--backend", "auto", "--output-dir", str(ckpt)],
                    ckpt,
                ),
                SuiteStep(
                    "evaluate_p1_suite",
                    "p1",
                    [sys.executable, "training/evaluate_p1_stack.py", "--checkpoint-dir", str(ckpt)],
                    ckpt,
                ),
                SuiteStep(
                    "run_p1_walk_forward",
                    "p1",
                    [sys.executable, "training/run_p1_walk_forward.py", "--output-dir", str(ckpt)],
                    ckpt,
                ),
            ]
        )
    if "sequence" in jobs:
        ckpt = _track_checkpoint(checkpoint_run_root, "sequence")
        steps.append(
            SuiteStep(
                "train_sequence_forecaster_full",
                "sequence",
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
                    "--output-dir",
                    str(ckpt),
                ],
                ckpt,
            )
        )
    if "event" in jobs:
        ckpt = _track_checkpoint(checkpoint_run_root, "event")
        steps.append(
            SuiteStep(
                "train_event_classifier_full_suite",
                "event",
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
                    "--output-root",
                    str(ckpt),
                ],
                ckpt,
            )
        )
    if "p2" in jobs:
        ckpt = _track_checkpoint(checkpoint_run_root, "p2")
        steps.extend(
            [
                SuiteStep(
                    "train_p2_selector",
                    "p2",
                    [sys.executable, "training/train_p2_selector.py", "--backend", "auto", "--output-dir", str(ckpt)],
                    ckpt,
                ),
                SuiteStep(
                    "evaluate_p2_selector",
                    "p2",
                    [sys.executable, "training/evaluate_p2_selector.py", "--checkpoint-dir", str(ckpt)],
                    ckpt,
                ),
            ]
        )
    if "bandit" in jobs:
        ckpt = _track_checkpoint(checkpoint_run_root, "bandit")
        steps.append(
            SuiteStep(
                "train_contextual_bandit",
                "bandit",
                [sys.executable, "training/train_contextual_bandit.py", "--output-dir", str(ckpt)],
                ckpt,
            )
        )
    if "gnn" in jobs:
        ckpt = _track_checkpoint(checkpoint_run_root, "gnn")
        command = [
            sys.executable,
            "training/train_gnn_graph.py",
            "--epochs",
            str(args.gnn_epochs),
            "--batch-size",
            str(args.gnn_batch_size),
            "--hidden-size",
            str(args.gnn_hidden_size),
            "--output-dir",
            str(ckpt),
        ]
        if args.dry_run:
            command.append("--dry-run")
        steps.append(SuiteStep("train_gnn_graph", "gnn", command, ckpt))
    if "ppo" in jobs:
        ckpt = _track_checkpoint(checkpoint_run_root, "ppo")
        command = [
            sys.executable,
            "training/train_ppo_policy.py",
            "--total-timesteps",
            str(args.ppo_total_timesteps),
            "--n-steps",
            str(args.ppo_n_steps),
            "--batch-size",
            str(args.ppo_batch_size),
            "--output-dir",
            str(ckpt),
        ]
        if args.dry_run:
            command.append("--dry-run")
        steps.append(SuiteStep("train_ppo_policy", "ppo", command, ckpt))
    return steps


def _run_step(
    step: SuiteStep,
    *,
    run_root: Path,
    logs_dir: Path,
    status_dir: Path,
    dry_run: bool,
    resume: bool,
    skip_existing: bool,
) -> dict[str, Any]:
    status_file = _status_path(status_dir, step.name)
    stdout_path = logs_dir / f"{step.name}.stdout.log"
    stderr_path = logs_dir / f"{step.name}.stderr.log"

    if resume and _step_completed(status_dir, step.name):
        payload = {
            **_read_json(status_file),
            "resume_action": "skipped_completed",
            "skipped_at": _utc_now(),
        }
        _write_json(status_file, payload)
        print(f"[full-suite] resume skip {step.name}")
        return payload

    if skip_existing and _checkpoint_nonempty(step.checkpoint_dir):
        payload = {
            "step": step.name,
            "job": step.job,
            "status": "skipped_existing",
            "checkpoint_dir": str(step.checkpoint_dir) if step.checkpoint_dir else None,
            "command": step.command,
            "skipped_at": _utc_now(),
            "stage1_label": step.stage1_label,
        }
        _write_json(status_file, payload)
        print(f"[full-suite] existing checkpoint skip {step.name}")
        return payload

    started_at = _utc_now()
    payload = {
        "step": step.name,
        "job": step.job,
        "status": "dry_run" if dry_run else "running",
        "command": step.command,
        "checkpoint_dir": str(step.checkpoint_dir) if step.checkpoint_dir else None,
        "stdout_log": str(stdout_path),
        "stderr_log": str(stderr_path),
        "run_root": str(run_root),
        "started_at": started_at,
        "stage1_label": step.stage1_label,
    }
    _write_json(status_file, payload)

    if dry_run:
        stdout_path.parent.mkdir(parents=True, exist_ok=True)
        stdout_path.write_text("[Dry Run] " + " ".join(step.command) + "\n", encoding="utf-8")
        stderr_path.write_text("", encoding="utf-8")
        payload["completed_at"] = _utc_now()
        _write_json(status_file, payload)
        print("[Dry Run]", step.name, "->", " ".join(step.command))
        return payload

    started = time.monotonic()
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    with stdout_path.open("w", encoding="utf-8") as stdout, stderr_path.open("w", encoding="utf-8") as stderr:
        result = subprocess.run(step.command, cwd=PROJECT_ROOT, stdout=stdout, stderr=stderr, text=True, check=False)
    payload["returncode"] = int(result.returncode)
    payload["duration_seconds"] = round(time.monotonic() - started, 3)
    payload["completed_at"] = _utc_now()
    payload["gpu_after"] = _gpu_snapshot()
    if result.returncode == 0:
        payload["status"] = "completed"
        _write_json(status_file, payload)
        print(f"[full-suite] completed {step.name}")
        return payload

    payload["status"] = "failed"
    _write_json(status_file, payload)
    raise subprocess.CalledProcessError(result.returncode, step.command)


def _promote_checkpoints(jobs: list[str], checkpoint_run_root: Path, run_root: Path) -> dict[str, Any]:
    promoted: list[dict[str, str]] = []
    for job in jobs:
        source = _track_checkpoint(checkpoint_run_root, job)
        target = CANONICAL_CHECKPOINT_DIRS[job]
        if not _checkpoint_nonempty(source):
            promoted.append({"job": job, "status": "missing_source", "source": str(source), "target": str(target)})
            continue
        if target.exists():
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, target)
        promoted.append({"job": job, "status": "promoted", "source": str(source), "target": str(target)})
    payload = {"generated_at": _utc_now(), "promoted": promoted}
    _write_json(run_root / "promotion_manifest.json", payload)
    return payload


def _copy_manifest_if_requested(manifest: dict[str, Any], manifest_path: str | None) -> None:
    if not manifest_path:
        return
    target = Path(manifest_path)
    if not target.is_absolute():
        target = PROJECT_ROOT / target
    _write_json(target, manifest)


def main() -> int:
    os.environ.setdefault("HF_ENDPOINT", DEFAULT_HF_ENDPOINT)
    hf_home = Path(os.environ.setdefault("HF_HOME", str(PROJECT_ROOT / ".cache" / "huggingface")))
    os.environ.setdefault("HUGGINGFACE_HUB_CACHE", str(hf_home / "hub"))
    os.environ.setdefault("TRANSFORMERS_CACHE", str(hf_home / "transformers"))
    hf_home.mkdir(parents=True, exist_ok=True)

    parser = argparse.ArgumentParser(description="Run the full 5090 model-training suite with resume-safe logs.")
    parser.add_argument("--jobs", default="all", help="Comma-separated subset of jobs, or all.")
    parser.add_argument("--prepare-data", action="store_true", help="Rebuild prepared datasets before training.")
    parser.add_argument("--run-id", default="", help="Run id. Defaults to UTC timestamp.")
    parser.add_argument("--run-root", default=str(DEFAULT_RUN_ROOT), help="Parent directory for full-suite run artifacts.")
    parser.add_argument("--checkpoint-root", default=str(DEFAULT_CHECKPOINT_ROOT), help="Parent directory for isolated checkpoints.")
    parser.add_argument("--manifest-path", default="", help="Optional extra manifest copy path.")
    parser.add_argument("--dry-run", action="store_true", help="Print commands and write manifests without executing training.")
    parser.add_argument("--resume", action="store_true", help="Skip steps already marked completed in status files.")
    parser.add_argument("--skip-existing", action="store_true", help="Skip steps whose isolated checkpoint directory is non-empty.")
    parser.add_argument("--require-cuda", action="store_true", help="Fail if CUDA is not visible.")
    parser.add_argument("--allow-cpu-smoke", action="store_true", help="Allow CPU only for explicit --smoke checks.")
    parser.add_argument("--smoke", action="store_true", help="Clamp hyperparameters for a quick verification pass.")
    parser.add_argument("--promote-latest", action="store_true", help="Promote successful isolated checkpoints to runtime paths.")

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

    _apply_smoke_defaults(args)
    _ensure_cuda_policy(require_cuda=args.require_cuda, allow_cpu_smoke=args.allow_cpu_smoke, smoke=args.smoke)

    jobs = _selected_jobs(args.jobs)
    run_id = args.run_id.strip() or _safe_run_id()
    run_root = Path(args.run_root)
    if not run_root.is_absolute():
        run_root = PROJECT_ROOT / run_root
    run_root = run_root / run_id
    checkpoint_root = Path(args.checkpoint_root)
    if not checkpoint_root.is_absolute():
        checkpoint_root = PROJECT_ROOT / checkpoint_root
    checkpoint_run_root = checkpoint_root / run_id
    logs_dir = run_root / "logs"
    status_dir = run_root / "status"
    run_root.mkdir(parents=True, exist_ok=True)
    checkpoint_run_root.mkdir(parents=True, exist_ok=True)

    _write_json(run_root / "environment_snapshot.json", _environment_snapshot())

    steps: list[SuiteStep] = []
    if args.prepare_data:
        steps.extend(_build_prepare_steps())
    steps.extend(_build_job_steps(args, jobs, checkpoint_run_root))

    manifest: dict[str, Any] = {
        "generated_at": _utc_now(),
        "run_id": run_id,
        "project_root": str(PROJECT_ROOT),
        "run_root": str(run_root),
        "checkpoint_root": str(checkpoint_root),
        "checkpoint_run_root": str(checkpoint_run_root),
        "jobs": jobs,
        "prepare_data": bool(args.prepare_data),
        "dry_run": bool(args.dry_run),
        "resume": bool(args.resume),
        "skip_existing": bool(args.skip_existing),
        "smoke": bool(args.smoke),
        "stage1_label": STAGE1_LABEL,
        "environment_snapshot": str(run_root / "environment_snapshot.json"),
        "steps": [],
    }

    _write_json(run_root / "full_training_manifest.json", manifest)
    try:
        for step in steps:
            result = _run_step(
                step,
                run_root=run_root,
                logs_dir=logs_dir,
                status_dir=status_dir,
                dry_run=args.dry_run,
                resume=args.resume,
                skip_existing=args.skip_existing,
            )
            manifest["steps"].append(result)
            _write_json(run_root / "full_training_manifest.json", manifest)
    finally:
        manifest["finished_at"] = _utc_now()
        manifest["status_counts"] = {
            status: sum(1 for item in manifest["steps"] if item.get("status") == status)
            for status in sorted({str(item.get("status")) for item in manifest["steps"]})
        }
        _write_json(run_root / "full_training_manifest.json", manifest)
        _copy_manifest_if_requested(manifest, args.manifest_path or None)

    if args.promote_latest and not args.dry_run:
        manifest["promotion"] = _promote_checkpoints(jobs, checkpoint_run_root, run_root)
        _write_json(run_root / "full_training_manifest.json", manifest)
        _copy_manifest_if_requested(manifest, args.manifest_path or None)

    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
