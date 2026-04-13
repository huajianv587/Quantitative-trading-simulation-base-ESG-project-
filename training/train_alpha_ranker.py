from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor
from sklearn.metrics import accuracy_score, mean_absolute_error, mean_squared_error, roc_auc_score

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = PROJECT_ROOT / "data" / "alpha_ranker"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "model-serving" / "checkpoint" / "alpha_ranker"

FEATURE_COLUMNS = [
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


def load_frame(path: str | Path) -> pd.DataFrame:
    return pd.read_csv(path)


def infer_objective(target_column: str) -> str:
    return "binary" if target_column.startswith("label_") else "regression"


def build_model(backend: str, objective: str):
    normalized = backend.strip().lower()
    if normalized in {"auto", "xgboost"}:
        try:
            from xgboost import XGBClassifier, XGBRegressor  # type: ignore

            if objective == "binary":
                return XGBClassifier(
                    n_estimators=250,
                    max_depth=4,
                    learning_rate=0.05,
                    subsample=0.9,
                    colsample_bytree=0.9,
                    eval_metric="logloss",
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

            if objective == "binary":
                return LGBMClassifier(n_estimators=300, learning_rate=0.05, num_leaves=31), "lightgbm"
            return LGBMRegressor(n_estimators=300, learning_rate=0.05, num_leaves=31), "lightgbm"
        except Exception:
            if normalized == "lightgbm":
                raise
    if objective == "binary":
        return GradientBoostingClassifier(random_state=42), "sklearn_gbdt"
    return GradientBoostingRegressor(random_state=42), "sklearn_gbdt"


def evaluate_model(model, objective: str, features: pd.DataFrame, target: pd.Series) -> tuple[dict[str, float], list[float]]:
    if objective == "binary":
        probabilities = model.predict_proba(features)[:, 1] if hasattr(model, "predict_proba") else model.predict(features)
        predictions = [1 if value >= 0.5 else 0 for value in probabilities]
        metrics = {
            "accuracy": round(float(accuracy_score(target, predictions)), 6),
        }
        if len(set(target.tolist())) > 1:
            metrics["roc_auc"] = round(float(roc_auc_score(target, probabilities)), 6)
        return metrics, [float(value) for value in probabilities]

    predictions = [float(value) for value in model.predict(features)]
    spearman = float(pd.Series(predictions).corr(target.reset_index(drop=True), method="spearman") or 0.0)
    mse = float(mean_squared_error(target, predictions))
    metrics = {
        "rmse": round(mse**0.5, 6),
        "mae": round(float(mean_absolute_error(target, predictions)), 6),
        "spearman": round(spearman, 6),
    }
    return metrics, predictions


def main() -> int:
    parser = argparse.ArgumentParser(description="Train an alpha ranker using XGBoost, LightGBM, or a sklearn fallback.")
    parser.add_argument("--train-csv", default=str(DEFAULT_DATA_DIR / "train.csv"), help="Training csv path.")
    parser.add_argument("--val-csv", default=str(DEFAULT_DATA_DIR / "val.csv"), help="Validation csv path.")
    parser.add_argument("--target-column", default="forward_return_5d", help="Target column to learn.")
    parser.add_argument("--backend", default="auto", choices=["auto", "xgboost", "lightgbm", "sklearn_gbdt"], help="Model backend.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Checkpoint output directory.")
    args = parser.parse_args()

    train = load_frame(args.train_csv)
    val = load_frame(args.val_csv)
    objective = infer_objective(args.target_column)
    model, resolved_backend = build_model(args.backend, objective)
    train_x = train[FEATURE_COLUMNS].fillna(0.0)
    val_x = val[FEATURE_COLUMNS].fillna(0.0)
    train_y = train[args.target_column]
    val_y = val[args.target_column]
    model.fit(train_x, train_y)
    metrics, predictions = evaluate_model(model, objective, val_x, val_y)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    model_path = output_dir / "model.joblib"
    joblib.dump(model, model_path)

    metadata = {
      "backend": resolved_backend,
      "model_name": f"{resolved_backend}_alpha_ranker",
      "objective": objective,
      "target_column": args.target_column,
      "feature_names": FEATURE_COLUMNS,
      "prediction_min": min(predictions) if predictions else 0.0,
      "prediction_max": max(predictions) if predictions else 1.0,
      "metrics": metrics,
    }
    (output_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")

    if hasattr(model, "feature_importances_"):
        importance = pd.DataFrame(
            {
                "feature": FEATURE_COLUMNS,
                "importance": [float(value) for value in model.feature_importances_],
            }
        ).sort_values("importance", ascending=False)
        importance.to_csv(output_dir / "feature_importance.csv", index=False)

    print(json.dumps({"output_dir": str(output_dir), **metadata}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
