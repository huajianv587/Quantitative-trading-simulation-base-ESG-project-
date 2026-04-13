from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from gateway.config import settings
from gateway.quant.models import ResearchSignal
from gateway.utils.logger import get_logger

logger = get_logger(__name__)


DEFAULT_FEATURES = [
    "momentum",
    "quality",
    "value",
    "alternative_data",
    "regime_fit",
    "esg_delta",
    "confidence",
    "risk_score",
    "overall_score",
    "e_score",
    "s_score",
    "g_score",
    "expected_return",
    "is_long",
    "is_neutral",
]


def signal_to_feature_row(signal: ResearchSignal) -> dict[str, float]:
    factor_map = {
        str(factor.name): float(factor.value)
        for factor in signal.factor_scores
    }
    return {
        "momentum": factor_map.get("momentum", 50.0),
        "quality": factor_map.get("quality", 50.0),
        "value": factor_map.get("value", 50.0),
        "alternative_data": factor_map.get("alternative_data", 50.0),
        "regime_fit": factor_map.get("regime_fit", 50.0),
        "esg_delta": factor_map.get("esg_delta", 50.0),
        "confidence": float(signal.confidence),
        "risk_score": float(signal.risk_score),
        "overall_score": float(signal.overall_score),
        "e_score": float(signal.e_score),
        "s_score": float(signal.s_score),
        "g_score": float(signal.g_score),
        "expected_return": float(signal.expected_return),
        "is_long": 1.0 if signal.action == "long" else 0.0,
        "is_neutral": 1.0 if signal.action == "neutral" else 0.0,
    }


class AlphaRankerRuntime:
    def __init__(self, checkpoint_dir: str | Path | None = None) -> None:
        configured = checkpoint_dir or getattr(settings, "ALPHA_RANKER_CHECKPOINT_DIR", "")
        self.checkpoint_root = self._resolve_checkpoint_dir(configured)
        self.enabled = bool(getattr(settings, "ALPHA_RANKER_ENABLED", True))
        self.backend = "unavailable"
        self.model_name = ""
        self.feature_names = list(DEFAULT_FEATURES)
        self.model: Any | None = None
        self.metadata: dict[str, Any] = {}
        self._load()

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "available": self.available(),
            "backend": self.backend,
            "model_name": self.model_name,
            "checkpoint_root": str(self.checkpoint_root),
            "feature_names": list(self.feature_names),
        }

    def available(self) -> bool:
        return self.enabled and self.model is not None

    def rerank(self, signals: list[ResearchSignal]) -> list[ResearchSignal]:
        if not signals:
            return []
        if not self.available():
            return [
                signal.model_copy(
                    update={
                        "alpha_model_score": None,
                        "alpha_model_name": None,
                        "alpha_rank": index + 1,
                    }
                )
                for index, signal in enumerate(signals)
            ]

        feature_rows = [signal_to_feature_row(signal) for signal in signals]
        scores = self.predict_many(feature_rows)
        if not scores:
            return signals

        ranked = sorted(
            zip(signals, scores),
            key=lambda item: (item[0].action != "long", -float(item[1]), -item[0].overall_score, -item[0].confidence),
        )
        updated: list[ResearchSignal] = []
        for index, (signal, score) in enumerate(ranked):
            updated.append(
                signal.model_copy(
                    update={
                        "alpha_model_score": round(float(score), 6),
                        "alpha_model_name": self.model_name or self.backend,
                        "alpha_rank": index + 1,
                        "expected_return": round(float(signal.expected_return), 4),
                        "signal_source": "alpha_ranker",
                    }
                )
            )
        return updated

    def predict_many(self, feature_rows: list[dict[str, float]]) -> list[float]:
        if not self.available():
            return []

        frame = pd.DataFrame(feature_rows)
        for feature in self.feature_names:
            if feature not in frame.columns:
                frame[feature] = 0.0
        frame = frame[self.feature_names].fillna(0.0)
        raw = self.model.predict(frame)
        values = [float(value) for value in raw]

        lower = float(self.metadata.get("prediction_min", min(values) if values else 0.0))
        upper = float(self.metadata.get("prediction_max", max(values) if values else 1.0))
        span = max(upper - lower, 1e-9)
        return [max(0.0, min(1.0, (value - lower) / span)) for value in values]

    def _load(self) -> None:
        if not self.enabled:
            return

        if not self.checkpoint_root.exists():
            return

        metadata_path = self.checkpoint_root / "metadata.json"
        model_path = self.checkpoint_root / "model.joblib"
        if not metadata_path.exists() or not model_path.exists():
            return

        try:
            import joblib
        except Exception as exc:
            logger.warning(f"Alpha ranker disabled because joblib is unavailable: {exc}")
            return

        try:
            self.metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            self.feature_names = [str(item) for item in self.metadata.get("feature_names", DEFAULT_FEATURES)]
            self.backend = str(self.metadata.get("backend") or "unknown")
            self.model_name = str(self.metadata.get("model_name") or self.backend)
            self.model = joblib.load(model_path)
        except Exception as exc:
            logger.warning(f"Failed to load alpha ranker checkpoint from {self.checkpoint_root}: {exc}")
            self.model = None
            self.metadata = {}
            self.backend = "unavailable"
            self.model_name = ""

    @staticmethod
    def _resolve_checkpoint_dir(raw_value: str | Path) -> Path:
        path = Path(raw_value)
        if path.is_absolute():
            return path
        return Path(__file__).resolve().parents[2] / path
