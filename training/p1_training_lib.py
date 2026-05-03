from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor, RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score, mean_absolute_error, mean_squared_error
from sklearn.preprocessing import LabelEncoder

from gateway.quant.p1_stack import (
    P1_FEATURE_COLUMNS,
    P1_MODEL_SPECS,
    compute_p1_stack_score,
)


def load_frame(path: str | Path) -> pd.DataFrame:
    return pd.read_csv(path)


def build_model(backend: str, objective: str, num_classes: int = 3):
    normalized = backend.strip().lower()
    if normalized in {"auto", "xgboost"}:
        try:
            from xgboost import XGBClassifier, XGBRegressor  # type: ignore

            if objective == "multiclass":
                return XGBClassifier(
                    n_estimators=250,
                    max_depth=4,
                    learning_rate=0.05,
                    subsample=0.9,
                    colsample_bytree=0.9,
                    objective="multi:softprob",
                    num_class=num_classes,
                ), "xgboost"
            return XGBRegressor(
                n_estimators=250,
                max_depth=4,
                learning_rate=0.05,
                subsample=0.9,
                colsample_bytree=0.9,
            ), "xgboost"
        except Exception:
            if normalized == "xgboost":
                raise
    if normalized in {"auto", "lightgbm"}:
        try:
            from lightgbm import LGBMClassifier, LGBMRegressor  # type: ignore

            if objective == "multiclass":
                return LGBMClassifier(
                    n_estimators=300,
                    learning_rate=0.05,
                    num_leaves=31,
                    objective="multiclass",
                    num_class=num_classes,
                ), "lightgbm"
            return LGBMRegressor(n_estimators=300, learning_rate=0.05, num_leaves=31), "lightgbm"
        except Exception:
            if normalized == "lightgbm":
                raise
    if normalized in {"auto", "catboost"}:
        try:
            from catboost import CatBoostClassifier, CatBoostRegressor  # type: ignore

            if objective == "multiclass":
                return CatBoostClassifier(loss_function="MultiClass", iterations=250, depth=5, learning_rate=0.05, verbose=False), "catboost"
            return CatBoostRegressor(loss_function="RMSE", iterations=250, depth=5, learning_rate=0.05, verbose=False), "catboost"
        except Exception:
            if normalized == "catboost":
                raise
    if objective == "multiclass":
        return RandomForestClassifier(n_estimators=300, max_depth=6, random_state=42), "sklearn_rf"
    return GradientBoostingRegressor(random_state=42), "sklearn_gbdt"


def evaluate_predictions(
    objective: str,
    target: pd.Series,
    predictions: list[float] | list[str],
) -> dict[str, float]:
    if objective == "multiclass":
        predicted_labels = [str(item) for item in predictions]
        return {
            "accuracy": round(float(accuracy_score(target, predicted_labels)), 6),
            "f1_macro": round(float(f1_score(target, predicted_labels, average="macro")), 6),
        }

    values = [float(value) for value in predictions]
    spearman = float(pd.Series(values).corr(target.reset_index(drop=True), method="spearman") or 0.0)
    mse = float(mean_squared_error(target, values))
    return {
        "rmse": round(mse**0.5, 6),
        "mae": round(float(mean_absolute_error(target, values)), 6),
        "spearman": round(spearman, 6),
    }


def fit_suite_model(train: pd.DataFrame, val: pd.DataFrame, model_key: str, backend: str) -> dict[str, Any]:
    spec = P1_MODEL_SPECS[model_key]
    feature_names = list(P1_FEATURE_COLUMNS)
    train_x = train[feature_names].fillna(0.0)
    val_x = val[feature_names].fillna(0.0)
    train_y = train[spec["target_column"]]
    val_y = val[spec["target_column"]]

    label_encoder = None
    if spec["objective"] == "multiclass":
        label_encoder = LabelEncoder()
        train_y_encoded = label_encoder.fit_transform(train_y)
        model, resolved_backend = build_model(backend, spec["objective"], num_classes=len(label_encoder.classes_))
        model.fit(train_x, train_y_encoded)
        predicted_encoded = model.predict(val_x)
        predictions = label_encoder.inverse_transform(predicted_encoded).tolist()
        metrics = evaluate_predictions(spec["objective"], val_y, predictions)
        metadata = {
            "backend": resolved_backend,
            "model_name": f"{resolved_backend}_{model_key}",
            "objective": spec["objective"],
            "target_column": spec["target_column"],
            "feature_names": feature_names,
            "metrics": metrics,
            "classes": [str(item) for item in label_encoder.classes_],
            "prediction_min": 0.0,
            "prediction_max": 1.0,
        }
        return {"model": model, "metadata": metadata}

    model, resolved_backend = build_model(backend, spec["objective"])
    model.fit(train_x, train_y)
    predictions = [float(value) for value in model.predict(val_x)]
    metrics = evaluate_predictions(spec["objective"], val_y, predictions)
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


