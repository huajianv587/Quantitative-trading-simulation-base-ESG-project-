from blueprint_runtime import build_risk_output


def evaluate_payload(payload: dict | None = None) -> dict:
    return build_risk_output("sharpe_monitor", payload)
