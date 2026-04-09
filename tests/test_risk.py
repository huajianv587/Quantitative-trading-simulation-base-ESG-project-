
from risk.drawdown_controller import evaluate_payload


def test_drawdown_controller_returns_result():
    result = evaluate_payload({"nav": [1.0, 0.96, 0.99]})
    assert result["module"] == "drawdown_controller"
