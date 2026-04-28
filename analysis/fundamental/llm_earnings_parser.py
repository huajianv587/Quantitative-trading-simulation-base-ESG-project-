from blueprint_runtime import build_analysis_output


def analyze_payload(payload: dict | None = None) -> dict:
    return build_analysis_output("llm_earnings_parser", payload, family="fundamental")
