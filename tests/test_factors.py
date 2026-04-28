
from analysis.factors.multi_factor_scoring import analyze_payload


def test_factor_scoring_returns_summary():
    result = analyze_payload(
        {
            "records": [
                {"symbol": "AAPL", "score": 82.0, "expected_return": 0.021, "confidence": 0.84},
                {"symbol": "MSFT", "score": 76.0, "expected_return": 0.017, "confidence": 0.79},
            ]
        }
    )
    assert result["module"] == "multi_factor_scoring"
    assert result["status"] == "completed"
    assert result["record_count"] == 2
    assert result["coverage"]["top_symbols"][0] == "AAPL"
    assert result["summary"]["average_score"] >= 75.0
    assert "score" in result["numeric_summary"]
