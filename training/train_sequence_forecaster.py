from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = PROJECT_ROOT / "data" / "p1_stack"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "model-serving" / "checkpoint" / "sequence_forecaster"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from gateway.quant.p1_stack import P1_FEATURE_COLUMNS, SEQUENCE_TARGET_COLUMN_TO_KEY
from training.prepare_alpha_data import split_dataset


TARGET_KEY_TO_COLUMN = {value: key for key, value in SEQUENCE_TARGET_COLUMN_TO_KEY.items()}
DEFAULT_TARGET_COLUMNS = [
    "forward_return_1d",
    "forward_return_5d",
    "future_volatility_10d",
    "future_max_drawdown_20d",
]


def build_sequences(
    frame: pd.DataFrame,
    feature_names: list[str],
    target_column: str,
    window_size: int,
) -> tuple[np.ndarray, np.ndarray]:
    ordered = frame.sort_values(["symbol", "date"]).reset_index(drop=True)
    x_rows: list[np.ndarray] = []
    y_rows: list[float] = []
    for _, symbol_slice in ordered.groupby("symbol"):
        values = symbol_slice[feature_names].fillna(0.0).to_numpy(dtype=np.float32)
        targets = symbol_slice[target_column].to_numpy(dtype=np.float32)
        for index in range(window_size, len(symbol_slice)):
            x_rows.append(values[index - window_size:index])
            y_rows.append(float(targets[index]))
    if not x_rows:
        return np.zeros((0, window_size, len(feature_names)), dtype=np.float32), np.zeros((0,), dtype=np.float32)
    return np.stack(x_rows), np.asarray(y_rows, dtype=np.float32)


def _parse_target_columns(args: argparse.Namespace) -> list[str]:
    if args.train_all_targets:
        return list(DEFAULT_TARGET_COLUMNS)
    raw = str(args.target_columns or "").strip()
    if raw:
        parsed = [item.strip() for item in raw.split(",") if item.strip()]
        return parsed or [args.target_column]
    return [args.target_column]


def _target_output_dir(base_dir: Path, target_column: str, multi_target: bool) -> Path:
    if not multi_target:
        return base_dir
    target_key = SEQUENCE_TARGET_COLUMN_TO_KEY.get(target_column, target_column)
    return base_dir / target_key


def _manifest_payload(
    *,
    args: argparse.Namespace,
    target_column: str,
    train_x: np.ndarray,
    val_x: np.ndarray,
    dry_run: bool,
) -> dict[str, object]:
    return {
        "generated_at": pd.Timestamp.utcnow().isoformat(),
        "architecture": args.architecture,
        "target_column": target_column,
        "target_key": SEQUENCE_TARGET_COLUMN_TO_KEY.get(target_column, target_column),
        "window_size": args.window_size,
        "hidden_size": args.hidden_size,
        "epochs": args.epochs,
        "batch_size": args.batch_size,
        "train_shape": list(train_x.shape),
        "val_shape": list(val_x.shape),
        "dry_run": bool(dry_run),
    }