def persist_suite_model(output_dir: Path, model_key: str, model, metadata: dict[str, Any]) -> None:
    target_dir = output_dir / model_key
    target_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, target_dir / "model.joblib")
    (target_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    if hasattr(model, "feature_importances_"):
        importance = pd.DataFrame(
            {
                "feature": P1_FEATURE_COLUMNS,
                "importance": [float(value) for value in model.feature_importances_],
            }
        ).sort_values("importance", ascending=False)
        importance.to_csv(target_dir / "feature_importance.csv", index=False)


def fit_and_persist_suite(
    train: pd.DataFrame,
    val: pd.DataFrame,
    output_dir: str | Path,
    backend: str,
) -> dict[str, Any]:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    now_utc = pd.Timestamp.now(tz="UTC")
    manifest = {
        "generated_at": now_utc.isoformat(),
        "suite_version": now_utc.strftime("p1-suite-%Y%m%d%H%M%S"),
        "backend_requested": backend,
        "models": [],
    }
    for model_key in P1_MODEL_SPECS:
        trained = fit_suite_model(train, val, model_key, backend)
        persist_suite_model(root, model_key, trained["model"], trained["metadata"])
        manifest["models"].append(
            {
                "key": model_key,
                "backend": trained["metadata"]["backend"],
                "model_name": trained["metadata"]["model_name"],
                "objective": trained["metadata"]["objective"],
                "target_column": trained["metadata"]["target_column"],
                "metrics": trained["metadata"]["metrics"],
            }
        )
    (root / "suite_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def predict_suite(checkpoint_dir: str | Path, frame: pd.DataFrame) -> pd.DataFrame:
    root = Path(checkpoint_dir)
    local = frame.copy()
    for feature in P1_FEATURE_COLUMNS:
        if feature not in local.columns:
            local[feature] = 0.0
    local = local.fillna(0.0)
    outputs = pd.DataFrame(index=local.index)
    for model_key, spec in P1_MODEL_SPECS.items():
        metadata = json.loads((root / model_key / "metadata.json").read_text(encoding="utf-8"))
        model = joblib.load(root / model_key / "model.joblib")
        features = [str(item) for item in metadata.get("feature_names", P1_FEATURE_COLUMNS)]
        if spec["objective"] == "multiclass":
            if hasattr(model, "predict_proba"):
                probabilities = model.predict_proba(local[features])
                classes = [str(item) for item in metadata.get("classes", [])]
                best = probabilities.argmax(axis=1)
                outputs["regime_label"] = [classes[index] for index in best]
                outputs["regime_probability"] = [float(probabilities[row_index][best[row_index]]) for row_index in range(len(best))]
            else:
                outputs["regime_label"] = [str(item) for item in model.predict(local[features])]
                outputs["regime_probability"] = 0.6
        else:
            outputs[f"predicted_{model_key}"] = [float(value) for value in model.predict(local[features])]
    return outputs


def score_p1_frame(frame: pd.DataFrame) -> pd.Series:
    values = []
    for _, row in frame.iterrows():
        values.append(
            compute_p1_stack_score(
                alpha_baseline=float(row.get("alpha_baseline", row.get("target_alpha_score", 0.5))),
                predicted_return_1d=float(row.get("predicted_return_1d", row.get("forward_return_1d", 0.0))),
                predicted_return_5d=float(row.get("predicted_return_5d", row.get("forward_return_5d", 0.0))),
                predicted_volatility_10d=float(row.get("predicted_volatility_10d", row.get("future_volatility_10d", 0.15))),
                predicted_drawdown_20d=float(row.get("predicted_drawdown_20d", row.get("future_max_drawdown_20d", 0.10))),
                regime_label=str(row.get("regime_label", "neutral")),
                regime_probability=float(row.get("regime_probability", 0.6)),
            )
        )
    return pd.Series(values, index=frame.index, dtype="float64")


def summarize_rank_performance(scored_frame: pd.DataFrame, top_n: int = 3) -> dict[str, float]:
    if scored_frame.empty:
        return {"mean_return_5d": 0.0, "sharpe": 0.0, "hit_rate": 0.0}
    daily_returns: list[float] = []
    for _, day_slice in scored_frame.groupby("date"):
        top = day_slice.sort_values("p1_stack_score", ascending=False).head(top_n)
        if not top.empty:
            daily_returns.append(float(top["forward_return_5d"].mean()))
    if not daily_returns:
        return {"mean_return_5d": 0.0, "sharpe": 0.0, "hit_rate": 0.0}
    series = pd.Series(daily_returns, dtype="float64")
    return {
        "mean_return_5d": round(float(series.mean()), 6),
        "sharpe": round(float(series.mean() / ((series.std(ddof=0) or 1e-6)) * (252 ** 0.5)), 6),
        "hit_rate": round(float((series > 0).mean()), 6),
    }
