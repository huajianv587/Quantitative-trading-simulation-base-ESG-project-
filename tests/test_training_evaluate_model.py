from pathlib import Path

import pytest

pytest.importorskip("matplotlib")
pytest.importorskip("numpy")
pytest.importorskip("torch")
pytest.importorskip("transformers")
pytest.importorskip("peft")
pytest.importorskip("rouge_score")

from training import evaluate_model as evaluate_module


def test_default_paths_match_repository_layout():
    assert Path(evaluate_module.DEFAULT_CKPT).exists()
    assert Path(evaluate_module.DEFAULT_VAL).exists()


def test_create_visualizations_writes_expected_files(tmp_path):
    results = [
        {
            "id": 0,
            "question": "Q1",
            "ground_truth": "GT1",
            "prediction": "PR1",
            "rougeL": 0.42,
        },
        {
            "id": 1,
            "question": "Q2",
            "ground_truth": "GT2",
            "prediction": "PR2",
            "rougeL": 0.87,
        },
    ]

    outputs = evaluate_module.create_visualizations(results, tmp_path, "checkpoint")

    assert Path(outputs["histogram"]).exists()
    assert Path(outputs["trend"]).exists()
    assert Path(outputs["summary"]).exists()
    assert Path(outputs["html_report"]).exists()


def test_create_visualizations_rejects_empty_results(tmp_path):
    with pytest.raises(ValueError):
        evaluate_module.create_visualizations([], tmp_path, "checkpoint")
