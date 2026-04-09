
from fastapi import APIRouter

from gateway.quant.service import get_quant_system

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.get("/overview")
def analysis_overview():
    return get_quant_system().build_platform_overview()


@router.post("/research")
def run_analysis(payload: dict):
    return get_quant_system().run_research_pipeline(
        universe_symbols=payload.get("universe") or None,
        benchmark=payload.get("benchmark"),
        research_question=payload.get("research_question", ""),
        capital_base=payload.get("capital_base"),
        horizon_days=payload.get("horizon_days", 20),
    )
