from blueprint_runtime import build_report_output


def build_output(payload: dict | None = None) -> dict:
    return build_report_output("factor_heatmap", payload)