def _write_manifest(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _train_single_target(
    *,
    args: argparse.Namespace,
    train: pd.DataFrame,
    val: pd.DataFrame,
    target_column: str,
    output_dir: Path,
) -> dict[str, object]:
    train_x, train_y = build_sequences(train, P1_FEATURE_COLUMNS, target_column, args.window_size)
    val_x, val_y = build_sequences(val, P1_FEATURE_COLUMNS, target_column, args.window_size)
    payload = _manifest_payload(
        args=args,
        target_column=target_column,
        train_x=train_x,
        val_x=val_x,
        dry_run=args.dry_run,
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.dry_run:
        _write_manifest(output_dir / "sequence_manifest.json", payload)
        return payload

    try:
        import torch
        from torch import nn
        from torch.utils.data import DataLoader, TensorDataset
    except Exception as exc:
        raise SystemExit(f"PyTorch is required for sequence training: {exc}") from exc

    class LSTMForecaster(nn.Module):
        def __init__(self, input_size: int, hidden_size: int) -> None:
            super().__init__()
            self.lstm = nn.LSTM(input_size=input_size, hidden_size=hidden_size, batch_first=True)
            self.head = nn.Linear(hidden_size, 1)

        def forward(self, batch):
            _, (hidden, _) = self.lstm(batch)
            return self.head(hidden[-1]).squeeze(-1)

    class TCNForecaster(nn.Module):
        def __init__(self, input_size: int, hidden_size: int) -> None:
            super().__init__()
            self.net = nn.Sequential(
                nn.Conv1d(input_size, hidden_size, kernel_size=3, padding=2),
                nn.ReLU(),
                nn.Conv1d(hidden_size, hidden_size, kernel_size=3, padding=4, dilation=2),
                nn.ReLU(),
                nn.AdaptiveAvgPool1d(1),
            )
            self.head = nn.Linear(hidden_size, 1)

        def forward(self, batch):
            features = self.net(batch.transpose(1, 2)).squeeze(-1)
            return self.head(features).squeeze(-1)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    train_ds = TensorDataset(torch.tensor(train_x), torch.tensor(train_y))
    val_ds = TensorDataset(torch.tensor(val_x), torch.tensor(val_y))
    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=args.batch_size, shuffle=False)
    model = (LSTMForecaster if args.architecture == "lstm" else TCNForecaster)(
        len(P1_FEATURE_COLUMNS),
        args.hidden_size,
    ).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    criterion = nn.MSELoss()
    best_val = float("inf")

    for _ in range(args.epochs):
        model.train()
        for batch_x, batch_y in train_loader:
            batch_x = batch_x.to(device)
            batch_y = batch_y.to(device)
            optimizer.zero_grad()
            loss = criterion(model(batch_x), batch_y)
            loss.backward()
            optimizer.step()
        model.eval()
        losses = []
        with torch.no_grad():
            for batch_x, batch_y in val_loader:
                batch_x = batch_x.to(device)
                batch_y = batch_y.to(device)
                losses.append(float(criterion(model(batch_x), batch_y).item()))
        best_val = min(best_val, float(np.mean(losses) if losses else 0.0))

    torch.save(model.state_dict(), output_dir / "model.pt")
    payload["best_val_loss"] = round(best_val, 6)
    _write_manifest(output_dir / "sequence_manifest.json", payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Train or dry-run multi-target sequence forecasters for P1.")
    parser.add_argument("--full-csv", default="", help="Optional full dataset csv path. If provided, create train/val splits automatically.")
    parser.add_argument("--train-csv", default=str(DEFAULT_DATA_DIR / "train.csv"), help="Training csv path.")
    parser.add_argument("--val-csv", default=str(DEFAULT_DATA_DIR / "val.csv"), help="Validation csv path.")
    parser.add_argument("--target-column", default="forward_return_5d", help="Single target to learn.")
    parser.add_argument(
        "--target-columns",
        default="",
        help="Comma-separated targets. Example: forward_return_1d,forward_return_5d",
    )
    parser.add_argument(
        "--train-all-targets",
        action="store_true",
        help="Train all default P1 sequence targets into per-target subdirectories.",
    )
    parser.add_argument("--window-size", type=int, default=20, help="Sequence window length.")
    parser.add_argument("--architecture", default="lstm", choices=["lstm", "tcn"], help="Sequence architecture.")
    parser.add_argument("--hidden-size", type=int, default=64, help="Hidden dimension.")
    parser.add_argument("--epochs", type=int, default=3, help="Training epochs.")
    parser.add_argument("--batch-size", type=int, default=32, help="Batch size.")
    parser.add_argument("--dry-run", action="store_true", help="Only prepare sequence tensors and metadata.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Checkpoint output directory.")
    args = parser.parse_args()

    if args.full_csv:
        full = pd.read_csv(args.full_csv)
        train, val = split_dataset(full, 0.2)
    else:
        train = pd.read_csv(args.train_csv)
        val = pd.read_csv(args.val_csv)

    target_columns = _parse_target_columns(args)
    unsupported = [item for item in target_columns if item not in SEQUENCE_TARGET_COLUMN_TO_KEY]
    if unsupported:
        raise SystemExit(
            f"Unsupported sequence targets: {unsupported}. Allowed targets: {list(SEQUENCE_TARGET_COLUMN_TO_KEY)}"
        )

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    multi_target = len(target_columns) > 1
    results: list[dict[str, object]] = []
    for target_column in target_columns:
        target_output_dir = _target_output_dir(output_dir, target_column, multi_target)
        results.append(
            _train_single_target(
                args=args,
                train=train,
                val=val,
                target_column=target_column,
                output_dir=target_output_dir,
            )
        )

    summary = {
        "generated_at": pd.Timestamp.utcnow().isoformat(),
        "architecture": args.architecture,
        "window_size": args.window_size,
        "targets": [
            {
                "target_column": item["target_column"],
                "target_key": item["target_key"],
                "output_dir": str(_target_output_dir(output_dir, str(item["target_column"]), multi_target)),
                "best_val_loss": item.get("best_val_loss"),
            }
            for item in results
        ],
        "dry_run": bool(args.dry_run),
        "multi_target": multi_target,
    }
    _write_manifest(output_dir / "multi_target_manifest.json", summary)
    if not multi_target and results:
        _write_manifest(output_dir / "sequence_manifest.json", results[0])
    print(json.dumps(summary if multi_target else results[0], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
