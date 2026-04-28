from blueprint_runtime import build_report_output


def build_output(payload: dict | None = None) -> dict:
    return build_report_output("portfolio_view", payload)
