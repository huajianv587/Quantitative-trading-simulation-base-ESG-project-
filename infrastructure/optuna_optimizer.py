from blueprint_runtime import build_infrastructure_output


def track(payload: dict | None = None) -> dict:
    return build_infrastructure_output("optuna_optimizer", payload)
