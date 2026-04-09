
def evaluate_payload(payload: dict | None = None) -> dict:
    payload = payload or {}
    return {
        "module": "compliance_checker",
        "status": "evaluated",
        "payload": payload,
    }
