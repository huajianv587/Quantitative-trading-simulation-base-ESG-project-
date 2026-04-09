
def track(payload: dict | None = None) -> dict:
    payload = payload or {}
    return {
        "module": "drift_monitor",
        "status": "tracked",
        "payload": payload,
    }
