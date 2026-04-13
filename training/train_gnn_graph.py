from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = PROJECT_ROOT / "data" / "advanced_decision"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "model-serving" / "checkpoint" / "gnn_graph"

FEATURE_COLUMNS = [
    "p1_stack_score",
    "graph_centrality",
    "graph_contagion_risk",
    "graph_diversification_score",
    "graph_influence_score",
    "predicted_return_1d",
    "predicted_return_5d",
    "predicted_volatility_10d",
    "predicted_drawdown_20d",
]
TARGET_COLUMNS = [
    "graph_centrality",
    "graph_contagion_risk",
    "graph_diversification_score",
    "graph_influence_score",
]
CLUSTER_LABELS = ["defensive", "growth", "balanced", "crowded"]


def _bounded(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _load_frame(path: str | Path) -> pd.DataFrame:
    return pd.read_csv(path)


def _assign_clusters(frame: pd.DataFrame, reference: pd.DataFrame) -> pd.Series:
    defensive_drawdown = float(reference["predicted_drawdown_20d"].quantile(0.35))
    defensive_contagion = float(reference["graph_contagion_risk"].quantile(0.40))
    growth_return = float(reference["predicted_return_5d"].quantile(0.72))
    growth_stack = float(reference["p1_stack_score"].quantile(0.70))
    crowded_centrality = float(reference["graph_centrality"].quantile(0.72))
    crowded_contagion = float(reference["graph_contagion_risk"].quantile(0.72))

    labels: list[str] = []
    for _, row in frame.iterrows():
        if (
            float(row["predicted_drawdown_20d"]) <= defensive_drawdown
            and float(row["graph_contagion_risk"]) <= defensive_contagion
        ):
            labels.append("defensive")
        elif (
            float(row["predicted_return_5d"]) >= growth_return
            and float(row["p1_stack_score"]) >= growth_stack
        ):
            labels.append("growth")
        elif (
            float(row["graph_centrality"]) >= crowded_centrality
            and float(row["graph_contagion_risk"]) >= crowded_contagion
        ):
            labels.append("crowded")
        else:
            labels.append("balanced")
    return pd.Series(labels, index=frame.index, dtype="string")


def _build_neighbor_matrix(
    frame: pd.DataFrame,
    edges: pd.DataFrame,
    feature_names: list[str],
) -> tuple[np.ndarray, np.ndarray]:
    local = frame.copy().reset_index(drop=True)
    feature_matrix = local[feature_names].fillna(0.0).to_numpy(dtype=np.float32)
    node_index = {
        (str(row["date"]), str(row["symbol"])): index
        for index, row in local[["date", "symbol"]].astype(str).iterrows()
    }
    neighbor_sum = np.zeros_like(feature_matrix, dtype=np.float32)
    neighbor_weight = np.zeros((len(local),), dtype=np.float32)

    for _, edge in edges.iterrows():
        date_key = str(edge["date"])
        source_key = (date_key, str(edge["source"]))
        target_key = (date_key, str(edge["target"]))
        if source_key not in node_index or target_key not in node_index:
            continue
        source_index = node_index[source_key]
        target_index = node_index[target_key]
        weight = float(edge.get("weight", 1.0))
        neighbor_sum[source_index] += feature_matrix[target_index] * weight
        neighbor_sum[target_index] += feature_matrix[source_index] * weight
        neighbor_weight[source_index] += weight
        neighbor_weight[target_index] += weight

    neighbor_matrix = np.zeros_like(feature_matrix, dtype=np.float32)
    valid = neighbor_weight > 0
    if np.any(valid):
        neighbor_matrix[valid] = neighbor_sum[valid] / neighbor_weight[valid][:, None]
    return neighbor_matrix, neighbor_weight


def _prepare_dataset(
    frame: pd.DataFrame,
    edges: pd.DataFrame,
    reference: pd.DataFrame,
) -> dict[str, np.ndarray]:
    neighbor_matrix, neighbor_weight = _build_neighbor_matrix(frame, edges, FEATURE_COLUMNS)
    cluster_labels = _assign_clusters(frame, reference)
    cluster_to_index = {label: index for index, label in enumerate(CLUSTER_LABELS)}
    return {
        "node_features": frame[FEATURE_COLUMNS].fillna(0.0).to_numpy(dtype=np.float32),
        "neighbor_features": neighbor_matrix.astype(np.float32),
        "targets": frame[TARGET_COLUMNS].fillna(0.0).to_numpy(dtype=np.float32),
        "clusters": np.asarray([cluster_to_index[str(label)] for label in cluster_labels], dtype=np.int64),
        "neighbor_weight": neighbor_weight.astype(np.float32),
    }


def _evaluate(model, dataset: dict[str, np.ndarray], *, device: str, batch_size: int) -> dict[str, float]:
    import torch
    from torch.utils.data import DataLoader, TensorDataset

    tensor_ds = TensorDataset(
        torch.tensor(dataset["node_features"], dtype=torch.float32),
        torch.tensor(dataset["neighbor_features"], dtype=torch.float32),
        torch.tensor(dataset["targets"], dtype=torch.float32),
        torch.tensor(dataset["clusters"], dtype=torch.long),
    )
    loader = DataLoader(tensor_ds, batch_size=batch_size, shuffle=False)
    mse_losses: list[float] = []
    accuracies: list[float] = []
    model.eval()
    with torch.no_grad():
        for node_features, neighbor_features, targets, clusters in loader:
            node_features = node_features.to(device)
            neighbor_features = neighbor_features.to(device)
            targets = targets.to(device)
            clusters = clusters.to(device)
            outputs = model(node_features, neighbor_features)
            mse_losses.append(float(torch.mean((outputs["node_scores"] - targets) ** 2).item()))
            predicted_clusters = torch.argmax(outputs["cluster_logits"], dim=-1)
            accuracies.append(float((predicted_clusters == clusters).float().mean().item()))
    return {
        "node_mse": round(float(np.mean(mse_losses) if mse_losses else 0.0), 6),
        "cluster_accuracy": round(float(np.mean(accuracies) if accuracies else 0.0), 6),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Train the optional P2 GNN graph refiner checkpoint.")
    parser.add_argument("--train-nodes", default=str(DEFAULT_DATA_DIR / "graph_nodes_train.csv"), help="Training node csv.")
    parser.add_argument("--val-nodes", default=str(DEFAULT_DATA_DIR / "graph_nodes_val.csv"), help="Validation node csv.")
    parser.add_argument("--edges-csv", default=str(DEFAULT_DATA_DIR / "graph_edges.csv"), help="Graph edge csv.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Checkpoint output directory.")
    parser.add_argument("--hidden-size", type=int, default=128, help="Hidden dimension.")
    parser.add_argument("--epochs", type=int, default=60, help="Epoch count.")
    parser.add_argument("--batch-size", type=int, default=1024, help="Mini-batch size.")
    parser.add_argument("--learning-rate", type=float, default=1e-3, help="Learning rate.")
    parser.add_argument("--weight-decay", type=float, default=1e-5, help="Weight decay.")
    parser.add_argument("--cluster-loss-weight", type=float, default=0.35, help="Classification loss weight.")
    parser.add_argument("--dry-run", action="store_true", help="Only validate dataset loading and emit metadata.")
    args = parser.parse_args()

    train_nodes = _load_frame(args.train_nodes)
    val_nodes = _load_frame(args.val_nodes)
    edges = _load_frame(args.edges_csv)

    train_dataset = _prepare_dataset(train_nodes, edges, train_nodes)
    val_dataset = _prepare_dataset(val_nodes, edges, train_nodes)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    metadata: dict[str, object] = {
        "generated_at": pd.Timestamp.utcnow().isoformat(),
        "model_name": "graphsage_refiner",
        "feature_names": list(FEATURE_COLUMNS),
        "target_columns": list(TARGET_COLUMNS),
        "cluster_labels": list(CLUSTER_LABELS),
        "hidden_size": int(args.hidden_size),
        "epochs": int(args.epochs),
        "batch_size": int(args.batch_size),
        "learning_rate": float(args.learning_rate),
        "train_rows": int(len(train_nodes)),
        "val_rows": int(len(val_nodes)),
        "dry_run": bool(args.dry_run),
    }

    if args.dry_run:
        (output_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"output_dir": str(output_dir), **metadata}, ensure_ascii=False, indent=2))
        return 0

    import torch
    from torch import nn
    from torch.utils.data import DataLoader, TensorDataset

    class GraphSAGERefiner(nn.Module):
        def __init__(self, input_size: int, hidden_size: int, cluster_count: int) -> None:
            super().__init__()
            self.self_proj = nn.Linear(input_size, hidden_size)
            self.neighbor_proj = nn.Linear(input_size, hidden_size)
            self.fusion = nn.Sequential(
                nn.ReLU(),
                nn.Linear(hidden_size * 2, hidden_size),
                nn.ReLU(),
            )
            self.node_head = nn.Linear(hidden_size, 4)
            self.cluster_head = nn.Linear(hidden_size, cluster_count)

        def forward(self, node_features, neighbor_features):
            fused = torch.cat(
                [self.self_proj(node_features), self.neighbor_proj(neighbor_features)],
                dim=-1,
            )
            hidden = self.fusion(fused)
            node_scores = torch.sigmoid(self.node_head(hidden))
            cluster_logits = self.cluster_head(hidden)
            return {"node_scores": node_scores, "cluster_logits": cluster_logits}

    train_tensor_ds = TensorDataset(
        torch.tensor(train_dataset["node_features"], dtype=torch.float32),
        torch.tensor(train_dataset["neighbor_features"], dtype=torch.float32),
        torch.tensor(train_dataset["targets"], dtype=torch.float32),
        torch.tensor(train_dataset["clusters"], dtype=torch.long),
    )
    train_loader = DataLoader(train_tensor_ds, batch_size=args.batch_size, shuffle=True)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = GraphSAGERefiner(len(FEATURE_COLUMNS), int(args.hidden_size), len(CLUSTER_LABELS)).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate, weight_decay=args.weight_decay)
    mse_loss = nn.MSELoss()
    ce_loss = nn.CrossEntropyLoss()

    best_state = None
    best_val_mse = float("inf")
    for _ in range(args.epochs):
        model.train()
        for node_features, neighbor_features, targets, clusters in train_loader:
            node_features = node_features.to(device)
            neighbor_features = neighbor_features.to(device)
            targets = targets.to(device)
            clusters = clusters.to(device)
            optimizer.zero_grad()
            outputs = model(node_features, neighbor_features)
            regression_loss = mse_loss(outputs["node_scores"], targets)
            classification_loss = ce_loss(outputs["cluster_logits"], clusters)
            loss = regression_loss + float(args.cluster_loss_weight) * classification_loss
            loss.backward()
            optimizer.step()

        validation = _evaluate(model, val_dataset, device=device, batch_size=args.batch_size)
        if validation["node_mse"] < best_val_mse:
            best_val_mse = validation["node_mse"]
            best_state = {key: value.detach().cpu() for key, value in model.state_dict().items()}

    if best_state is not None:
        model.load_state_dict(best_state)
    torch.save(model.state_dict(), output_dir / "model.pt")

    train_metrics = _evaluate(model, train_dataset, device=device, batch_size=args.batch_size)
    val_metrics = _evaluate(model, val_dataset, device=device, batch_size=args.batch_size)
    metadata["train_metrics"] = train_metrics
    metadata["validation"] = val_metrics
    metadata["neighbor_strength_mean_train"] = round(
        float(np.mean(train_dataset["neighbor_weight"])) if train_dataset["neighbor_weight"].size else 0.0,
        6,
    )
    metadata["neighbor_strength_mean_val"] = round(
        float(np.mean(val_dataset["neighbor_weight"])) if val_dataset["neighbor_weight"].size else 0.0,
        6,
    )
    (output_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output_dir": str(output_dir), **metadata}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
