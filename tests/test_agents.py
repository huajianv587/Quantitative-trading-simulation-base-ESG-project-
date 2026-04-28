
from agents.strategy_agent import run_agent_task


def test_strategy_agent_returns_payload():
    result = run_agent_task({"universe": ["AAPL", "MSFT"]})
    assert result["status"] == "completed"
    assert result["focus_symbols"] == ["AAPL", "MSFT"]
    assert result["actions"]
    assert result["benchmark"]
