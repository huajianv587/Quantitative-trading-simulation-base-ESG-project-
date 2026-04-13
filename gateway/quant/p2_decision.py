from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from gateway.config import settings
from gateway.quant.models import ResearchSignal
from gateway.quant.p1_stack import signal_to_p1_feature_row
from gateway.utils.logger import get_logger

logger = get_logger(__name__)

P2_STRATEGY_PROFILES: dict[str, dict[str, Any]] = {
    "momentum_leaders": {
        "label": "Momentum Leaders",
        "summary": "Bias toward high-conviction growth with disciplined paper sizing.",
        "max_positions": 4,
        "max_single_name_weight": 0.22,
        "paper_gate_min_decision_score": 0.58,
        "turnover_budget_bps": 110.0,
    },
    "balanced_quality_growth": {
        "label": "Balanced Quality Growth",
        "summary": "Blend quality, ESG consistency, and medium-term trend persistence.",
        "max_positions": 5,
        "max_single_name_weight": 0.20,
        "paper_gate_min_decision_score": 0.54,
        "turnover_budget_bps": 85.0,
    },
    "diversified_barbell": {
        "label": "Diversified Barbell",
        "summary": "Reduce cluster concentration while keeping exposure to top alpha ideas.",
        "max_positions": 6,
        "max_single_name_weight": 0.18,
        "paper_gate_min_decision_score": 0.52,
        "turnover_budget_bps": 70.0,
    },
    "defensive_quality": {
        "label": "Defensive Quality",
        "summary": "Favor resilient, lower-drawdown names when contagion or regime risk rises.",
        "max_positions": 5,
        "max_single_name_weight": 0.16,
        "paper_gate_min_decision_score": 0.50,
        "turnover_budget_bps": 55.0,
    },
}

P2_STRATEGY_ORDER = list(P2_STRATEGY_PROFILES.keys())

P2_STRATEGY_SNAPSHOT_COLUMNS = [
    "breadth_long_ratio",
    "risk_on_ratio",
    "risk_off_ratio",
    "avg_p1_score",
    "avg_expected_return",
    "avg_return_5d",
    "avg_volatility_10d",
    "avg_drawdown_20d",
    "avg_quality",
    "avg_momentum",
    "avg_confidence",
    "avg_graph_centrality",
    "avg_graph_contagion",
    "avg_diversification",
    "sector_concentration",
]

P2_PRIORITY_FEATURE_COLUMNS = [
    "alpha_baseline",
    "fundamental_score",
    "news_sentiment_score",
    "p1_stack_score",
    "predicted_return_1d",
    "predicted_return_5d",
    "predicted_volatility_10d",
    "predicted_drawdown_20d",
    "graph_centrality",
    "graph_contagion_risk",
    "graph_diversification_score",
    "graph_influence_score",
    "confidence",
    "overall_score",
    "risk_score",
    "momentum",
    "quality",
    "value",
    "alternative_data",
    "regime_fit",
    "esg_delta",
    "e_score",
    "s_score",
    "g_score",
    "expected_return",
    "is_risk_on",
    "is_risk_off",
]

P2_MODEL_SPECS: dict[str, dict[str, Any]] = {
    "strategy_classifier": {
        "objective": "multiclass",
        "target_column": "strategy_label",
        "feature_names": P2_STRATEGY_SNAPSHOT_COLUMNS,
    },
    "priority_regressor": {
        "objective": "regression",
        "target_column": "selector_priority_target",
        "feature_names": P2_PRIORITY_FEATURE_COLUMNS,
    },
}


