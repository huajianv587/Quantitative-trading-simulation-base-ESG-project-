
def run_module(payload: dict | None = None) -> dict:
    payload = payload or {}
    return {
        "module": "walk_forward",
        "status": "ready",
        "payload": payload,
    }
