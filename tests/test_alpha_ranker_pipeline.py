from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor

from gateway.quant.alpha_ranker import AlphaRankerRuntime
from gateway.quant.models import FactorScore, ResearchSignal
from training.prepare_alpha_data import FEATURE_COLUMNS, split_dataset, synthetic_dataset


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _signal(symbol: str, overall_score: float, momentum: float) -> ResearchSignal:
    return ResearchSignal(
        symbol=symbol,
        company_name=symbol,
        sector="Technology",
        thesis=f"{symbol} signal",
        action="long",
        confidence=0.8,
        expected_return=0.05,
        risk_score=30.0,
        overall_score=overall_score,
        e_score=70.0,
        s_score=68.0,
        g_score=72.0,
        factor_scores=[
            FactorScore(name="momentum", value=momentum, contribution=0.34, description="m"),
            FactorScore(name="quality", value=80, contribution=0.16, description="q"),
            FactorScore(name="value", value=55, contribution=0.10, description="v"),
            FactorScore(name="alternative_data", value=66, contribution=0.12, description="a"),
            FactorScore(name="regime_fit", value=60, contribution=0.12, description="r"),
            FactorScore(name="esg_delta", value=72, contribution=0.16, description="e"),
        ],
    )


def test_alpha_ranker_runtime_loads_checkpoint_and_reranks(tmp_path):
    train = synthetic_dataset(["AAPL", "MSFT"], rows_per_symbol=40)
    model = GradientBoostingRegressor(random_state=42)
    model.fit(train[FEATURE_COLUMNS], train["forward_return_5d"])
    joblib.dump(model, tmp_path / "model.joblib")
    (tmp_path / "metadata.json").write_text(
        json.dumps(
            {
                "backend": "sklearn_gbdt",
                "model_name": "unit_test_ranker",
                "feature_names": FEATURE_COLUMNS,
                "prediction_min": -0.1,
                "prediction_max": 0.1,
            }
        ),
        encoding="utf-8",
    )

    ranker = AlphaRankerRuntime(tmp_path)
    ranked = ranker.rerank([_signal("AAPL", 70, 85), _signal("MSFT", 66, 52)])

    assert ranker.available() is True
    assert ranked[0].alpha_model_name == "unit_test_ranker"
    assert ranked[0].alpha_rank == 1
    assert ranked[0].alpha_model_score is not None


def test_alpha_ranker_train_and_evaluate_scripts_run_on_synthetic_data(tmp_path):
    dataset = synthetic_dataset(["AAPL", "MSFT", "TSLA"], rows_per_symbol=50)
    train, val = split_dataset(dataset, 0.2)
    data_dir = tmp_path / "data"
    ckpt_dir = tmp_path / "checkpoint"
    data_dir.mkdir(parents=True, exist_ok=True)
    train.to_csv(data_dir / "train.csv", index=False)
    val.to_csv(data_dir / "val.csv", index=False)

    train_cmd = [
        sys.executable,
        "training/train_alpha_ranker.py",
        "--train-csv",
        str(data_dir / "train.csv"),
        "--val-csv",
        str(data_dir / "val.csv"),
        "--backend",
        "sklearn_gbdt",
        "--output-dir",
        str(ckpt_dir),
    ]
    eval_cmd = [
        sys.executable,
        "training/evaluate_alpha_ranker.py",
        "--checkpoint-dir",
        str(ckpt_dir),
        "--val-csv",
        str(data_dir / "val.csv"),
    ]

    train_result = subprocess.run(train_cmd, cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=60, check=False)
    eval_result = subprocess.run(eval_cmd, cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=60, check=False)

    assert train_result.returncode == 0, train_result.stderr
    assert eval_result.returncode == 0, eval_result.stderr
    assert (ckpt_dir / "model.joblib").exists()
    assert (ckpt_dir / "metadata.json").exists()
    assert (ckpt_dir / "evaluation.json").exists()
