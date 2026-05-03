from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from gateway.config import settings
from gateway.quant.alpha_ranker import signal_to_feature_row
from gateway.quant.models import ResearchSignal
from gateway.utils.logger import get_logger

logger = get_logger(__name__)


P1_FEATURE_COLUMNS = [
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
    "alpha_baseline",
    "fundamental_score",
    "news_sentiment_score",
    "relative_strength_20d",
    "return_1d_proxy",
    "return_5d_proxy",
    "return_20d_proxy",
    "volatility_5d",
    "volatility_20d",
    "drawdown_20d",
    "drawdown_60d",
    "benchmark_return_5d",
    "beta_proxy",
    "trend_gap",
]

P1_MODEL_SPECS: dict[str, dict[str, str]] = {
    "return_1d": {
        "label": "Next-day Return",
        "task": "return_forecast",
        "objective": "regression",
        "target_column": "forward_return_1d",
    },
    "return_5d": {
        "label": "Five-day Return",
        "task": "return_forecast",
        "objective": "regression",
        "target_column": "forward_return_5d",
    },
    "volatility_10d": {
        "label": "Ten-day Volatility",
        "task": "risk_forecast",
        "objective": "regression",
        "target_column": "future_volatility_10d",
    },
    "drawdown_20d": {
        "label": "Twenty-day Drawdown",
        "task": "risk_forecast",
        "objective": "regression",
        "target_column": "future_max_drawdown_20d",
    },
    "regime_classifier": {
        "label": "Regime Classifier",
        "task": "regime",
        "objective": "multiclass",
        "target_column": "regime_label",
    },
}

P1_REGIME_LABELS = ["risk_off", "neutral", "risk_on"]
P1_NORMALIZATION_RANGES = {
    "return_1d": (-0.06, 0.06),
    "return_5d": (-0.12, 0.18),
    "volatility_10d": (0.05, 0.55),
    "drawdown_20d": (0.03, 0.45),
}
DEFAULT_STACK_WEIGHTS = {
    "alpha": 0.18,
    "return_1d": 0.14,
    "return_5d": 0.28,
    "risk": 0.22,
    "regime": 0.18,
}

SEQUENCE_TARGET_COLUMN_TO_KEY = {
    "forward_return_1d": "return_1d",
    "forward_return_5d": "return_5d",
    "future_volatility_10d": "volatility_10d",
    "future_max_drawdown_20d": "drawdown_20d",
}


