
from analysis.factors.multi_factor_scoring import analyze_payload


def test_factor_scoring_returns_summary():
    result = analyze_payload({"records": [{"symbol": "AAPL"}]})
    assert result["module"] == "multi_factor_scoring"
