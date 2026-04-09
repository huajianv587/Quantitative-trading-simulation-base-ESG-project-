
def apply_pipeline(records: list[dict] | None = None) -> dict:
    records = records or []
    return {
        "module": "missing_values",
        "records": records,
        "status": "processed",
    }
