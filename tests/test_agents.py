
from agents.strategy_agent import run_agent_task


def test_strategy_agent_returns_payload():
    result = run_agent_task({"universe": ["AAPL", "MSFT"]})
    assert "status" in result
