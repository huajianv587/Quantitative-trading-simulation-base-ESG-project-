from gateway.trading.service import TradingAgentService


class _RiskFallbackStore:
    def __init__(self):
        self.saved = []

    def list_debate_runs(self, *, limit=1, symbol=None):
        return []

    def save_risk_approval(self, approval):
        payload = approval.model_dump(mode="json")
        self.saved.append(payload)
        return payload


def test_risk_evaluate_returns_blocked_record_when_debate_is_missing():
    service = object.__new__(TradingAgentService)
    service.store = _RiskFallbackStore()

    payload = service.evaluate_risk(symbol="AAPL", signal_ttl_minutes=120)

    assert payload["symbol"] == "AAPL"
    assert payload["verdict"] == "reject"
    assert payload["approved_action"] == "block"
    assert payload["hard_blocks"] == ["missing_debate_run"]
    assert payload["metadata"]["next_action"] == "run_debate_before_risk_approval"
    assert service.store.saved
