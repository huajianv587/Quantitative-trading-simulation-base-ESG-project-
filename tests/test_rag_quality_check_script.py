import json
from pathlib import Path

from scripts import rag_quality_check


def test_load_samples_normalizes_optional_fields(tmp_path: Path):
    sample_file = tmp_path / "samples.json"
    sample_file.write_text(
        json.dumps(
            [
                {
                    "name": "demo",
                    "question": "Analyze Singtel ESG performance",
                    "require_scores": True,
                }
            ]
        ),
        encoding="utf-8",
    )

    samples = rag_quality_check.load_samples(sample_file)

    assert samples[0]["name"] == "demo"
    assert samples[0]["require_scores"] is True
    assert samples[0]["min_answer_chars"] == 120
    assert samples[0]["min_confidence"] == 0.35


def test_evaluate_result_flags_short_low_confidence_answers():
    sample = {
        "name": "demo",
        "question": "question",
        "require_scores": True,
        "min_answer_chars": 50,
        "min_confidence": 0.6,
    }
    result = rag_quality_check.evaluate_result(
        {
            "sample": sample,
            "status_code": 200,
            "payload": {
                "answer": "Too short",
                "confidence": 0.42,
                "esg_scores": {},
                "analysis_summary": "",
            },
            "latency_seconds": 1.2,
        }
    )

    assert result["passed"] is False
    assert "answer_too_short:9<50" in result["checks"]
    assert "confidence_too_low:0.42<0.60" in result["checks"]
    assert "missing_esg_scores" in result["checks"]
    assert "missing_analysis_summary" in result["checks"]


def test_summarize_results_counts_pass_and_fail():
    summary = rag_quality_check.summarize_results(
        [
            {
                "sample": {"name": "ok"},
                "passed": True,
                "checks": [],
                "status_code": 200,
                "confidence": 0.7,
                "latency_seconds": 2.0,
            },
            {
                "sample": {"name": "bad"},
                "passed": False,
                "checks": ["missing_esg_scores"],
                "status_code": 200,
                "confidence": 0.3,
                "latency_seconds": 4.0,
            },
        ]
    )

    assert summary["passed"] == 1
    assert summary["failed"] == 1
    assert summary["pass_rate"] == 0.5
    assert summary["average_confidence"] == 0.5
    assert summary["average_latency_seconds"] == 3.0
    assert summary["failed_samples"][0]["name"] == "bad"
