from blueprint_runtime import apply_governance_pipeline


def apply_pipeline(records: list[dict] | None = None) -> dict:
    return apply_governance_pipeline("data_lineage", records)
