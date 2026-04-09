
def run_module(payload: dict | None = None) -> dict:
    payload = payload or {}
    return {
        "module": "performance_attribution",
        "status": "ready",
        "payload": payload,
    }
