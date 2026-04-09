
def apply_pipeline(records: list[dict] | None = None) -> dict:
    records = records or []
    return {
        "module": "outlier_detection",
        "records": records,
        "status": "processed",
    }
