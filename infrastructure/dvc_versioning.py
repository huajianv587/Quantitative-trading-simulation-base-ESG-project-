
def track(payload: dict | None = None) -> dict:
    payload = payload or {}
    return {
        "module": "dvc_versioning",
        "status": "tracked",
        "payload": payload,
    }