def _bounded(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _resolve_checkpoint_dir(raw_value: str | Path) -> Path:
    path = Path(raw_value)
    if path.is_absolute():
        return path
    return Path(__file__).resolve().parents[2] / path


def _safe_mean(values: list[float]) -> float:
    return float(sum(values) / max(1, len(values)))


def _factor_value(signal: ResearchSignal, name: str, fallback: float = 50.0) -> float:
    for factor in signal.factor_scores:
        if str(factor.name) == name:
            return float(factor.value)
    return fallback


def _normalize_return(value: float | None) -> float:
    return _bounded(((float(value or 0.0) + 0.08) / 0.22), 0.0, 1.0)


def _normalize_risk(value: float | None, ceiling: float) -> float:
    return 1.0 - _bounded(float(value or 0.0) / max(ceiling, 1e-9), 0.0, 1.0)


def _risk_bias(label: str | None) -> float:
    return {"risk_on": 1.0, "neutral": 0.55, "risk_off": 0.15}.get(str(label or "neutral").lower(), 0.55)


def _temperature_probability(value: float, temperature: float) -> float:
    centered = (float(value) - 0.5) / max(float(temperature), 1e-6)
    return _bounded(1.0 / (1.0 + np.exp(-centered)), 0.0, 1.0)


def signal_to_priority_feature_row(signal: ResearchSignal) -> dict[str, float]:
    p1_row = signal_to_p1_feature_row(signal)
    graph_centrality = float(signal.graph_centrality if signal.graph_centrality is not None else 0.35)
    graph_contagion = float(signal.graph_contagion_risk if signal.graph_contagion_risk is not None else 0.28)
    graph_diversification = float(signal.graph_diversification_score if signal.graph_diversification_score is not None else 0.52)
    graph_influence = _bounded(
        0.46 * graph_centrality
        + 0.32 * float(signal.p1_stack_score if signal.p1_stack_score is not None else p1_row["alpha_baseline"])
        + 0.22 * float(signal.confidence),
        0.0,
        1.0,
    )
    regime_label = str(signal.regime_label or "neutral").lower()
    return {
        "alpha_baseline": round(float(signal.alpha_model_score if signal.alpha_model_score is not None else p1_row["alpha_baseline"]), 6),
        "fundamental_score": round(float(signal.fundamental_score if signal.fundamental_score is not None else p1_row["fundamental_score"]), 6),
        "news_sentiment_score": round(float(signal.news_sentiment_score if signal.news_sentiment_score is not None else p1_row["news_sentiment_score"]), 6),
        "p1_stack_score": round(float(signal.p1_stack_score if signal.p1_stack_score is not None else p1_row["alpha_baseline"]), 6),
        "predicted_return_1d": round(float(signal.predicted_return_1d if signal.predicted_return_1d is not None else p1_row["return_1d_proxy"]), 6),
        "predicted_return_5d": round(float(signal.predicted_return_5d if signal.predicted_return_5d is not None else p1_row["return_5d_proxy"]), 6),
        "predicted_volatility_10d": round(float(signal.predicted_volatility_10d if signal.predicted_volatility_10d is not None else p1_row["volatility_20d"] * 0.78), 6),
        "predicted_drawdown_20d": round(float(signal.predicted_drawdown_20d if signal.predicted_drawdown_20d is not None else p1_row["drawdown_20d"]), 6),
        "graph_centrality": round(graph_centrality, 6),
        "graph_contagion_risk": round(graph_contagion, 6),
        "graph_diversification_score": round(graph_diversification, 6),
        "graph_influence_score": round(graph_influence, 6),
        "confidence": round(float(signal.confidence), 6),
        "overall_score": round(float(signal.overall_score), 6),
        "risk_score": round(float(signal.risk_score), 6),
        "momentum": round(float(_factor_value(signal, "momentum")), 6),
        "quality": round(float(_factor_value(signal, "quality")), 6),
        "value": round(float(_factor_value(signal, "value")), 6),
        "alternative_data": round(float(_factor_value(signal, "alternative_data")), 6),
        "regime_fit": round(float(_factor_value(signal, "regime_fit")), 6),
        "esg_delta": round(float(_factor_value(signal, "esg_delta")), 6),
        "e_score": round(float(signal.e_score), 6),
        "s_score": round(float(signal.s_score), 6),
        "g_score": round(float(signal.g_score), 6),
        "expected_return": round(float(signal.expected_return), 6),
        "is_risk_on": 1.0 if regime_label == "risk_on" else 0.0,
        "is_risk_off": 1.0 if regime_label == "risk_off" else 0.0,
    }


def build_strategy_snapshot(signals: list[ResearchSignal], graph_payload: dict[str, Any]) -> dict[str, float]:
    if not signals:
        return {key: 0.0 for key in P2_STRATEGY_SNAPSHOT_COLUMNS}

    long_ratio = sum(1 for signal in signals if signal.action == "long") / max(1, len(signals))
    risk_on_ratio = sum(1 for signal in signals if str(signal.regime_label or "").lower() == "risk_on") / max(1, len(signals))
    risk_off_ratio = sum(1 for signal in signals if str(signal.regime_label or "").lower() == "risk_off") / max(1, len(signals))
    sector_counts = Counter(str(signal.sector or "Unknown") for signal in signals)
    sector_concentration = max(sector_counts.values()) / max(1, len(signals))
    graph_summary = graph_payload.get("summary", {})

    return {
        "breadth_long_ratio": round(long_ratio, 6),
        "risk_on_ratio": round(risk_on_ratio, 6),
        "risk_off_ratio": round(risk_off_ratio, 6),
        "avg_p1_score": round(_safe_mean([float(signal.p1_stack_score or 0.0) for signal in signals]), 6),
        "avg_expected_return": round(_safe_mean([float(signal.expected_return or 0.0) for signal in signals]), 6),
        "avg_return_5d": round(_safe_mean([float(signal.predicted_return_5d or 0.0) for signal in signals]), 6),
        "avg_volatility_10d": round(_safe_mean([float(signal.predicted_volatility_10d or 0.0) for signal in signals]), 6),
        "avg_drawdown_20d": round(_safe_mean([float(signal.predicted_drawdown_20d or 0.0) for signal in signals]), 6),
        "avg_quality": round(_safe_mean([float(_factor_value(signal, "quality")) for signal in signals]), 6),
        "avg_momentum": round(_safe_mean([float(_factor_value(signal, "momentum")) for signal in signals]), 6),
        "avg_confidence": round(_safe_mean([float(signal.confidence or 0.0) for signal in signals]), 6),
        "avg_graph_centrality": round(float(graph_summary.get("average_centrality", 0.0)), 6),
        "avg_graph_contagion": round(float(graph_summary.get("average_contagion_risk", 0.0)), 6),
        "avg_diversification": round(float(graph_summary.get("average_diversification_score", 0.0)), 6),
        "sector_concentration": round(sector_concentration, 6),
    }


class GraphNeuralRuntime:
    def __init__(self, checkpoint_dir: str | Path | None = None) -> None:
        configured = checkpoint_dir or getattr(
            settings,
            "P2_GRAPH_CHECKPOINT_DIR",
            "model-serving/checkpoint/p2_graph",
        )
        self.enabled = bool(getattr(settings, "P2_DECISION_STACK_ENABLED", True))
        self.checkpoint_dir = _resolve_checkpoint_dir(configured)
        self.metadata: dict[str, Any] = {}
        self._torch = None
        self._device = "cpu"
        self._model = None
        self._feature_names = list(P2_PRIORITY_FEATURE_COLUMNS)
        self._cluster_labels = ["defensive", "growth", "balanced", "crowded"]
        self._load()

    def available(self) -> bool:
        return self.enabled and self._model is not None

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "available": self.available(),
            "checkpoint_dir": str(self.checkpoint_dir),
            "model_name": self.metadata.get("model_name", ""),
            "generated_at": self.metadata.get("generated_at"),
            "feature_names": list(self._feature_names),
            "cluster_labels": list(self._cluster_labels),
            "device": self._device,
        }

    def refine(
        self,
        signals: list[ResearchSignal],
        *,
        neighbor_map: dict[str, list[tuple[str, float]]],
        heuristic_nodes: list[dict[str, Any]],
    ) -> dict[str, dict[str, Any]] | None:
        if not self.available() or not signals:
            return None
        torch = self._torch
        node_lookup = {item["symbol"]: item for item in heuristic_nodes}
        vectors: list[np.ndarray] = []
        for signal in signals:
            feature_row = signal_to_priority_feature_row(signal)
            vectors.append(
                np.asarray([float(feature_row.get(name, 0.0)) for name in self._feature_names], dtype=np.float32)
            )
        feature_matrix = np.stack(vectors).astype(np.float32)
        symbols = [signal.symbol for signal in signals]
        index_by_symbol = {symbol: index for index, symbol in enumerate(symbols)}
        neighbor_features: list[np.ndarray] = []
        neighbor_strengths: list[float] = []
        for symbol in symbols:
            neighbors = neighbor_map.get(symbol, [])
            if not neighbors:
                neighbor_features.append(np.zeros(feature_matrix.shape[1], dtype=np.float32))
                neighbor_strengths.append(0.0)
                continue
            weighted = np.zeros(feature_matrix.shape[1], dtype=np.float32)
            total = 0.0
            for neighbor_symbol, weight in neighbors:
                if neighbor_symbol not in index_by_symbol:
                    continue
                weighted += feature_matrix[index_by_symbol[neighbor_symbol]] * float(weight)
                total += float(weight)
            if total <= 0:
                neighbor_features.append(np.zeros(feature_matrix.shape[1], dtype=np.float32))
                neighbor_strengths.append(0.0)
            else:
                neighbor_features.append(weighted / total)
                neighbor_strengths.append(total / max(1, len(neighbors)))
        neighbor_matrix = np.stack(neighbor_features).astype(np.float32)
        with torch.no_grad():
            outputs = self._model(
                torch.tensor(feature_matrix, dtype=torch.float32, device=self._device),
                torch.tensor(neighbor_matrix, dtype=torch.float32, device=self._device),
            )
        node_scores = outputs["node_scores"].detach().cpu().numpy()
        cluster_logits = outputs["cluster_logits"].detach().cpu().numpy()
        refined: dict[str, dict[str, Any]] = {}
        for index, signal in enumerate(signals):
            heuristic = node_lookup.get(signal.symbol, {})
            centrality = round(_bounded(float(node_scores[index][0]), 0.0, 1.0), 6)
            contagion = round(_bounded(float(node_scores[index][1]), 0.0, 1.0), 6)
            diversification = round(_bounded(float(node_scores[index][2]), 0.0, 1.0), 6)
            influence = round(_bounded(float(node_scores[index][3]), 0.0, 1.0), 6)
            cluster_probs = np.exp(cluster_logits[index] - np.max(cluster_logits[index]))
            cluster_probs = cluster_probs / max(np.sum(cluster_probs), 1e-9)
            cluster_index = int(np.argmax(cluster_probs))
            refined[signal.symbol] = {
                "graph_cluster": f"gnn::{self._cluster_labels[cluster_index]}",
                "graph_neighbors": heuristic.get("neighbors", []),
                "graph_centrality": round(0.55 * centrality + 0.45 * float(heuristic.get("centrality", 0.0)), 6),
                "graph_contagion_risk": round(0.60 * contagion + 0.40 * float(heuristic.get("contagion_risk", 0.0)), 6),
                "graph_diversification_score": round(0.60 * diversification + 0.40 * float(heuristic.get("diversification_score", 0.0)), 6),
                "graph_influence_score": round(0.62 * influence + 0.38 * float(heuristic.get("influence_score", 0.0)), 6),
                "graph_engine": "gnn_graph_runtime",
                "graph_model_version": str(self.metadata.get("generated_at") or self.metadata.get("model_name") or "gnn"),
                "graph_neighbor_strength": round(float(neighbor_strengths[index]), 6),
            }
        return refined

    def _load(self) -> None:
        if not self.enabled or not self.checkpoint_dir.exists():
            return
        metadata_path = self.checkpoint_dir / "metadata.json"
        model_path = self.checkpoint_dir / "model.pt"
        if not metadata_path.exists() or not model_path.exists():
            return
        try:
            import torch
            from torch import nn
        except Exception as exc:
            logger.warning(f"P2 GNN runtime unavailable because PyTorch is missing: {exc}")
            return

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

        try:
            self.metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            self._feature_names = [str(item) for item in self.metadata.get("feature_names", P2_PRIORITY_FEATURE_COLUMNS)]
            self._cluster_labels = [str(item) for item in self.metadata.get("cluster_labels", self._cluster_labels)]
            self._torch = torch
            self._device = "cuda" if torch.cuda.is_available() else "cpu"
            hidden_size = int(self.metadata.get("hidden_size", 64) or 64)
            model = GraphSAGERefiner(len(self._feature_names), hidden_size, len(self._cluster_labels)).to(self._device)
            state_dict = torch.load(model_path, map_location=self._device)
            model.load_state_dict(state_dict)
            model.eval()
            self._model = model
        except Exception as exc:
            logger.warning(f"Failed to load P2 GNN checkpoint from {self.checkpoint_dir}: {exc}")
            self.metadata = {}
            self._model = None


