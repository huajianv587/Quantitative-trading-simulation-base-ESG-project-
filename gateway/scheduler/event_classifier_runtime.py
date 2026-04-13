from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gateway.config import settings
from gateway.utils.logger import get_logger

logger = get_logger(__name__)


def _resolve_checkpoint_dir(raw_value: str | Path) -> Path:
    path = Path(raw_value)
    if path.is_absolute():
        return path
    return Path(__file__).resolve().parents[2] / path


class EventClassifierRuntime:
    def __init__(
        self,
        checkpoint_root: str | Path | None = None,
        target: str | None = None,
    ) -> None:
        self.enabled = bool(getattr(settings, "EVENT_CLASSIFIER_ENABLED", True))
        configured_root = checkpoint_root or getattr(
            settings,
            "EVENT_CLASSIFIER_CHECKPOINT_ROOT",
            "model-serving/checkpoint/event_classifier",
        )
        self.target = str(target or getattr(settings, "EVENT_CLASSIFIER_TARGET", "controversy_label"))
        configured_tasks = str(
            getattr(
                settings,
                "EVENT_CLASSIFIER_TASKS",
                "controversy_label,severity,impact_area,event_type",
            )
            or ""
        )
        parsed_tasks = [item.strip() for item in configured_tasks.split(",") if item.strip()]
        self.tasks = parsed_tasks or [self.target]
        if self.target not in self.tasks:
            self.tasks.insert(0, self.target)
        self.max_length = int(getattr(settings, "EVENT_CLASSIFIER_MAX_LENGTH", 256) or 256)
        self.checkpoint_root = _resolve_checkpoint_dir(configured_root)
        self.checkpoint_dir = self._task_checkpoint_dir(self.target)
        self.metadata: dict[str, Any] = {}
        self.task_metadata: dict[str, dict[str, Any]] = {}
        self._models: dict[str, Any] = {}
        self._tokenizers: dict[str, Any] = {}
        self._torch = None
        self._device = "cpu"
        self._load_metadata()

    def available(self) -> bool:
        return self.enabled and any(self._task_available(task) for task in self.tasks)

    def status(self) -> dict[str, Any]:
        task_payload = {}
        for task in self.tasks:
            metadata = self.task_metadata.get(task, {})
            checkpoint_dir = self._task_checkpoint_dir(task)
            task_payload[task] = {
                "available": self._task_available(task),
                "checkpoint_dir": str(checkpoint_dir),
                "model_name": metadata.get("model_name", ""),
                "classes": list(metadata.get("classes", [])),
                "metrics": dict(metadata.get("metrics", {})),
                "loaded": bool(task in self._models and task in self._tokenizers),
            }
        return {
            "enabled": self.enabled,
            "available": self.available(),
            "target": self.target,
            "checkpoint_dir": str(self.checkpoint_dir),
            "model_name": self.metadata.get("model_name", ""),
            "classes": list(self.metadata.get("classes", [])),
            "metrics": dict(self.metadata.get("metrics", {})),
            "device": self._device,
            "loaded": bool(self._models and self._tokenizers),
            "tasks": task_payload,
        }

    def classify(self, text: str) -> dict[str, Any] | None:
        normalized = str(text or "").strip()
        if not normalized or not self.available():
            return None
        tasks_payload: dict[str, dict[str, Any]] = {}
        for task in self.tasks:
            result = self.classify_task(task, normalized)
            if result is not None:
                tasks_payload[task] = result
        if not tasks_payload:
            return None
        primary_task = self.target if self.target in tasks_payload else next(iter(tasks_payload))
        primary = tasks_payload[primary_task]
        return {
            **primary,
            "target": primary_task,
            "tasks": tasks_payload,
            "available_tasks": list(tasks_payload.keys()),
        }

    def classify_task(self, task: str, text: str) -> dict[str, Any] | None:
        normalized = str(text or "").strip()
        task_name = str(task or "").strip()
        if not normalized or not task_name or not self._task_available(task_name):
            return None
        if not self._ensure_loaded(task_name):
            return None

        torch = self._torch
        tokenizer = self._tokenizers[task_name]
        model = self._models[task_name]
        metadata = self.task_metadata.get(task_name, {})
        encoded = tokenizer(
            normalized,
            truncation=True,
            max_length=self.max_length,
            padding=True,
            return_tensors="pt",
        )
        encoded = {key: value.to(self._device) for key, value in encoded.items()}
        with torch.no_grad():
            logits = model(**encoded).logits
            probabilities = torch.softmax(logits, dim=-1)[0].detach().cpu().tolist()
        classes = [str(item) for item in metadata.get("classes", [])]
        if not classes:
            return None
        best_index = max(range(len(probabilities)), key=lambda idx: float(probabilities[idx]))
        return {
            "target": task_name,
            "label": classes[best_index],
            "probability": round(float(probabilities[best_index]), 6),
            "scores": {classes[index]: round(float(probability), 6) for index, probability in enumerate(probabilities)},
            "model_name": metadata.get("model_name", task_name),
            "checkpoint_dir": str(self._task_checkpoint_dir(task_name)),
        }

    def _load_metadata(self) -> None:
        for task in self.tasks:
            for metadata_path in self._task_metadata_candidates(task):
                if not metadata_path.exists():
                    continue
                try:
                    self.task_metadata[task] = json.loads(metadata_path.read_text(encoding="utf-8"))
                    break
                except Exception as exc:
                    logger.warning(f"Failed to load event classifier metadata from {metadata_path}: {exc}")
        self.metadata = dict(self.task_metadata.get(self.target, {}))

    def _task_available(self, task: str) -> bool:
        metadata = self.task_metadata.get(task, {})
        return self.enabled and bool(metadata.get("classes")) and self._task_checkpoint_dir(task).exists()

    @staticmethod
    def _task_aliases(task: str) -> list[str]:
        normalized = str(task or "").strip()
        aliases = [normalized]
        alias_map = {
            "severity": ["controversy_label"],
            "impact_area": ["esg_axis_label"],
            "event_type": ["impact_direction"],
        }
        for alias in alias_map.get(normalized, []):
            if alias not in aliases:
                aliases.append(alias)
        return aliases

    def _task_metadata_candidates(self, task: str) -> list[Path]:
        candidates: list[Path] = []
        for alias in self._task_aliases(task):
            candidates.append(self.checkpoint_root / alias / "metadata.json")
        return candidates

    def _task_checkpoint_dir(self, task: str) -> Path:
        for alias in self._task_aliases(task):
            candidate = self.checkpoint_root / alias
            if candidate.exists():
                return candidate
        return self.checkpoint_root / task

    def _ensure_loaded(self, task: str) -> bool:
        if task in self._models and task in self._tokenizers:
            return True
        try:
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
        except Exception as exc:
            logger.warning(f"Event classifier runtime unavailable because dependencies are missing: {exc}")
            return False

        try:
            checkpoint_dir = self._task_checkpoint_dir(task)
            self._torch = torch
            self._device = "cuda" if torch.cuda.is_available() else "cpu"
            tokenizer = AutoTokenizer.from_pretrained(str(checkpoint_dir))
            model = AutoModelForSequenceClassification.from_pretrained(str(checkpoint_dir))
            model.to(self._device)
            model.eval()
            self._tokenizers[task] = tokenizer
            self._models[task] = model
            return True
        except Exception as exc:
            logger.warning(f"Failed to load event classifier checkpoint from {self._task_checkpoint_dir(task)}: {exc}")
            self._models.pop(task, None)
            self._tokenizers.pop(task, None)
            return False


_event_classifier_runtime: EventClassifierRuntime | None = None


def get_event_classifier_runtime() -> EventClassifierRuntime:
    global _event_classifier_runtime
    if _event_classifier_runtime is None:
        _event_classifier_runtime = EventClassifierRuntime()
    return _event_classifier_runtime
