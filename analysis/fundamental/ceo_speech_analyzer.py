from blueprint_runtime import build_analysis_output


def analyze_payload(payload: dict | None = None) -> dict:
    return build_analysis_output("ceo_speech_analyzer", payload, family="fundamental")