class ContextualBanditRuntime:
    def __init__(self, checkpoint_dir: str | Path | None = None) -> None:
        self.enabled = bool(getattr(settings, "P2_BANDIT_ENABLED", True))
        configured = checkpoint_dir or getattr(
            settings,
            "P2_BANDIT_CHECKPOINT_DIR",
            "model-serving/checkpoint/contextual_bandit",
        )
        self.checkpoint_dir = _resolve_checkpoint_dir(configured)
        self.metadata: dict[str, Any] = {}
        self.policy: dict[str, dict[str, np.ndarray]] = {}
        self._load()

    def available(self) -> bool:
        return self.enabled and bool(self.policy)

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "available": self.available(),
            "checkpoint_dir": str(self.checkpoint_dir),
            "arms": list(self.metadata.get("arms", [])),
            "alpha": self.metadata.get("alpha"),
            "validation": dict(self.metadata.get("validation", {})),
        }

    def select(self, snapshot: dict[str, float]) -> dict[str, Any]:
        if not self.available():
            return {
                "available": False,
                "selected_strategy": None,
                "confidence": 0.0,
                "arm_scores": {},
                "size_multiplier": 1.0,
                "execution_style": "balanced_day",
                "execution_delay_seconds": 0,
            }
        feature_names = [str(item) for item in self.metadata.get("feature_names", P2_STRATEGY_SNAPSHOT_COLUMNS)]
        context = np.asarray([float(snapshot.get(name, 0.0)) for name in feature_names], dtype=np.float64)
        alpha = float(self.metadata.get("alpha", 0.6) or 0.6)
        arm_scores: dict[str, float] = {}
        for arm, payload in self.policy.items():
            try:
                inv = np.linalg.inv(payload["A"])
                theta = inv @ payload["b"]
                arm_scores[arm] = float(theta @ context + alpha * np.sqrt(context @ inv @ context))
            except Exception as exc:
                logger.warning(f"Failed to score contextual bandit arm {arm}: {exc}")
        if not arm_scores:
            return {
                "available": False,
                "selected_strategy": None,
                "confidence": 0.0,
                "arm_scores": {},
                "size_multiplier": 1.0,
                "execution_style": "balanced_day",
                "execution_delay_seconds": 0,
            }
        values = list(arm_scores.values())
        lower = min(values)
        upper = max(values)
        span = max(upper - lower, 1e-9)
        normalized = {arm: _bounded((score - lower) / span, 0.0, 1.0) for arm, score in arm_scores.items()}
        selected = max(normalized.items(), key=lambda item: item[1])[0]
        confidence = float(normalized[selected])
        risk_on_ratio = float(snapshot.get("risk_on_ratio", 0.0))
        risk_off_ratio = float(snapshot.get("risk_off_ratio", 0.0))
        contagion = float(snapshot.get("avg_graph_contagion", 0.0))
        breadth = float(snapshot.get("breadth_long_ratio", 0.0))
        size_multiplier = _bounded(
            0.82
            + confidence * 0.34
            + risk_on_ratio * 0.14
            + breadth * 0.08
            - risk_off_ratio * 0.18
            - contagion * 0.16,
            float(getattr(settings, "P2_BANDIT_SIZE_MULTIPLIER_MIN", 0.65) or 0.65),
            float(getattr(settings, "P2_BANDIT_SIZE_MULTIPLIER_MAX", 1.35) or 1.35),
        )
        if risk_on_ratio >= 0.48 and confidence >= 0.68:
            execution_style = "aggressive_open"
            delay_seconds = 0
        elif contagion >= 0.56 or risk_off_ratio >= 0.42:
            execution_style = "patient_limit"
            delay_seconds = int(
                float(getattr(settings, "P2_BANDIT_EXECUTION_DELAY_MAX_SECONDS", 900) or 900)
                * _bounded(0.65 + contagion * 0.35, 0.4, 1.0)
            )
        elif breadth < 0.34:
            execution_style = "staggered"
            delay_seconds = int(
                float(getattr(settings, "P2_BANDIT_EXECUTION_DELAY_MAX_SECONDS", 900) or 900)
                * 0.45
            )
        else:
            execution_style = "balanced_day"
            delay_seconds = int(
                float(getattr(settings, "P2_BANDIT_EXECUTION_DELAY_MAX_SECONDS", 900) or 900)
                * 0.15
            )
        return {
            "available": True,
            "selected_strategy": selected,
            "confidence": round(confidence, 6),
            "arm_scores": {arm: round(score, 6) for arm, score in normalized.items()},
            "size_multiplier": round(float(size_multiplier), 6),
            "execution_style": execution_style,
            "execution_delay_seconds": int(delay_seconds),
        }

    def _load(self) -> None:
        if not self.enabled or not self.checkpoint_dir.exists():
            return
        metadata_path = self.checkpoint_dir / "metadata.json"
        policy_path = self.checkpoint_dir / "policy.json"
        if not metadata_path.exists() or not policy_path.exists():
            return
        try:
            self.metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            raw_policy = json.loads(policy_path.read_text(encoding="utf-8"))
            self.policy = {
                arm: {
                    "A": np.asarray(payload.get("A", []), dtype=np.float64),
                    "b": np.asarray(payload.get("b", []), dtype=np.float64),
                }
                for arm, payload in raw_policy.items()
            }
        except Exception as exc:
            logger.warning(f"Failed to load contextual bandit checkpoint from {self.checkpoint_dir}: {exc}")
            self.metadata = {}
            self.policy = {}


