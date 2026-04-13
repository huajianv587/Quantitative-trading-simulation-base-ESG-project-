from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = PROJECT_ROOT / "data" / "event_classifier"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "model-serving" / "checkpoint" / "event_classifier"

TASK_SPECS = [
    {
        "task": "controversy_label",
        "model_name": "ProsusAI/finbert",
        "description": "Primary controversy and severity head.",
    },
    {
        "task": "sentiment_label",
        "model_name": "ProsusAI/finbert",
        "description": "Finance/news sentiment head.",
    },
    {
        "task": "esg_axis_label",
        "model_name": "microsoft/deberta-v3-base",
        "description": "E/S/G axis classifier.",
    },
    {
        "task": "impact_direction",
        "model_name": "microsoft/deberta-v3-base",
        "description": "Opportunity / watchlist / risk-event direction head.",
    },
    {
        "task": "regime_label",
        "model_name": "microsoft/deberta-v3-base",
        "description": "Risk-on / neutral / risk-off text regime head.",
    },
]


def _selected_specs(tasks_arg: str) -> list[dict[str, str]]:
    if not tasks_arg.strip():
        return list(TASK_SPECS)
    requested = [item.strip() for item in tasks_arg.split(",") if item.strip()]
    lookup = {spec["task"]: spec for spec in TASK_SPECS}
    missing = [task for task in requested if task not in lookup]
    if missing:
        raise SystemExit(f"Unsupported event tasks: {missing}. Allowed: {sorted(lookup)}")
    return [lookup[task] for task in requested]


def _run(command: list[str], *, dry_run: bool) -> None:
    if dry_run:
        print("[Dry Run]", " ".join(command))
        return
    subprocess.run(command, cwd=PROJECT_ROOT, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Train the complete event-classifier suite task by task.")
    parser.add_argument("--train-csv", default=str(DEFAULT_DATA_DIR / "train.csv"), help="Training csv path.")
    parser.add_argument("--val-csv", default=str(DEFAULT_DATA_DIR / "val.csv"), help="Validation csv path.")
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT), help="Output checkpoint root.")
    parser.add_argument("--tasks", default="", help="Optional comma-separated subset of tasks.")
    parser.add_argument("--max-length", type=int, default=256, help="Tokenization length.")
    parser.add_argument("--num-train-epochs", type=int, default=4, help="Epoch count per task.")
    parser.add_argument("--per-device-train-batch-size", type=int, default=32, help="Train batch size per task.")
    parser.add_argument("--per-device-eval-batch-size", type=int, default=64, help="Eval batch size per task.")
    parser.add_argument("--learning-rate", type=float, default=2e-5, help="Learning rate.")
    parser.add_argument("--max-steps", type=int, default=-1, help="Optional quick smoke limit.")
    parser.add_argument("--dry-run", action="store_true", help="Print commands without executing them.")
    args = parser.parse_args()

    output_root = Path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    selected_specs = _selected_specs(args.tasks)

    manifest: dict[str, object] = {
        "generated_at": None,
        "suite_version": None,
        "train_csv": str(Path(args.train_csv)),
        "val_csv": str(Path(args.val_csv)),
        "output_root": str(output_root),
        "tasks": {},
        "dry_run": bool(args.dry_run),
    }

    for spec in selected_specs:
        task_name = str(spec["task"])
        checkpoint_dir = output_root / task_name
        train_command = [
            sys.executable,
            "training/train_event_classifier.py",
            "--task",
            task_name,
            "--model-name",
            str(spec["model_name"]),
            "--train-csv",
            str(args.train_csv),
            "--val-csv",
            str(args.val_csv),
            "--output-dir",
            str(checkpoint_dir),
            "--max-length",
            str(args.max_length),
            "--num-train-epochs",
            str(args.num_train_epochs),
            "--per-device-train-batch-size",
            str(args.per_device_train_batch_size),
            "--per-device-eval-batch-size",
            str(args.per_device_eval_batch_size),
            "--learning-rate",
            str(args.learning_rate),
        ]
        if args.max_steps > 0:
            train_command.extend(["--max-steps", str(args.max_steps)])

        eval_command = [
            sys.executable,
            "training/evaluate_event_classifier.py",
            "--checkpoint-dir",
            str(checkpoint_dir),
            "--val-csv",
            str(args.val_csv),
            "--target-column",
            task_name,
        ]

        _run(train_command, dry_run=args.dry_run)
        _run(eval_command, dry_run=args.dry_run)

        manifest["tasks"][task_name] = {
            "model_name": spec["model_name"],
            "description": spec["description"],
            "checkpoint_dir": str(checkpoint_dir),
            "train_command": train_command,
            "eval_command": eval_command,
        }

    if not args.dry_run:
        generated_at = None
        for task_name in manifest["tasks"]:
            metadata_path = output_root / str(task_name) / "metadata.json"
            if metadata_path.exists():
                payload = json.loads(metadata_path.read_text(encoding="utf-8"))
                manifest["tasks"][task_name]["metadata"] = payload
                generated_at = generated_at or payload.get("generated_at")
            evaluation_path = output_root / str(task_name) / "evaluation.json"
            if evaluation_path.exists():
                manifest["tasks"][task_name]["evaluation"] = json.loads(evaluation_path.read_text(encoding="utf-8"))
        manifest["generated_at"] = generated_at
        manifest["suite_version"] = f"event-suite-{generated_at or 'manual'}"
    else:
        manifest["generated_at"] = "dry-run"
        manifest["suite_version"] = "event-suite-dry-run"

    (output_root / "suite_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
