
from gateway.quant.service import get_quant_system


def run_agent_task(payload: dict | None = None) -> dict:
    payload = payload or {}
    service = get_quant_system()
    return {
        "module": "autonomous_research_agent",
        "status": "ready",
        "benchmark": service.default_benchmark,
        "payload": payload,
    }
