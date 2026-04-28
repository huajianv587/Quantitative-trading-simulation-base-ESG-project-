
from risk.drawdown_controller import evaluate_payload


def test_drawdown_controller_returns_result():
    result = evaluate_payload({"nav": [1.0, 0.92, 0.95], "max_drawdown_limit": 0.05})
    assert result["module"] == "drawdown_controller"
    assert result["status"] == "breach_detected"
    assert result["metrics"]["max_drawdown"] > 0.05
    assert result["breaches"][0]["metric"] == "max_drawdown"
    assert result["recommendations"]
