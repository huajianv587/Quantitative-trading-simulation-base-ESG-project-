
def evaluate_payload(payload: dict | None = None) -> dict:
    payload = payload or {}
    return {
        "module": "sharpe_monitor",
        "status": "evaluated",
        "payload": payload,
    }
