
def run_module(payload: dict | None = None) -> dict:
    payload = payload or {}
    return {
        "module": "monte_carlo",
        "status": "ready",
        "payload": payload,
    }
