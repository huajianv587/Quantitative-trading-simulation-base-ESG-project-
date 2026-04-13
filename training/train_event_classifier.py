from __future__ import annotations

import argparse
import inspect
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score
from sklearn.preprocessing import LabelEncoder

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = PROJECT_ROOT / "data" / "event_classifier"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "model-serving" / "checkpoint" / "event_classifier"

TASK_TARGET_MAP = {
    "severity": "controversy_label",
    "impact_area": "esg_axis_label",
    "event_type": "impact_direction",
    "sentiment": "sentiment_label",
    "regime": "regime_label",
    "controversy_label": "controversy_label",
    "sentiment_label": "sentiment_label",
    "esg_axis_label": "esg_axis_label",
    "impact_direction": "impact_direction",
    "regime_label": "regime_label",
}
DEFAULT_TASKS = ["severity", "impact_area", "event_type"]


def _load_frame(path: str | Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    if "text" not in frame.columns:
        raise ValueError(f"{path} is missing the text column.")
    return frame


def _normalize_task_name(task: str) -> str:
    normalized = str(task or "").strip()
    if normalized not in TASK_TARGET_MAP:
        supported = ", ".join(sorted(TASK_TARGET_MAP))
        raise ValueError(f"Unsupported task '{task}'. Supported values: {supported}")
    return normalized


def _resolve_tasks(args: argparse.Namespace) -> list[str]:
    if args.train_all_tasks:
        raw_tasks = list(DEFAULT_TASKS)
    elif args.tasks:
        raw_tasks = [item.strip() for item in str(args.tasks).split(",") if item.strip()]
    elif args.task:
        raw_tasks = [str(args.task).strip()]
    elif args.target_column:
        raw_tasks = [str(args.target_column).strip()]
    else:
        raw_tasks = ["controversy_label"]

    tasks: list[str] = []
    for item in raw_tasks:
        normalized = _normalize_task_name(item)
        if normalized not in tasks:
            tasks.append(normalized)
    return tasks


def _train_single_task(
    *,
    task_name: str,
    model_name: str,
    train: pd.DataFrame,
    val: pd.DataFrame,
    text_column: str,
    max_length: int,
    num_train_epochs: int,
    per_device_train_batch_size: int,
    per_device_eval_batch_size: int,
    learning_rate: float,
    max_steps: int,
    output_dir: Path,
) -> dict[str, object]:
    target_column = TASK_TARGET_MAP[task_name]
    if target_column not in train.columns or target_column not in val.columns:
        raise ValueError(f"Target column '{target_column}' required by task '{task_name}' is missing.")

    label_encoder = LabelEncoder()
    train_labels = label_encoder.fit_transform(train[target_column].astype(str))
    val_labels = label_encoder.transform(val[target_column].astype(str))

    from datasets import Dataset
    from transformers import (
        AutoModelForSequenceClassification,
        AutoTokenizer,
        DataCollatorWithPadding,
        Trainer,
        TrainingArguments,
    )

    tokenizer = AutoTokenizer.from_pretrained(model_name)
    train_ds = Dataset.from_pandas(
        pd.DataFrame({"text": train[text_column].astype(str), "label": train_labels}),
        preserve_index=False,
    )
    val_ds = Dataset.from_pandas(
        pd.DataFrame({"text": val[text_column].astype(str), "label": val_labels}),
        preserve_index=False,
    )

    def tokenize(batch: dict[str, list[str]]) -> dict[str, object]:
        return tokenizer(batch["text"], truncation=True, max_length=max_length)

    train_ds = train_ds.map(tokenize, batched=True)
    val_ds = val_ds.map(tokenize, batched=True)
    model = AutoModelForSequenceClassification.from_pretrained(
        model_name,
        num_labels=len(label_encoder.classes_),
        ignore_mismatched_sizes=True,
    )

    def compute_metrics(eval_pred) -> dict[str, float]:
        logits, labels = eval_pred
        predictions = np.argmax(logits, axis=-1)
        return {
            "accuracy": round(float(accuracy_score(labels, predictions)), 6),
            "f1_macro": round(float(f1_score(labels, predictions, average="macro")), 6),
        }

    training_arg_kwargs = dict(
        output_dir=str(output_dir),
        learning_rate=learning_rate,
        per_device_train_batch_size=per_device_train_batch_size,
        per_device_eval_batch_size=per_device_eval_batch_size,
        num_train_epochs=num_train_epochs,
        weight_decay=0.01,
        save_strategy="epoch",
        logging_steps=10,
        load_best_model_at_end=True,
        metric_for_best_model="f1_macro",
        greater_is_better=True,
        report_to="none",
    )
    training_arg_params = inspect.signature(TrainingArguments.__init__).parameters
    if "eval_strategy" in training_arg_params:
        training_arg_kwargs["eval_strategy"] = "epoch"
    else:
        training_arg_kwargs["evaluation_strategy"] = "epoch"
    training_args = TrainingArguments(**training_arg_kwargs)
    if max_steps > 0:
        training_args.max_steps = max_steps

    trainer_kwargs = dict(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        data_collator=DataCollatorWithPadding(tokenizer=tokenizer),
        compute_metrics=compute_metrics,
    )
    trainer_params = inspect.signature(Trainer.__init__).parameters
    if "processing_class" in trainer_params:
        trainer_kwargs["processing_class"] = tokenizer
    else:
        trainer_kwargs["tokenizer"] = tokenizer
    trainer = Trainer(**trainer_kwargs)
    trainer.train()
    metrics = trainer.evaluate()
    trainer.save_model(str(output_dir))
    tokenizer.save_pretrained(str(output_dir))

    metadata = {
        "generated_at": pd.Timestamp.utcnow().isoformat(),
        "task": task_name,
        "target_column": target_column,
        "model_name": model_name,
        "text_column": text_column,
        "max_length": max_length,
        "classes": [str(item) for item in label_encoder.classes_],
        "metrics": {
            "accuracy": round(float(metrics.get("eval_accuracy", 0.0)), 6),
            "f1_macro": round(float(metrics.get("eval_f1_macro", 0.0)), 6),
        },
        "rows_train": int(len(train)),
        "rows_val": int(len(val)),
    }
    (output_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"output_dir": str(output_dir), **metadata}


def main() -> int:
    parser = argparse.ArgumentParser(description="Train ESG event classifiers with single-task or multi-task orchestration.")
    parser.add_argument("--model-name", default="ProsusAI/finbert", help="Base model repo id.")
    parser.add_argument("--train-csv", default=str(DEFAULT_DATA_DIR / "train.csv"), help="Training csv path.")
    parser.add_argument("--val-csv", default=str(DEFAULT_DATA_DIR / "val.csv"), help="Validation csv path.")
    parser.add_argument("--text-column", default="text", help="Input text column.")
    parser.add_argument("--task", default="", help="Logical task name, for example severity or impact_area.")
    parser.add_argument("--tasks", default="", help="Comma-separated task names for multi-task orchestration.")
    parser.add_argument("--train-all-tasks", action="store_true", help="Train the default P1/P2 event task suite.")
    parser.add_argument(
        "--target-column",
        default="",
        help="Backward-compatible target column or task alias (for example controversy_label).",
    )
    parser.add_argument("--max-length", type=int, default=256, help="Tokenization length.")
    parser.add_argument("--num-train-epochs", type=int, default=2, help="Epoch count.")
    parser.add_argument("--per-device-train-batch-size", type=int, default=8, help="Training batch size.")
    parser.add_argument("--per-device-eval-batch-size", type=int, default=16, help="Validation batch size.")
    parser.add_argument("--learning-rate", type=float, default=2e-5, help="Learning rate.")
    parser.add_argument("--max-steps", type=int, default=-1, help="Optional quick smoke limit.")
    parser.add_argument("--output-dir", default="", help="Optional output checkpoint directory.")
    args = parser.parse_args()

    train = _load_frame(args.train_csv)
    val = _load_frame(args.val_csv)
    tasks = _resolve_tasks(args)

    custom_output = Path(args.output_dir) if args.output_dir else None
    root_output_dir = custom_output or DEFAULT_OUTPUT_ROOT
    root_output_dir.mkdir(parents=True, exist_ok=True)

    task_reports: dict[str, dict[str, object]] = {}
    single_task_mode = len(tasks) == 1 and not args.train_all_tasks and not args.tasks
    for task_name in tasks:
        task_output_dir = root_output_dir if single_task_mode else root_output_dir / task_name
        task_output_dir.mkdir(parents=True, exist_ok=True)
        task_reports[task_name] = _train_single_task(
            task_name=task_name,
            model_name=args.model_name,
            train=train,
            val=val,
            text_column=args.text_column,
            max_length=args.max_length,
            num_train_epochs=args.num_train_epochs,
            per_device_train_batch_size=args.per_device_train_batch_size,
            per_device_eval_batch_size=args.per_device_eval_batch_size,
            learning_rate=args.learning_rate,
            max_steps=args.max_steps,
            output_dir=task_output_dir,
        )

    if not single_task_mode:
        manifest = {
            "generated_at": pd.Timestamp.utcnow().isoformat(),
            "model_name": args.model_name,
            "text_column": args.text_column,
            "tasks": task_reports,
        }
        (root_output_dir / "multi_task_manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(json.dumps({"output_dir": str(root_output_dir), **manifest}, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(task_reports[tasks[0]], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