class SequenceForecasterRuntime:
    def __init__(
        self,
        checkpoint_dir: str | Path | None = None,
        data_dir: str | Path | None = None,
    ) -> None:
        configured = checkpoint_dir or getattr(
            settings,
            "P1_SEQUENCE_CHECKPOINT_DIR",
            "model-serving/checkpoint/sequence_forecaster",
        )
        self.checkpoint_dir = _resolve_checkpoint_dir(configured)
        configured_data = data_dir or getattr(settings, "P1_MODEL_SUITE_DATA_DIR", "data/p1_stack")
        self.data_dir = _resolve_checkpoint_dir(configured_data)
        self.enabled = bool(getattr(settings, "P1_SEQUENCE_ENABLED", True))
        self.blend_weight = float(getattr(settings, "P1_SEQUENCE_BLEND_WEIGHT", 0.35) or 0.35)
        configured_targets = str(
            getattr(
                settings,
                "P1_SEQUENCE_TARGETS",
                "forward_return_1d,forward_return_5d,future_volatility_10d,future_max_drawdown_20d",
            )
            or ""
        )
        self.requested_targets = [
            item.strip()
            for item in configured_targets.split(",")
            if item.strip() in SEQUENCE_TARGET_COLUMN_TO_KEY
        ] or list(SEQUENCE_TARGET_COLUMN_TO_KEY)
        self.manifests: dict[str, dict[str, Any]] = {}
        self._torch = None
        self._device = "cpu"
        self._models: dict[str, Any] = {}
        self._history_frame: pd.DataFrame | None = None
        self._load_attempted = False
        self._load_lock = threading.RLock()

    def available(self) -> bool:
        with self._load_lock:
            return self.enabled and bool(self._models) and bool(self.manifests)

    def status(self) -> dict[str, Any]:
        with self._load_lock:
            loaded_targets = list(self._models.keys())
            manifests = dict(self.manifests)
        return {
            "enabled": self.enabled,
            "available": self.available(),
            "checkpoint_dir": str(self.checkpoint_dir),
            "data_dir": str(self.data_dir),
            "blend_weight": self.blend_weight,
            "device": self._device,
            "requested_targets": list(self.requested_targets),
            "loaded_targets": loaded_targets,
            "manifests": manifests,
            "history_rows": 0 if self._history_frame is None else int(len(self._history_frame)),
        }

    def predict(self, signals: list[ResearchSignal], frame: pd.DataFrame) -> dict[str, list[float | None]]:
        payload = {key: [None for _ in signals] for key in SEQUENCE_TARGET_COLUMN_TO_KEY.values()}
        if not signals or frame.empty:
            return payload
        self._ensure_loaded()
        if not self.available():
            return payload
        torch = self._torch
        with self._load_lock:
            models_snapshot = list(self._models.items())
            manifests_snapshot = dict(self.manifests)
        for target_key, model in models_snapshot:
            manifest = manifests_snapshot.get(target_key, {})
            window_size = int(manifest.get("window_size", 20) or 20)
            windows = [
                self._build_window(signal, frame.iloc[index].to_dict(), window_size)
                for index, signal in enumerate(signals)
            ]
            batch = np.stack(windows).astype(np.float32)
            tensor = torch.tensor(batch, dtype=torch.float32, device=self._device)
            with torch.no_grad():
                predictions = model(tensor).detach().cpu().numpy().tolist()
            payload[target_key] = [float(value) for value in predictions]
        return payload

    def _build_window(self, signal: ResearchSignal, row: dict[str, Any], window_size: int) -> np.ndarray:
        if self._history_frame is not None:
            symbol_history = self._history_frame[self._history_frame["symbol"] == signal.symbol].copy()
            if len(symbol_history) >= window_size:
                tail = symbol_history.tail(window_size)
                for feature in P1_FEATURE_COLUMNS:
                    if feature not in tail.columns:
                        tail[feature] = 0.0
                return tail[P1_FEATURE_COLUMNS].fillna(0.0).to_numpy(dtype=np.float32)

        base = np.asarray([float(row.get(feature, 0.0)) for feature in P1_FEATURE_COLUMNS], dtype=np.float32)
        multipliers = np.linspace(0.94, 1.02, num=window_size, dtype=np.float32)
        return np.stack([base * scale for scale in multipliers], axis=0)

    def _ensure_loaded(self) -> None:
        with self._load_lock:
            if self._load_attempted:
                return
            self._load_attempted = True
            self._load()

    def _load(self) -> None:
        if not self.enabled:
            return
        candidate_dirs = [self.checkpoint_dir]
        for target_column in self.requested_targets:
            target_key = SEQUENCE_TARGET_COLUMN_TO_KEY.get(target_column)
            if target_key is None:
                continue
            candidate_dirs.extend([self.checkpoint_dir / target_key, self.checkpoint_dir / target_column])
        has_checkpoint = any(
            (candidate / "sequence_manifest.json").exists() and (candidate / "model.pt").exists()
            for candidate in candidate_dirs
        )
        if not has_checkpoint:
            return
        try:
            import torch
            from torch import nn
        except Exception as exc:
            logger.warning(f"Sequence forecaster unavailable because PyTorch is missing: {exc}")
            return

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

        def load_single(checkpoint_dir: Path) -> tuple[str, dict[str, Any], Any] | None:
            manifest_path = checkpoint_dir / "sequence_manifest.json"
            model_path = checkpoint_dir / "model.pt"
            if not manifest_path.exists() or not model_path.exists():
                return None
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            target_column = str(manifest.get("target_column", "forward_return_5d"))
            runtime_key = SEQUENCE_TARGET_COLUMN_TO_KEY.get(target_column)
            if runtime_key is None:
                return None
            hidden_size = int(manifest.get("hidden_size", 64) or 64)
            architecture = str(manifest.get("architecture", "lstm")).lower()
            model_cls = LSTMForecaster if architecture == "lstm" else TCNForecaster
            model = model_cls(len(P1_FEATURE_COLUMNS), hidden_size).to(self._device)
            state_dict = torch.load(model_path, map_location=self._device)
            model.load_state_dict(state_dict)
            model.eval()
            return runtime_key, manifest, model

        try:
            self._torch = torch
            self._device = "cuda" if torch.cuda.is_available() else "cpu"
            loaded_targets: set[str] = set()
            for target_column in self.requested_targets:
                target_key = SEQUENCE_TARGET_COLUMN_TO_KEY.get(target_column)
                if target_key is None:
                    continue
                candidate_dirs = [self.checkpoint_dir / target_key, self.checkpoint_dir / target_column]
                for candidate in candidate_dirs:
                    result = load_single(candidate)
                    if result is None:
                        continue
                    runtime_key, manifest, model = result
                    self.manifests[runtime_key] = manifest
                    self._models[runtime_key] = model
                    loaded_targets.add(runtime_key)
                    break
            legacy_result = load_single(self.checkpoint_dir)
            if legacy_result is not None:
                runtime_key, manifest, model = legacy_result
                if runtime_key not in loaded_targets:
                    self.manifests[runtime_key] = manifest
                    self._models[runtime_key] = model
        except Exception as exc:
            logger.warning(f"Failed to load sequence forecaster from {self.checkpoint_dir}: {exc}")
            self._models = {}
            self.manifests = {}
            return

        full_dataset_path = self.data_dir / "full_dataset.csv"
        if full_dataset_path.exists():
            try:
                history = pd.read_csv(full_dataset_path)
                if {"symbol", *P1_FEATURE_COLUMNS}.issubset(history.columns):
                    self._history_frame = history.sort_values(["symbol", "date"]).reset_index(drop=True)
            except Exception as exc:
                logger.warning(f"Failed to load P1 historical dataset for sequence forecaster: {exc}")


