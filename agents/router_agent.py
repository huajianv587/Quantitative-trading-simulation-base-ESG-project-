from blueprint_runtime import build_agent_output


def run_agent_task(payload: dict | None = None) -> dict:
    return build_agent_output("router_agent", payload)