class RelationshipGraphRuntime:
    def __init__(self) -> None:
        self.enabled = bool(getattr(settings, "P2_DECISION_STACK_ENABLED", True))
        self.edge_threshold = float(getattr(settings, "P2_GRAPH_EDGE_THRESHOLD", 0.58) or 0.58)
        self.gnn = GraphNeuralRuntime()

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "available": self.enabled,
            "engine": "gnn_graph_runtime" if self.gnn.available() else "heuristic_relationship_graph",
            "edge_threshold": self.edge_threshold,
            "gnn": self.gnn.status(),
        }

    def analyze(self, signals: list[ResearchSignal]) -> dict[str, Any]:
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []
        if not signals:
            return {
                "nodes": nodes,
                "edges": edges,
                "summary": {
                    "node_count": 0,
                    "edge_count": 0,
                    "density": 0.0,
                    "average_centrality": 0.0,
                    "average_contagion_risk": 0.0,
                    "average_diversification_score": 0.0,
                    "cluster_count": 0,
                    "top_contagion_symbols": [],
                    "topology_warnings": [],
                },
                "signal_updates": {},
            }

        neighbor_map: dict[str, list[tuple[str, float]]] = {signal.symbol: [] for signal in signals}
        for index, left in enumerate(signals):
            for right in signals[index + 1 :]:
                weight, relation = self._similarity(left, right)
                if weight < self.edge_threshold:
                    continue
                rounded = round(weight, 6)
                edges.append(
                    {
                        "source": left.symbol,
                        "target": right.symbol,
                        "weight": rounded,
                        "relationship": relation,
                    }
                )
                neighbor_map[left.symbol].append((right.symbol, rounded))
                neighbor_map[right.symbol].append((left.symbol, rounded))

        signal_updates: dict[str, dict[str, Any]] = {}
        centralities: list[float] = []
        contagion_scores: list[float] = []
        diversification_scores: list[float] = []
        cluster_counts: Counter[str] = Counter()

        for signal in signals:
            neighbors = neighbor_map.get(signal.symbol, [])
            degree = len(neighbors)
            centrality = round(sum(weight for _, weight in neighbors) / max(1, len(signals) - 1), 6)
            same_sector_ratio = 0.0
            if neighbors:
                same_sector_ratio = sum(
                    1
                    for symbol, _ in neighbors
                    if next((item.sector for item in signals if item.symbol == symbol), "") == signal.sector
                ) / max(1, degree)
            predicted_drawdown = float(signal.predicted_drawdown_20d or 0.10)
            risk_component = float(signal.risk_score) / 100.0
            regime_component = {"risk_off": 0.9, "neutral": 0.55, "risk_on": 0.25}.get(
                str(signal.regime_label or "neutral").lower(),
                0.55,
            )
            contagion = round(
                _bounded(
                    0.35 * centrality
                    + 0.27 * risk_component
                    + 0.22 * predicted_drawdown
                    + 0.16 * regime_component,
                    0.0,
                    1.0,
                ),
                6,
            )
            diversification = round(
                _bounded(1.0 - centrality * 0.72 - same_sector_ratio * 0.18, 0.0, 1.0),
                6,
            )
            p1_score = float(signal.p1_stack_score if signal.p1_stack_score is not None else signal.alpha_model_score or 0.5)
            influence = round(
                _bounded(
                    0.44 * p1_score
                    + 0.28 * centrality
                    + 0.16 * float(signal.confidence)
                    + 0.12 * _normalize_return(signal.predicted_return_5d),
                    0.0,
                    1.0,
                ),
                6,
            )
            cluster = f"{str(signal.sector or 'custom').lower().replace(' ', '_')}::{str(signal.regime_label or 'neutral').lower()}"
            cluster_counts[cluster] += 1
            top_neighbors = [symbol for symbol, _ in sorted(neighbors, key=lambda item: item[1], reverse=True)[:3]]
            nodes.append(
                {
                    "symbol": signal.symbol,
                    "cluster": cluster,
                    "degree": degree,
                    "centrality": centrality,
                    "contagion_risk": contagion,
                    "diversification_score": diversification,
                    "influence_score": influence,
                    "neighbors": top_neighbors,
                }
            )
            signal_updates[signal.symbol] = {
                "graph_cluster": cluster,
                "graph_neighbors": top_neighbors,
                "graph_centrality": centrality,
                "graph_contagion_risk": contagion,
                "graph_diversification_score": diversification,
                "graph_engine": "heuristic_relationship_graph",
                "graph_model_version": None,
            }
            centralities.append(centrality)
            contagion_scores.append(contagion)
            diversification_scores.append(diversification)

        possible_edges = max(1, len(signals) * (len(signals) - 1) / 2)
        density = round(len(edges) / possible_edges, 6)
        top_contagion = sorted(nodes, key=lambda item: (-float(item["contagion_risk"]), -float(item["centrality"])))[:3]
        warnings: list[str] = []
        if density >= 0.68:
            warnings.append("Relationship graph is dense; sector and factor crowding are elevated.")
        if any(item["contagion_risk"] >= 0.62 for item in nodes):
            warnings.append("At least one symbol sits above the P2 contagion watch threshold.")
        if max(cluster_counts.values(), default=0) / max(1, len(signals)) >= 0.55:
            warnings.append("Cluster concentration is high; diversification routing should stay active.")

        if self.gnn.available():
            gnn_updates = self.gnn.refine(
                signals,
                neighbor_map=neighbor_map,
                heuristic_nodes=nodes,
            )
            if gnn_updates:
                for node in nodes:
                    update = gnn_updates.get(node["symbol"])
                    if not update:
                        continue
                    node.update(
                        {
                            "cluster": update.get("graph_cluster", node.get("cluster")),
                            "centrality": update.get("graph_centrality", node.get("centrality")),
                            "contagion_risk": update.get("graph_contagion_risk", node.get("contagion_risk")),
                            "diversification_score": update.get("graph_diversification_score", node.get("diversification_score")),
                            "influence_score": update.get("graph_influence_score", node.get("influence_score")),
                            "graph_engine": update.get("graph_engine"),
                            "graph_model_version": update.get("graph_model_version"),
                        }
                    )
                signal_updates.update(gnn_updates)
                centralities = [float(item.get("centrality", 0.0)) for item in nodes]
                contagion_scores = [float(item.get("contagion_risk", 0.0)) for item in nodes]
                diversification_scores = [float(item.get("diversification_score", 0.0)) for item in nodes]

        return {
            "nodes": nodes,
            "edges": edges,
            "summary": {
                "node_count": len(nodes),
                "edge_count": len(edges),
                "density": density,
                "average_centrality": round(_safe_mean(centralities), 6),
                "average_contagion_risk": round(_safe_mean(contagion_scores), 6),
                "average_diversification_score": round(_safe_mean(diversification_scores), 6),
                "cluster_count": len(cluster_counts),
                "cluster_distribution": dict(cluster_counts),
                "top_contagion_symbols": top_contagion,
                "topology_warnings": warnings,
                "graph_engine": "gnn_graph_runtime" if self.gnn.available() else "heuristic_relationship_graph",
                "graph_model_version": self.gnn.metadata.get("generated_at") if self.gnn.available() else None,
            },
            "signal_updates": signal_updates,
        }

    @staticmethod
    def _similarity(left: ResearchSignal, right: ResearchSignal) -> tuple[float, str]:
        sector_bonus = 0.30 if left.sector == right.sector else 0.0
        industry_bonus = 0.12 if left.company_name != right.company_name and left.sector == right.sector else 0.0
        overall_similarity = 1.0 - min(abs(float(left.overall_score) - float(right.overall_score)) / 100.0, 1.0)
        p1_left = float(left.p1_stack_score if left.p1_stack_score is not None else left.alpha_model_score or 0.5)
        p1_right = float(right.p1_stack_score if right.p1_stack_score is not None else right.alpha_model_score or 0.5)
        p1_similarity = 1.0 - min(abs(p1_left - p1_right), 1.0)
        regime_bonus = 0.10 if str(left.regime_label or "neutral").lower() == str(right.regime_label or "neutral").lower() else 0.0
        return_similarity = 1.0 - min(abs(float(left.expected_return) - float(right.expected_return)) / 0.2, 1.0)
        weight = _bounded(
            sector_bonus
            + industry_bonus
            + 0.20 * overall_similarity
            + 0.18 * p1_similarity
            + regime_bonus
            + 0.10 * return_similarity,
            0.0,
            1.0,
        )
        relation = "peer_cluster" if left.sector == right.sector else "factor_similarity"
        return weight, relation


