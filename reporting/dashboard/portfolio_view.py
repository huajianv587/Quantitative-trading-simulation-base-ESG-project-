
from gateway.quant.service import get_quant_system


def build_output(payload: dict | None = None) -> dict:
    payload = payload or {}
    return {
        "module": "portfolio_view",
        "status": "ready",
        "overview": get_quant_system().build_platform_overview(),
        "payload": payload,
    }
