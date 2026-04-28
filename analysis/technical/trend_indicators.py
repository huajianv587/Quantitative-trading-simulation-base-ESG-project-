from blueprint_runtime import build_analysis_output


def analyze_payload(payload: dict | None = None) -> dict:
    return build_analysis_output("trend_indicators", payload, family="technical")
