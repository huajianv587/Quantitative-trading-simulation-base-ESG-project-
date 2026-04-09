
def apply_pipeline(records: list[dict] | None = None) -> dict:
    records = records or []
    return {
        "module": "adjustment",
        "records": records,
        "status": "processed",
    }