def _bounded(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _resolve_checkpoint_dir(raw_value: str | Path) -> Path:
    path = Path(raw_value)
    if path.is_absolute():
        return path
    return Path(__file__).resolve().parents[2] / path


def _factor_value(signal: ResearchSignal, name: str, fallback: float = 50.0) -> float:
    for factor in signal.factor_scores:
        if str(factor.name) == name:
            return float(factor.value)
    return fallback


def _normalize_component(value: float | None, key: str, invert: bool = False) -> float:
    if value is None:
        return 0.5
    lower, upper = P1_NORMALIZATION_RANGES[key]
    span = max(upper - lower, 1e-9)
    normalized = _bounded((float(value) - lower) / span, 0.0, 1.0)
    return 1.0 - normalized if invert else normalized


def compute_p1_stack_score(
    *,
    alpha_baseline: float | None,
    predicted_return_1d: float | None,
    predicted_return_5d: float | None,
    predicted_volatility_10d: float | None,
    predicted_drawdown_20d: float | None,
    regime_label: str | None,
    regime_probability: float | None,
    weights: dict[str, float] | None = None,
) -> float:
    stack_weights = dict(DEFAULT_STACK_WEIGHTS)
    stack_weights.update(weights or {})
    alpha_component = _bounded(float(alpha_baseline if alpha_baseline is not None else 0.5), 0.0, 1.0)
    return_1d_component = _normalize_component(predicted_return_1d, "return_1d")
    return_5d_component = _normalize_component(predicted_return_5d, "return_5d")
    risk_component = (
        _normalize_component(predicted_volatility_10d, "volatility_10d", invert=True)
        + _normalize_component(predicted_drawdown_20d, "drawdown_20d", invert=True)
    ) / 2.0
    regime_bias = {"risk_off": 0.0, "neutral": 0.5, "risk_on": 1.0}.get(str(regime_label or "neutral").lower(), 0.5)
    regime_component = _bounded(0.65 * regime_bias + 0.35 * float(regime_probability or 0.5), 0.0, 1.0)
    score = (
        stack_weights["alpha"] * alpha_component
        + stack_weights["return_1d"] * return_1d_component
        + stack_weights["return_5d"] * return_5d_component
        + stack_weights["risk"] * risk_component
        + stack_weights["regime"] * regime_component
    )
    return round(_bounded(score, 0.0, 1.0), 6)


def _sigmoid(value: float) -> float:
    return 1.0 / (1.0 + np.exp(-float(value)))


def _blend_prediction(base_value: float | None, sequence_value: float | None, blend_weight: float) -> float | None:
    if base_value is None and sequence_value is None:
        return None
    if base_value is None:
        return float(sequence_value) if sequence_value is not None else None
    if sequence_value is None:
        return float(base_value)
    weight = _bounded(float(blend_weight), 0.0, 0.9)
    return (1.0 - weight) * float(base_value) + weight * float(sequence_value)


def _calibrate_probability(*, stack_score: float, regime_probability: float | None, temperature: float, enabled: bool) -> float:
    baseline = float(stack_score)
    if regime_probability is not None:
        baseline = 0.72 * baseline + 0.28 * float(regime_probability)
    if not enabled:
        return round(_bounded(baseline, 0.0, 1.0), 6)
    scaled = (baseline - 0.5) / max(float(temperature), 1e-6)
    return round(_bounded(_sigmoid(scaled), 0.0, 1.0), 6)


def _calibrate_confidence(*, raw_confidence: float, calibrated_probability: float, slope: float, enabled: bool) -> float:
    if not enabled:
        return round(_bounded(float(raw_confidence), 0.0, 1.0), 6)
    centered = (float(calibrated_probability) - 0.5) * max(float(slope), 0.1)
    calibrated = float(raw_confidence) * (0.72 + 0.34 * float(calibrated_probability)) + centered * 0.08
    return round(_bounded(calibrated, 0.0, 1.0), 6)


def signal_to_p1_feature_row(signal: ResearchSignal) -> dict[str, float]:
    base = signal_to_feature_row(signal)
    momentum = float(base["momentum"])
    quality = float(base["quality"])
    value = float(base["value"])
    alternative_data = float(base["alternative_data"])
    regime_fit = float(base["regime_fit"])
    esg_delta = float(base["esg_delta"])
    confidence = float(base["confidence"])
    risk_score = float(base["risk_score"])
    overall_score = float(base["overall_score"])
    expected_return = float(base["expected_return"])

    fundamental_score = _bounded(
        0.40 * quality + 0.20 * value + 0.15 * base["g_score"] + 0.15 * base["s_score"] + 0.10 * regime_fit,
        35.0,
        95.0,
    )
    news_sentiment_score = _bounded(
        0.36 * momentum + 0.24 * alternative_data + 0.14 * esg_delta + 18.0 * confidence - 0.15 * risk_score,
        12.0,
        96.0,
    )
    trend_gap = (momentum - 50.0) / 100.0
    relative_strength_20d = _bounded(expected_return * 2.2 + trend_gap * 0.18 + (regime_fit - 50.0) / 600.0, -0.35, 0.35)
    return_1d_proxy = _bounded(expected_return * 0.28 + trend_gap / 12.0, -0.08, 0.08)
    return_5d_proxy = _bounded(expected_return + relative_strength_20d * 0.12, -0.12, 0.18)
    return_20d_proxy = _bounded(return_5d_proxy * 2.4 + (fundamental_score - 60.0) / 500.0, -0.20, 0.30)
    volatility_5d = _bounded(0.08 + risk_score / 380.0 + abs(trend_gap) / 4.0, 0.04, 0.40)
    volatility_20d = _bounded(volatility_5d * 1.18 + max(0.0, -return_5d_proxy) * 0.9, 0.05, 0.55)
    drawdown_20d = _bounded(0.04 + volatility_20d * 0.55 + max(0.0, (58.0 - overall_score)) / 260.0, 0.03, 0.40)
    drawdown_60d = _bounded(drawdown_20d * 1.45, 0.04, 0.58)
    benchmark_return_5d = _bounded(0.002 + (regime_fit - 50.0) / 5000.0, -0.04, 0.05)
    beta_proxy = _bounded(0.72 + risk_score / 145.0 - base["g_score"] / 380.0 + abs(trend_gap) * 0.35, 0.35, 1.75)
    alpha_baseline = float(signal.alpha_model_score if signal.alpha_model_score is not None else _bounded(overall_score / 100.0, 0.0, 1.0))

    return {
        **base,
        "alpha_baseline": round(alpha_baseline, 6),
        "fundamental_score": round(fundamental_score, 6),
        "news_sentiment_score": round(news_sentiment_score, 6),
        "relative_strength_20d": round(relative_strength_20d, 6),
        "return_1d_proxy": round(return_1d_proxy, 6),
        "return_5d_proxy": round(return_5d_proxy, 6),
        "return_20d_proxy": round(return_20d_proxy, 6),
        "volatility_5d": round(volatility_5d, 6),
        "volatility_20d": round(volatility_20d, 6),
        "drawdown_20d": round(drawdown_20d, 6),
        "drawdown_60d": round(drawdown_60d, 6),
        "benchmark_return_5d": round(benchmark_return_5d, 6),
        "beta_proxy": round(beta_proxy, 6),
        "trend_gap": round(trend_gap, 6),
    }


class P1ModelSuiteRuntime:
    def __init__(
        self,
        checkpoint_dir: str | Path | None = None,
        sequence_checkpoint_dir: str | Path | None = None,
    ) -> None:
        configured = checkpoint_dir or getattr(settings, "P1_MODEL_SUITE_CHECKPOINT_DIR", "model-serving/checkpoint/p1_suite")
        self.checkpoint_root = _resolve_checkpoint_dir(configured)
        self.enabled = bool(getattr(settings, "P1_MODEL_SUITE_ENABLED", True))
        self.models: dict[str, Any] = {}
        self.metadata: dict[str, dict[str, Any]] = {}
        self.suite_manifest: dict[str, Any] = {}
        self.sequence_forecaster = SequenceForecasterRuntime(
            checkpoint_dir=sequence_checkpoint_dir,
            data_dir=getattr(settings, "P1_MODEL_SUITE_DATA_DIR", "data/p1_stack"),
        )
        self.stack_weights = {
            "alpha": float(getattr(settings, "P1_STACK_WEIGHT_ALPHA", DEFAULT_STACK_WEIGHTS["alpha"]) or DEFAULT_STACK_WEIGHTS["alpha"]),
            "return_1d": float(getattr(settings, "P1_STACK_WEIGHT_RETURN_1D", DEFAULT_STACK_WEIGHTS["return_1d"]) or DEFAULT_STACK_WEIGHTS["return_1d"]),
            "return_5d": float(getattr(settings, "P1_STACK_WEIGHT_RETURN_5D", DEFAULT_STACK_WEIGHTS["return_5d"]) or DEFAULT_STACK_WEIGHTS["return_5d"]),
            "risk": float(getattr(settings, "P1_STACK_WEIGHT_RISK", DEFAULT_STACK_WEIGHTS["risk"]) or DEFAULT_STACK_WEIGHTS["risk"]),
            "regime": float(getattr(settings, "P1_STACK_WEIGHT_REGIME", DEFAULT_STACK_WEIGHTS["regime"]) or DEFAULT_STACK_WEIGHTS["regime"]),
        }
        self.calibration_enabled = bool(getattr(settings, "P1_CALIBRATION_ENABLED", True))
        self.calibration_temperature = float(getattr(settings, "P1_CALIBRATION_TEMPERATURE", 0.22) or 0.22)
        self.confidence_slope = float(getattr(settings, "P1_CONFIDENCE_SLOPE", 1.25) or 1.25)
        self._load()

    def available(self) -> bool:
        return self.enabled and bool(self.models)

    def status(self) -> dict[str, Any]:
        model_descriptors: list[dict[str, Any]] = []
        for key, spec in P1_MODEL_SPECS.items():
            metadata = self.metadata.get(key, {})
            model_descriptors.append(
                {
                    "key": key,
                    "label": spec["label"],
                    "task": spec["task"],
                    "objective": spec["objective"],
                    "target_column": spec["target_column"],
                    "available": key in self.models,
                    "backend": metadata.get("backend", "heuristic_fallback"),
                    "model_name": metadata.get("model_name", key),
                    "metrics": metadata.get("metrics", {}),
                    "checkpoint_dir": str(self.checkpoint_root / key),
                }
            )
        return {
            "enabled": self.enabled,
            "available": self.available(),
            "checkpoint_root": str(self.checkpoint_root),
            "loaded_models": len(self.models),
            "expected_models": len(P1_MODEL_SPECS),
            "suite_manifest": self.suite_manifest,
            "sequence_forecaster": self.sequence_forecaster.status(),
            "stack_weights": dict(self.stack_weights),
            "calibration": {
                "enabled": self.calibration_enabled,
                "temperature": self.calibration_temperature,
                "confidence_slope": self.confidence_slope,
            },
            "models": model_descriptors,
        }

    def enrich_and_rerank(self, signals: list[ResearchSignal]) -> list[ResearchSignal]:
        if not signals:
            return []

        frame = pd.DataFrame([signal_to_p1_feature_row(signal) for signal in signals]).fillna(0.0)
        predictions = {
            "return_1d": self._predict_numeric("return_1d", frame, signals),
            "return_5d": self._predict_numeric("return_5d", frame, signals),
            "volatility_10d": self._predict_numeric("volatility_10d", frame, signals),
            "drawdown_20d": self._predict_numeric("drawdown_20d", frame, signals),
            "regime_classifier": self._predict_regime(frame, signals),
        }
        sequence_predictions = self.sequence_forecaster.predict(signals, frame)

        enriched: list[ResearchSignal] = []
        for index, signal in enumerate(signals):
            regime_payload = predictions["regime_classifier"][index]
            predicted_return_1d = predictions["return_1d"][index]
            predicted_return_5d = predictions["return_5d"][index]
            sequence_return_1d = sequence_predictions.get("return_1d", [None for _ in signals])[index]
            sequence_return_5d = sequence_predictions.get("return_5d", [None for _ in signals])[index]
            sequence_volatility_10d = sequence_predictions.get("volatility_10d", [None for _ in signals])[index]
            sequence_drawdown_20d = sequence_predictions.get("drawdown_20d", [None for _ in signals])[index]
            blend_weight = self.sequence_forecaster.blend_weight
            predicted_return_1d = float(
                _blend_prediction(predicted_return_1d, sequence_return_1d, blend_weight * 0.85)
                or 0.0
            )
            predicted_return_5d = float(
                _blend_prediction(predicted_return_5d, sequence_return_5d, blend_weight)
                or 0.0
            )
            predicted_volatility_10d = predictions["volatility_10d"][index]
            predicted_volatility_10d = float(
                _blend_prediction(predicted_volatility_10d, sequence_volatility_10d, blend_weight * 0.65)
                or 0.0
            )
            predicted_drawdown_20d = predictions["drawdown_20d"][index]
            predicted_drawdown_20d = float(
                _blend_prediction(predicted_drawdown_20d, sequence_drawdown_20d, blend_weight * 0.65)
                or 0.0
            )
            p1_score = compute_p1_stack_score(
                alpha_baseline=signal.alpha_model_score if signal.alpha_model_score is not None else frame.iloc[index]["alpha_baseline"],
                predicted_return_1d=predicted_return_1d,
                predicted_return_5d=predicted_return_5d,
                predicted_volatility_10d=predicted_volatility_10d,
                predicted_drawdown_20d=predicted_drawdown_20d,
                regime_label=regime_payload["label"],
                regime_probability=regime_payload["probability"],
                weights=self.stack_weights,
            )
            calibrated_probability = _calibrate_probability(
                stack_score=p1_score,
                regime_probability=regime_payload["probability"],
                temperature=self.calibration_temperature,
                enabled=self.calibration_enabled,
            )
            calibrated_confidence = _calibrate_confidence(
                raw_confidence=float(signal.confidence),
                calibrated_probability=calibrated_probability,
                slope=self.confidence_slope,
                enabled=self.calibration_enabled,
            )
            action = signal.action
            if action == "long":
                if regime_payload["label"] == "risk_off" and regime_payload["probability"] >= 0.68:
                    action = "neutral"
                elif predicted_drawdown_20d >= 0.26 or predicted_volatility_10d >= 0.36:
                    action = "neutral"
                elif calibrated_probability < 0.46:
                    action = "neutral"

            enriched.append(
                signal.model_copy(
                    update={
                        "action": action,
                        "predicted_return_1d": round(float(predicted_return_1d), 6),
                        "predicted_return_5d": round(float(predicted_return_5d), 6),
                        "sequence_return_1d": None if sequence_return_1d is None else round(float(sequence_return_1d), 6),
                        "sequence_return_5d": None if sequence_return_5d is None else round(float(sequence_return_5d), 6),
                        "sequence_volatility_10d": None if sequence_volatility_10d is None else round(float(sequence_volatility_10d), 6),
                        "sequence_drawdown_20d": None if sequence_drawdown_20d is None else round(float(sequence_drawdown_20d), 6),
                        "predicted_volatility_10d": round(float(predicted_volatility_10d), 6),
                        "predicted_drawdown_20d": round(float(predicted_drawdown_20d), 6),
                        "sequence_model_version": (
                            "|".join(
                                f"{target}:{str(manifest.get('generated_at') or manifest.get('architecture') or target)}"
                                for target, manifest in self.sequence_forecaster.manifests.items()
                            )
                            if self.sequence_forecaster.manifests
                            else None
                        ),
                        "regime_label": regime_payload["label"],
                        "regime_probability": round(float(regime_payload["probability"]), 6),
                        "fundamental_score": round(float(frame.iloc[index]["fundamental_score"]), 4),
                        "news_sentiment_score": round(float(frame.iloc[index]["news_sentiment_score"]), 4),
                        "p1_stack_score": p1_score,
                        "p1_calibrated_probability": calibrated_probability,
                        "p1_confidence_calibrated": calibrated_confidence,
                        "p1_model_version": str(self.suite_manifest.get("suite_version") or self.suite_manifest.get("generated_at") or "heuristic_fallback"),
                        "signal_source": "p1_stack" if self.available() else "p1_stack_heuristic",
                    }
                )
            )

        ranked = sorted(
            enriched,
            key=lambda item: (
                item.action != "long",
                -(item.p1_stack_score or 0.0),
                -(item.alpha_model_score or 0.0),
                -(item.p1_confidence_calibrated if item.p1_confidence_calibrated is not None else item.confidence),
            ),
        )
        return [
            signal.model_copy(update={"alpha_rank": index + 1})
            for index, signal in enumerate(ranked)
        ]

    def _predict_numeric(
        self,
        model_key: str,
        frame: pd.DataFrame,
        signals: list[ResearchSignal],
    ) -> list[float]:
        model = self.models.get(model_key)
        metadata = self.metadata.get(model_key, {})
        if model is not None:
            feature_names = [str(item) for item in metadata.get("feature_names", P1_FEATURE_COLUMNS)]
            local = frame.copy()
            for feature in feature_names:
                if feature not in local.columns:
                    local[feature] = 0.0
            values = model.predict(local[feature_names].fillna(0.0))
            return [float(value) for value in values]

        predicted: list[float] = []
        for signal in signals:
            feature_row = signal_to_p1_feature_row(signal)
            if model_key == "return_1d":
                predicted.append(float(feature_row["return_1d_proxy"]))
            elif model_key == "return_5d":
                predicted.append(float(feature_row["return_5d_proxy"]))
            elif model_key == "volatility_10d":
                predicted.append(float(_bounded(feature_row["volatility_20d"] * 0.78, 0.05, 0.55)))
            elif model_key == "drawdown_20d":
                predicted.append(float(feature_row["drawdown_20d"]))
            else:
                predicted.append(0.0)
        return predicted

    def _predict_regime(
        self,
        frame: pd.DataFrame,
        signals: list[ResearchSignal],
    ) -> list[dict[str, Any]]:
        model = self.models.get("regime_classifier")
        metadata = self.metadata.get("regime_classifier", {})
        if model is not None:
            feature_names = [str(item) for item in metadata.get("feature_names", P1_FEATURE_COLUMNS)]
            local = frame.copy()
            for feature in feature_names:
                if feature not in local.columns:
                    local[feature] = 0.0
            payloads: list[dict[str, Any]] = []
            if hasattr(model, "predict_proba"):
                probabilities = model.predict_proba(local[feature_names].fillna(0.0))
                classes = [str(item) for item in metadata.get("classes", P1_REGIME_LABELS)]
                for row in probabilities:
                    best_index = max(range(len(row)), key=lambda idx: float(row[idx]))
                    payloads.append({"label": classes[best_index], "probability": float(row[best_index])})
                return payloads
            labels = model.predict(local[feature_names].fillna(0.0))
            return [{"label": str(value), "probability": 0.6} for value in labels]

        payloads = []
        for signal in signals:
            feature_row = signal_to_p1_feature_row(signal)
            regime_score = (
                0.34 * feature_row["regime_fit"]
                + 0.22 * feature_row["momentum"]
                + 0.18 * feature_row["fundamental_score"]
                + 0.16 * feature_row["news_sentiment_score"]
                - 0.16 * feature_row["risk_score"]
            ) / 100.0
            if regime_score >= 0.58:
                payloads.append({"label": "risk_on", "probability": _bounded(0.58 + regime_score / 3.0, 0.58, 0.91)})
            elif regime_score <= 0.46:
                payloads.append({"label": "risk_off", "probability": _bounded(0.56 + (0.5 - regime_score) / 2.5, 0.56, 0.9)})
            else:
                payloads.append({"label": "neutral", "probability": _bounded(0.52 + abs(regime_score - 0.52), 0.52, 0.78)})
        return payloads

    def _load(self) -> None:
        if not self.enabled or not self.checkpoint_root.exists():
            return

        suite_manifest_path = self.checkpoint_root / "suite_manifest.json"
        if suite_manifest_path.exists():
            try:
                self.suite_manifest = json.loads(suite_manifest_path.read_text(encoding="utf-8"))
            except Exception as exc:
                logger.warning(f"Failed to load P1 suite manifest from {suite_manifest_path}: {exc}")

        try:
            import joblib
        except Exception as exc:
            logger.warning(f"P1 model suite disabled because joblib is unavailable: {exc}")
            return

        for key in P1_MODEL_SPECS:
            checkpoint_dir = self.checkpoint_root / key
            metadata_path = checkpoint_dir / "metadata.json"
            model_path = checkpoint_dir / "model.joblib"
            if not metadata_path.exists() or not model_path.exists():
                continue
            try:
                self.metadata[key] = json.loads(metadata_path.read_text(encoding="utf-8"))
                self.models[key] = joblib.load(model_path)
            except Exception as exc:
                logger.warning(f"Failed to load P1 checkpoint {key} from {checkpoint_dir}: {exc}")
                self.models.pop(key, None)
                self.metadata.pop(key, None)
