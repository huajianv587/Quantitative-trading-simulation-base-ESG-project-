
from fastapi import APIRouter

from gateway.agents.graph import run_agent

router = APIRouter(prefix="/agents", tags=["agents"])


@router.post("/run")
def run_agents(payload: dict):
    question = payload.get("question", "Summarize the current ESG quant setup.")
    session_id = payload.get("session_id", "")
    return run_agent(question, session_id=session_id)
