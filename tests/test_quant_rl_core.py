from quant_rl.service.quant_service import QuantRLService


def test_overview_has_frontier_stack():
    overview = QuantRLService().overview()
    assert 'frontier' in overview['stack']
