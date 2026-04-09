
def evaluate_payload(payload: dict | None = None) -> dict:
    payload = payload or {}
    return {
        "module": "cvar_risk",
        "status": "evaluated",
        "payload": payload,
    }
