from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

from gateway.quant.models import FactorScore, ResearchSignal
from gateway.quant.p1_stack import P1ModelSuiteRuntime
from training.p1_training_lib import fit_and_persist_suite
from training.prepare_alpha_data import split_dataset
from training.prepare_p1_data import enrich_p1_features, synthetic_p1_dataset


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _signal(symbol: str, momentum: float, quality: float, overall: float) -> ResearchSignal:
    return ResearchSignal(
        symbol=symbol,
        company_name=symbol,
        sector="Technology",
        thesis=f"{symbol} P1 signal",
        action="long",
        confidence=0.82,
        expected_return=0.045,
        risk_score=28.0,
        overall_score=overall,
        e_score=72.0,
        s_score=69.0,
        g_score=75.0,
        alpha_model_score=0.68,
        alpha_model_name="baseline_alpha",
        factor_scores=[
            FactorScore(name="momentum", value=momentum, contribution=0.18, description="m"),
            FactorScore(name="quality", value=quality, contribution=0.22, description="q"),
            FactorScore(name="value", value=58.0, contribution=0.14, description="v"),
            FactorScore(name="alternative_data", value=66.0, contribution=0.19, description="a"),
            FactorScore(name="regime_fit", value=64.0, contribution=0.11, description="r"),
            FactorScore(name="esg_delta", value=71.0, contribution=0.16, description="e"),
        ],
    )


def test_p1_runtime_loads_suite_and_enriches_signals(tmp_path):
    dataset = synthetic_p1_dataset(["AAPL", "MSFT", "TSLA"], rows_per_symbol=70)
    train, val = split_dataset(dataset, 0.25)
    fit_and_persist_suite(train=train, val=val, output_dir=tmp_path, backend="sklearn_gbdt")
    data_dir = tmp_path / "data"
    sequence_dir = tmp_path / "sequence"
    data_dir.mkdir(parents=True, exist_ok=True)
    dataset.to_csv(data_dir / "full_dataset.csv", index=False)
    subprocess.run(
        [
            sys.executable,
            "training/train_sequence_forecaster.py",
            "--full-csv",
            str(data_dir / "full_dataset.csv"),
            "--output-dir",
            str(sequence_dir),
            "--architecture",
            "lstm",
            "--epochs",
            "1",
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=180,
        check=True,
    )

    runtime = P1ModelSuiteRuntime(tmp_path, sequence_checkpoint_dir=sequence_dir)
    ranked = runtime.enrich_and_rerank(
        [
            _signal("AAPL", 88.0, 84.0, 79.0),
            _signal("MSFT", 72.0, 78.0, 73.0),
            _signal("TSLA", 55.0, 61.0, 64.0),
        ]
    )

    assert runtime.available() is True
    assert runtime.status()["loaded_models"] == 5
    assert runtime.status()["sequence_forecaster"]["available"] is True
    assert ranked[0].p1_stack_score is not None
    assert ranked[0].predicted_return_5d is not None
    assert ranked[0].sequence_return_5d is not None
    assert ranked[0].predicted_volatility_10d is not None
    assert ranked[0].predicted_drawdown_20d is not None
    assert ranked[0].regime_label in {"risk_on", "neutral", "risk_off"}
    assert ranked[0].alpha_rank == 1


def test_p1_training_scripts_run_on_synthetic_data(tmp_path):
    dataset = synthetic_p1_dataset(["AAPL", "MSFT", "TSLA"], rows_per_symbol=90)
    train, val = split_dataset(dataset, 0.2)
    data_dir = tmp_path / "data"
    ckpt_dir = tmp_path / "checkpoint"
    data_dir.mkdir(parents=True, exist_ok=True)
    dataset.to_csv(data_dir / "full_dataset.csv", index=False)
    train.to_csv(data_dir / "train.csv", index=False)
    val.to_csv(data_dir / "val.csv", index=False)

    commands = [
        [
            sys.executable,
            "training/train_p1_stack.py",
            "--train-csv",
            str(data_dir / "train.csv"),
            "--val-csv",
            str(data_dir / "val.csv"),
            "--backend",
            "sklearn_gbdt",
            "--output-dir",
            str(ckpt_dir),
        ],
        [
            sys.executable,
            "training/evaluate_p1_stack.py",
            "--checkpoint-dir",
            str(ckpt_dir),
            "--val-csv",
            str(data_dir / "val.csv"),
        ],
        [
            sys.executable,
            "training/run_p1_walk_forward.py",
            "--full-csv",
            str(data_dir / "full_dataset.csv"),
            "--backend",
            "sklearn_gbdt",
            "--train-dates",
            "40",
            "--test-dates",
            "15",
            "--max-windows",
            "2",
            "--output-dir",
            str(ckpt_dir),
        ],
        [
            sys.executable,
            "training/train_sequence_forecaster.py",
            "--full-csv",
            str(data_dir / "full_dataset.csv"),
            "--output-dir",
            str(tmp_path / "sequence"),
            "--architecture",
            "lstm",
            "--dry-run",
        ],
        [
            sys.executable,
            "training/download_p1_assets.py",
        ],
    ]

    for command in commands:
        result = subprocess.run(command, cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=180, check=False)
        assert result.returncode == 0, result.stderr

    suite_manifest = json.loads((ckpt_dir / "suite_manifest.json").read_text(encoding="utf-8"))
    evaluation = json.loads((ckpt_dir / "evaluation.json").read_text(encoding="utf-8"))
    walk_forward = json.loads((ckpt_dir / "walk_forward.json").read_text(encoding="utf-8"))
    sequence_manifest = json.loads((tmp_path / "sequence" / "sequence_manifest.json").read_text(encoding="utf-8"))

    assert len(suite_manifest["models"]) == 5
    assert "p1_rank_performance" in evaluation
    assert walk_forward["window_count"] >= 1
    assert sequence_manifest["architecture"] == "lstm"
    assert (PROJECT_ROOT / "training" / "p1_assets" / "p1_asset_manifest.json").exists()