class StrategySelectorRuntime:
    def __init__(self) -> None:
        self.enabled = bool(getattr(settings, "P2_DECISION_STACK_ENABLED", True))
        self.decision_min_score = float(getattr(settings, "P2_DECISION_MIN_SCORE", 0.54) or 0.54)
        self.graph_contagion_limit = float(getattr(settings, "P2_GRAPH_CONTAGION_LIMIT", 0.62) or 0.62)
        self.bandit_blend_weight = float(getattr(settings, "P2_BANDIT_BLEND_WEIGHT", 0.4) or 0.4)
        self.regime_mixture_enabled = bool(getattr(settings, "P2_REGIME_MIXTURE_ENABLED", True))
        self.calibration_enabled = bool(getattr(settings, "P2_CALIBRATION_ENABLED", True))
        self.decision_temperature = float(getattr(settings, "P2_DECISION_CONFIDENCE_TEMPERATURE", 0.24) or 0.24)
        self.checkpoint_root = _resolve_checkpoint_dir(
            getattr(settings, "P2_SELECTOR_CHECKPOINT_DIR", "model-serving/checkpoint/p2_selector")
        )
        self.models: dict[str, Any] = {}
        self.metadata: dict[str, dict[str, Any]] = {}
        self.suite_manifest: dict[str, Any] = {}
        self.bandit = ContextualBanditRuntime()
        self._load()

    def available(self) -> bool:
        return self.enabled and (bool(self.models) or self.bandit.available())

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "available": self.available(),
            "checkpoint_root": str(self.checkpoint_root),
            "loaded_models": len(self.models),
            "expected_models": len(P2_MODEL_SPECS),
            "suite_manifest": self.suite_manifest,
            "bandit": self.bandit.status(),
            "regime_mixture_enabled": self.regime_mixture_enabled,
            "calibration_enabled": self.calibration_enabled,
            "decision_temperature": self.decision_temperature,
            "strategies": [
                {
                    "key": key,
                    "label": profile["label"],
                    "summary": profile["summary"],
                    "max_positions": profile["max_positions"],
                    "max_single_name_weight": profile["max_single_name_weight"],
                }
                for key, profile in P2_STRATEGY_PROFILES.items()
            ],
        }

    def select(self, signals: list[ResearchSignal], graph_payload: dict[str, Any]) -> tuple[list[ResearchSignal], dict[str, Any]]:
        if not signals:
            return [], {
                "selected_strategy": "balanced_quality_growth",
                "selected_label": P2_STRATEGY_PROFILES["balanced_quality_growth"]["label"],
                "selector_confidence": 0.0,
                "market_regime": "neutral",
                "snapshot": {key: 0.0 for key in P2_STRATEGY_SNAPSHOT_COLUMNS},
                "deployment_policy": dict(P2_STRATEGY_PROFILES["balanced_quality_growth"]),
                "blockers": ["No signals were available for P2 selection."],
            }

        snapshot = build_strategy_snapshot(signals, graph_payload)
        strategy_key, selector_confidence, strategy_source, bandit_payload, blended_scores = self._select_strategy(snapshot)
        profile = P2_STRATEGY_PROFILES[strategy_key]
        priorities = self._score_priorities(signals, strategy_key)
        market_regime = self._market_regime_from_snapshot(snapshot)
        alpha_engine = self._alpha_engine_for_regime(strategy_key, market_regime)

        enriched: list[ResearchSignal] = []
        blockers: list[str] = []
        for signal, selector_priority in zip(signals, priorities):
            graph_centrality = float(signal.graph_centrality or 0.35)
            graph_contagion = float(signal.graph_contagion_risk or 0.28)
            graph_diversification = float(signal.graph_diversification_score or 0.52)
            p1_score = float(signal.p1_stack_score if signal.p1_stack_score is not None else signal.alpha_model_score or 0.5)
            decision_score = self._decision_score(
                strategy_key=strategy_key,
                p1_score=p1_score,
                selector_priority=selector_priority,
                signal=signal,
                graph_centrality=graph_centrality,
                graph_contagion=graph_contagion,
                graph_diversification=graph_diversification,
            )
            decision_confidence = round(
                self._calibrate_decision_confidence(
                    selector_confidence=selector_confidence,
                    signal_confidence=float(signal.confidence),
                    p1_score=p1_score,
                ),
                6,
            )
            action = signal.action
            if action == "long" and (
                decision_score < max(self.decision_min_score, float(profile["paper_gate_min_decision_score"]))
                or graph_contagion > self.graph_contagion_limit
            ):
                action = "neutral"

            enriched.append(
                signal.model_copy(
                    update={
                        "action": action,
                        "selector_strategy": strategy_key,
                        "selector_priority_score": round(selector_priority, 6),
                        "bandit_strategy": bandit_payload.get("selected_strategy"),
                        "bandit_confidence": round(float(bandit_payload.get("confidence", 0.0)), 6),
                        "bandit_size_multiplier": round(float(bandit_payload.get("size_multiplier", 1.0)), 6),
                        "bandit_execution_style": bandit_payload.get("execution_style"),
                        "bandit_execution_delay_seconds": int(bandit_payload.get("execution_delay_seconds", 0) or 0),
                        "decision_score": round(decision_score, 6),
                        "decision_confidence": decision_confidence,
                        "alpha_engine": alpha_engine,
                        "signal_source": "p2_decision_stack" if self.available() else "p2_decision_heuristic",
                    }
                )
            )

        if snapshot["risk_off_ratio"] >= 0.45:
            blockers.append("Risk-off ratio remains elevated; route only the highest-conviction paper orders.")
        if float(graph_payload.get("summary", {}).get("average_contagion_risk", 0.0)) >= self.graph_contagion_limit:
            blockers.append("Average contagion risk remains above the P2 watch threshold.")
        if sum(1 for signal in enriched if signal.action == "long") == 0:
            blockers.append("No symbols cleared the P2 decision score and contagion filters.")

        ranked = sorted(
            enriched,
            key=lambda item: (
                item.action != "long",
                -(item.decision_score or 0.0),
                -(item.selector_priority_score or 0.0),
                -(item.p1_stack_score or 0.0),
                -item.confidence,
            ),
        )
        return ranked, {
            "selected_strategy": strategy_key,
            "selected_label": profile["label"],
            "selector_confidence": round(selector_confidence, 6),
            "strategy_source": strategy_source,
            "bandit": bandit_payload,
            "blended_strategy_scores": blended_scores,
            "market_regime": market_regime,
            "alpha_engine": alpha_engine,
            "snapshot": snapshot,
            "deployment_policy": dict(profile),
            "blockers": blockers,
        }

    def _select_strategy(self, snapshot: dict[str, float]) -> tuple[str, float, str, dict[str, Any], dict[str, float]]:
        model = self.models.get("strategy_classifier")
        metadata = self.metadata.get("strategy_classifier", {})
        base_scores = {strategy: 0.1 for strategy in P2_STRATEGY_PROFILES}
        source = "heuristic"
        if model is not None:
            frame = pd.DataFrame([{name: snapshot.get(name, 0.0) for name in P2_STRATEGY_SNAPSHOT_COLUMNS}]).fillna(0.0)
            feature_names = [str(item) for item in metadata.get("feature_names", P2_STRATEGY_SNAPSHOT_COLUMNS)]
            try:
                if hasattr(model, "predict_proba"):
                    probabilities = model.predict_proba(frame[feature_names])[0]
                    classes = [str(item) for item in metadata.get("classes", P2_STRATEGY_ORDER)]
                    for index, label in enumerate(classes):
                        if label in P2_STRATEGY_PROFILES:
                            base_scores[label] = float(probabilities[index])
                    source = str(metadata.get("backend", "model"))
                predicted = str(model.predict(frame[feature_names])[0])
                if predicted in P2_STRATEGY_PROFILES:
                    base_scores[predicted] = max(base_scores.get(predicted, 0.0), 0.68)
                    source = str(metadata.get("backend", "model"))
            except Exception as exc:
                logger.warning(f"Failed to score P2 strategy classifier, falling back to heuristics: {exc}")

        if source == "heuristic":
            risk_off = snapshot["risk_off_ratio"]
            risk_on = snapshot["risk_on_ratio"]
            avg_drawdown = snapshot["avg_drawdown_20d"]
            avg_contagion = snapshot["avg_graph_contagion"]
            sector_concentration = snapshot["sector_concentration"]
            avg_return = snapshot["avg_return_5d"]
            base_scores = {
                "defensive_quality": _bounded(
                    0.25 + 0.42 * max(risk_off, avg_contagion) + 0.20 * avg_drawdown,
                    0.0,
                    1.0,
                ),
                "momentum_leaders": _bounded(
                    0.20 + 0.45 * risk_on + 0.20 * max(avg_return, 0.0) + 0.15 * snapshot["breadth_long_ratio"],
                    0.0,
                    1.0,
                ),
                "diversified_barbell": _bounded(
                    0.18 + 0.35 * sector_concentration + 0.30 * snapshot["avg_graph_centrality"] + 0.15 * avg_contagion,
                    0.0,
                    1.0,
                ),
                "balanced_quality_growth": _bounded(
                    0.26 + 0.34 * snapshot["avg_p1_score"] + 0.16 * snapshot["avg_quality"] / 100.0,
                    0.0,
                    1.0,
                ),
            }

        if self.regime_mixture_enabled:
            regime_bias = {
                "momentum_leaders": 0.0,
                "balanced_quality_growth": 0.0,
                "diversified_barbell": 0.0,
                "defensive_quality": 0.0,
            }
            if snapshot["risk_off_ratio"] >= 0.40 or snapshot["avg_drawdown_20d"] >= 0.14:
                regime_bias["defensive_quality"] += 0.18
                regime_bias["diversified_barbell"] += 0.08
                regime_bias["momentum_leaders"] -= 0.08
            elif snapshot["risk_on_ratio"] >= 0.42 and snapshot["avg_return_5d"] >= 0.01:
                regime_bias["momentum_leaders"] += 0.16
                regime_bias["balanced_quality_growth"] += 0.05
                regime_bias["defensive_quality"] -= 0.06
            else:
                regime_bias["balanced_quality_growth"] += 0.08
            base_scores = {
                strategy: round(_bounded(score + regime_bias.get(strategy, 0.0), 0.0, 1.0), 6)
                for strategy, score in base_scores.items()
            }

        bandit_payload = self.bandit.select(snapshot)
        blended_scores = dict(base_scores)
        if bandit_payload.get("available"):
            bandit_weight = _bounded(self.bandit_blend_weight, 0.0, 0.95)
            bandit_scores = {
                strategy: float(bandit_payload.get("arm_scores", {}).get(strategy, 0.0))
                for strategy in P2_STRATEGY_PROFILES
            }
            blended_scores = {
                strategy: round(
                    (1.0 - bandit_weight) * float(base_scores.get(strategy, 0.0))
                    + bandit_weight * bandit_scores.get(strategy, 0.0),
                    6,
                )
                for strategy in P2_STRATEGY_PROFILES
            }
            source = f"{source}+bandit"

        selected_strategy = max(blended_scores.items(), key=lambda item: item[1])[0]
        return selected_strategy, float(blended_scores[selected_strategy]), source, bandit_payload, blended_scores

    def _alpha_engine_for_regime(self, strategy_key: str, market_regime: str) -> str:
        if not self.regime_mixture_enabled:
            return strategy_key
        if market_regime == "risk_off":
            return "defensive_alpha_engine"
        if market_regime == "risk_on" and strategy_key == "momentum_leaders":
            return "momentum_alpha_engine"
        if strategy_key == "diversified_barbell":
            return "barbell_alpha_engine"
        return "balanced_quality_engine"

    def _calibrate_decision_confidence(self, *, selector_confidence: float, signal_confidence: float, p1_score: float) -> float:
        baseline = 0.54 * float(selector_confidence) + 0.28 * float(signal_confidence) + 0.18 * float(p1_score)
        if not self.calibration_enabled:
            return _bounded(baseline, 0.0, 1.0)
        return _temperature_probability(baseline, self.decision_temperature)

    def _score_priorities(self, signals: list[ResearchSignal], strategy_key: str) -> list[float]:
        model = self.models.get("priority_regressor")
        metadata = self.metadata.get("priority_regressor", {})
        frame = pd.DataFrame([signal_to_priority_feature_row(signal) for signal in signals]).fillna(0.0)
        if model is not None:
            feature_names = [str(item) for item in metadata.get("feature_names", P2_PRIORITY_FEATURE_COLUMNS)]
            try:
                raw = [float(value) for value in model.predict(frame[feature_names])]
                lower = float(metadata.get("prediction_min", min(raw) if raw else 0.0))
                upper = float(metadata.get("prediction_max", max(raw) if raw else 1.0))
                span = max(upper - lower, 1e-9)
                return [_bounded((value - lower) / span, 0.0, 1.0) for value in raw]
            except Exception as exc:
                logger.warning(f"Failed to score P2 priority regressor, falling back to heuristics: {exc}")

        scores: list[float] = []
        for signal in signals:
            row = signal_to_priority_feature_row(signal)
            if strategy_key == "momentum_leaders":
                score = (
                    0.30 * _normalize_return(row["predicted_return_5d"])
                    + 0.22 * _normalize_return(row["predicted_return_1d"])
                    + 0.18 * (row["news_sentiment_score"] / 100.0)
                    + 0.18 * row["p1_stack_score"]
                    + 0.12 * _risk_bias(signal.regime_label)
                )
            elif strategy_key == "defensive_quality":
                score = (
                    0.26 * (row["fundamental_score"] / 100.0)
                    + 0.22 * _normalize_risk(row["predicted_drawdown_20d"], 0.35)
                    + 0.18 * _normalize_risk(row["predicted_volatility_10d"], 0.45)
                    + 0.18 * (row["g_score"] / 100.0)
                    + 0.16 * row["graph_diversification_score"]
                )
            elif strategy_key == "diversified_barbell":
                score = (
                    0.24 * row["p1_stack_score"]
                    + 0.20 * row["graph_diversification_score"]
                    + 0.18 * (row["fundamental_score"] / 100.0)
                    + 0.18 * _normalize_return(row["predicted_return_5d"])
                    + 0.20 * _normalize_risk(row["graph_contagion_risk"], 1.0)
                )
            else:
                score = (
                    0.26 * row["p1_stack_score"]
                    + 0.20 * (row["fundamental_score"] / 100.0)
                    + 0.18 * _normalize_return(row["predicted_return_5d"])
                    + 0.18 * _normalize_risk(row["predicted_drawdown_20d"], 0.35)
                    + 0.18 * row["graph_diversification_score"]
                )
            scores.append(round(_bounded(score, 0.0, 1.0), 6))
        return scores

    def _decision_score(
        self,
        *,
        strategy_key: str,
        p1_score: float,
        selector_priority: float,
        signal: ResearchSignal,
        graph_centrality: float,
        graph_contagion: float,
        graph_diversification: float,
    ) -> float:
        return_component = _normalize_return(signal.predicted_return_5d if signal.predicted_return_5d is not None else signal.expected_return)
        risk_component = (
            _normalize_risk(signal.predicted_volatility_10d, 0.45)
            + _normalize_risk(signal.predicted_drawdown_20d, 0.35)
        ) / 2.0
        profile_bias = {
            "momentum_leaders": 0.10 * _risk_bias(signal.regime_label),
            "balanced_quality_growth": 0.08,
            "diversified_barbell": 0.10 * graph_diversification,
            "defensive_quality": 0.12 * risk_component,
        }.get(strategy_key, 0.08)
        score = (
            0.34 * _bounded(p1_score, 0.0, 1.0)
            + 0.28 * _bounded(selector_priority, 0.0, 1.0)
            + 0.14 * return_component
            + 0.12 * risk_component
            + 0.08 * graph_diversification
            + 0.06 * _bounded(graph_centrality, 0.0, 1.0)
            + profile_bias
            - 0.18 * _bounded(graph_contagion, 0.0, 1.0)
        )
        return round(_bounded(score, 0.0, 1.0), 6)

    @staticmethod
    def _market_regime_from_snapshot(snapshot: dict[str, float]) -> str:
        if snapshot["risk_off_ratio"] >= 0.42:
            return "risk_off"
        if snapshot["risk_on_ratio"] >= 0.40 and snapshot["avg_return_5d"] >= 0.01:
            return "risk_on"
        return "neutral"

    def _load(self) -> None:
        if not self.enabled or not self.checkpoint_root.exists():
            return
        manifest_path = self.checkpoint_root / "suite_manifest.json"
        if manifest_path.exists():
            try:
                self.suite_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except Exception as exc:
                logger.warning(f"Failed to load P2 suite manifest from {manifest_path}: {exc}")

        try:
            import joblib
        except Exception as exc:
            logger.warning(f"P2 selector runtime disabled because joblib is unavailable: {exc}")
            return

        for model_key in P2_MODEL_SPECS:
            metadata_path = self.checkpoint_root / model_key / "metadata.json"
            model_path = self.checkpoint_root / model_key / "model.joblib"
            if not metadata_path.exists() or not model_path.exists():
                continue
            try:
                self.metadata[model_key] = json.loads(metadata_path.read_text(encoding="utf-8"))
                self.models[model_key] = joblib.load(model_path)
            except Exception as exc:
                logger.warning(f"Failed to load P2 checkpoint {model_key} from {self.checkpoint_root / model_key}: {exc}")
                self.metadata.pop(model_key, None)
                self.models.pop(model_key, None)


class P2DecisionStackRuntime:
    def __init__(self) -> None:
        self.enabled = bool(getattr(settings, "P2_DECISION_STACK_ENABLED", True))
        self.graph = RelationshipGraphRuntime()
        self.selector = StrategySelectorRuntime()

    def available(self) -> bool:
        return self.enabled

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "available": self.available(),
            "graph": self.graph.status(),
            "selector": self.selector.status(),
        }

    def apply(self, signals: list[ResearchSignal]) -> tuple[list[ResearchSignal], dict[str, Any], dict[str, Any]]:
        if not signals:
            return [], self.graph.analyze([]), self.selector.select([], {"summary": {}})[1]

        graph_payload = self.graph.analyze(signals)
        graph_enriched = [
            signal.model_copy(update=graph_payload.get("signal_updates", {}).get(signal.symbol, {}))
            for signal in signals
        ]
        enriched, selector_payload = self.selector.select(graph_enriched, graph_payload)
        return enriched, graph_payload, selector_payload
