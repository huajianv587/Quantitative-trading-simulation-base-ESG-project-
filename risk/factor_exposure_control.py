
def evaluate_payload(payload: dict | None = None) -> dict:
    payload = payload or {}
    return {
        "module": "factor_exposure_control",
        "status": "evaluated",
        "payload": payload,
    }
