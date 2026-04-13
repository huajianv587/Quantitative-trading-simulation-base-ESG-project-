from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from sklearn.preprocessing import LabelEncoder

from gateway.quant.p2_decision import P2_MODEL_SPECS
from training.p1_training_lib import build_model, evaluate_predictions


def load_frame(path: str | Path) -> pd.DataFrame:
    return pd.read_csv(path)


def fit_model(train: pd.DataFrame, val: pd.DataFrame, model_key: str, backend: str) -> dict[str, Any]:
    spec = P2_MODEL_SPECS[model_key]
    feature_names = list(spec["feature_names"])
    train_x = train[feature_names].fillna(0.0)
    val_x = val[feature_names].fillna(0.0)
    train_y = train[spec["target_column"]]
    val_y = val[spec["target_column"]]

    if spec["objective"] == "multiclass":
        label_encoder = LabelEncoder()
        train_y_encoded = label_encoder.fit_transform(train_y)
        model, resolved_backend = build_model(backend, "multiclass", num_classes=len(label_encoder.classes_))
        model.fit(train_x, train_y_encoded)
        predicted_encoded = model.predict(val_x)
        classes = [str(item) for item in label_encoder.classes_]
        predictions = [
            classes[max(0, min(len(classes) - 1, int(round(float(value)))))]
            for value in predicted_encoded
        ]
        metrics = evaluate_predictions("multiclass", val_y, predictions)
        metadata = {
            "backend": resolved_backend,
            "model_name": f"{resolved_backend}_{model_key}",
            "objective": spec["objective"],
            "target_column": spec["target_column"],
            "feature_names": feature_names,
            "metrics": metrics,
            "classes": classes,
            "prediction_min": 0.0,
            "prediction_max": 1.0,
        }
        return {"model": model, "metadata": metadata}

    model, resolved_backend = build_model(backend, "regression")
    model.fit(train_x, train_y)
    predictions = [float(value) for value in model.predict(val_x)]
    metrics = evaluate_predictions("regression", val_y, predictions)
    metadata = {
        "backend": resolved_backend,
        "model_name": f"{resolved_backend}_{model_key}",
        "objective": spec["objective"],
        "target_column": spec["target_column"],
        "feature_names": feature_names,
        "metrics": metrics,
        "prediction_min": float(min(predictions) if predictions else train_y.min()),
        "prediction_max": float(max(predictions) if predictions else train_y.max()),
    }
    return {"model": model, "metadata": metadata}


def persist_model(output_dir: Path, model_key: str, model: Any, metadata: dict[str, Any]) -> None:
    target_dir = output_dir / model_key
    target_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, target_dir / "model.joblib")
    (target_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    if hasattr(model, "feature_importances_"):
        pd.DataFrame(
            {
                "feature": metadata.get("feature_names", []),
                "importance": [float(value) for value in model.feature_importances_],
            }
        ).sort_values("importance", ascending=False).to_csv(target_dir / "feature_importance.csv", index=False)


def fit_and_persist_suite(
    *,
    train_snapshots: pd.DataFrame,
    val_snapshots: pd.DataFrame,
    train_signals: pd.DataFrame,
    val_signals: pd.DataFrame,
    output_dir: str | Path,
    backend: str,
) -> dict[str, Any]:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    manifest = {
        "generated_at": pd.Timestamp.utcnow().isoformat(),
        "suite_version": pd.Timestamp.utcnow().strftime("p2-selector-%Y%m%d%H%M%S"),
        "backend_requested": backend,
        "models": [],
    }
    for model_key in P2_MODEL_SPECS:
        if model_key == "strategy_classifier":
            trained = fit_model(train_snapshots, val_snapshots, model_key, backend)
        else:
            trained = fit_model(train_signals, val_signals, model_key, backend)
        persist_model(root, model_key, trained["model"], trained["metadata"])
        manifest["models"].append(
            {
                "key": model_key,
                "backend": trained["metadata"]["backend"],
                "model_name": trained["metadata"]["model_name"],
                "metrics": trained["metadata"]["metrics"],
                "target_column": trained["metadata"]["target_column"],
            }
        )
    (root / "suite_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest
