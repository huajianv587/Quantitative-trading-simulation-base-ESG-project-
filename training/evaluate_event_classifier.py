from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, classification_report, f1_score

DEFAULT_DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "event_classifier"
DEFAULT_CHECKPOINT_ROOT = Path(__file__).resolve().parents[1] / "model-serving" / "checkpoint" / "event_classifier"


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate an ESG news / controversy classifier checkpoint.")
    parser.add_argument("--checkpoint-dir", default=str(DEFAULT_CHECKPOINT_ROOT / "controversy_label"), help="Checkpoint directory.")
    parser.add_argument("--val-csv", default=str(DEFAULT_DATA_DIR / "val.csv"), help="Validation csv.")
    parser.add_argument("--text-column", default="text", help="Input text column.")
    parser.add_argument("--target-column", default="controversy_label", help="Target label column.")
    parser.add_argument("--batch-size", type=int, default=16, help="Batch size.")
    args = parser.parse_args()

    checkpoint_dir = Path(args.checkpoint_dir)
    metadata = json.loads((checkpoint_dir / "metadata.json").read_text(encoding="utf-8"))
    labels = [str(item) for item in metadata.get("classes", [])]
    label_to_index = {label: index for index, label in enumerate(labels)}
    frame = pd.read_csv(args.val_csv)

    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    import torch

    tokenizer = AutoTokenizer.from_pretrained(str(checkpoint_dir))
    model = AutoModelForSequenceClassification.from_pretrained(str(checkpoint_dir))
    model.eval()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)

    predictions: list[int] = []
    targets = [label_to_index[str(item)] for item in frame[args.target_column].astype(str)]
    texts = frame[args.text_column].astype(str).tolist()
    for start in range(0, len(texts), args.batch_size):
        batch = texts[start : start + args.batch_size]
        encoded = tokenizer(batch, padding=True, truncation=True, return_tensors="pt")
        encoded = {key: value.to(device) for key, value in encoded.items()}
        with torch.no_grad():
            logits = model(**encoded).logits
        predictions.extend(np.argmax(logits.detach().cpu().numpy(), axis=-1).tolist())

    report = {
        "generated_at": pd.Timestamp.utcnow().isoformat(),
        "checkpoint_dir": str(checkpoint_dir),
        "target_column": args.target_column,
        "accuracy": round(float(accuracy_score(targets, predictions)), 6),
        "f1_macro": round(float(f1_score(targets, predictions, average="macro")), 6),
        "classification_report": classification_report(
            targets,
            predictions,
            target_names=labels,
            output_dict=True,
            zero_division=0,
        ),
    }
    (checkpoint_dir / "evaluation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
