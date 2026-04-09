
def evaluate_payload(payload: dict | None = None) -> dict:
    payload = payload or {}
    return {
        "module": "drawdown_controller",
        "status": "evaluated",
        "payload": payload,
    }
