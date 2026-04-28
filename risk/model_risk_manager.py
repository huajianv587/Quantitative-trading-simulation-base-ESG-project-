from blueprint_runtime import build_risk_output


def evaluate_payload(payload: dict | None = None) -> dict:
    return build_risk_output("model_risk_manager", payload)
