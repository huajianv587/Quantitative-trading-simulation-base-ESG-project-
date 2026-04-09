
from gateway.agents.graph import run_agent


def run_workflow(question: str = "Summarize ESG quant status.") -> dict:
    return run_agent(question)
