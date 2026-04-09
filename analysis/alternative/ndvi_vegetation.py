
def analyze_payload(payload: dict | None = None) -> dict:
    payload = payload or {}
    records = payload.get("records", [])
    return {
        "module": "ndvi_vegetation",
        "records": records,
        "summary": "Analysis scaffold ready",
    }
