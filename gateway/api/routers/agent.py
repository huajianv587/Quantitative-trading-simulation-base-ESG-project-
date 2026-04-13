from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Body, HTTPException, Query, Request

from gateway.api.schemas import AnalyzeRequest, ESGScoreRequest, QueryRequest, QueryResponse
from gateway.app_runtime import runtime
from gateway.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.post("/session")
def new_session(session_id: str, user_id: str | None = None):
    if runtime.create_session is None:
        raise HTTPException(status_code=503, detail="Database module not available")
    runtime.create_session(session_id=session_id, user_id=user_id)
    return {"session_id": session_id, "created": True}


@router.post("/query", response_model=QueryResponse)
def query(req: QueryRequest, request: Request):
    engine = request.app.state.query_engine
    if engine is None:
        raise HTTPException(status_code=503, detail="RAG engine not ready.")

    runtime.ensure_session(req.session_id)
    history = runtime.get_history(req.session_id, limit=10) if runtime.get_history else []
    context_prefix = ""
    if history:
        lines = [f"{message['role'].upper()}: {message['content']}" for message in history]
        context_prefix = "【对话历史】\n" + "\n".join(lines) + "\n\n【当前问题】\n"

    full_question = context_prefix + req.question
    response = engine.query(full_question)
    answer = str(response)

    if runtime.save_message:
        runtime.save_message(req.session_id, "user", req.question)
        runtime.save_message(req.session_id, "assistant", answer)

    return QueryResponse(
        session_id=req.session_id,
        question=req.question,
        answer=answer,
    )


@router.get("/history/{session_id}")
def history(session_id: str, limit: int = 20):
    if runtime.get_history is None:
        raise HTTPException(status_code=503, detail="Database module not available")
    return {"session_id": session_id, "messages": runtime.get_history(session_id, limit=limit)}


@router.post("/agent/analyze")
def analyze_esg(
    payload: Optional[AnalyzeRequest] = Body(default=None),
    question: Optional[str] = Query(default=None),
    session_id: str = Query(default=""),
):
    actual_question = payload.question if payload else question
    actual_session_id = payload.session_id if payload and payload.session_id else session_id

    if not actual_question:
        raise HTTPException(status_code=422, detail="question is required")
    if runtime.run_agent is None:
        raise HTTPException(status_code=503, detail="Agent module not available")

    try:
        result = runtime.run_agent(actual_question, session_id=actual_session_id)

        if actual_session_id and runtime.save_message:
            runtime.ensure_session(actual_session_id)
            runtime.save_message(actual_session_id, "user", actual_question)
            runtime.save_message(actual_session_id, "assistant", result.get("final_answer", ""))

        return {
            "question": actual_question,
            "answer": result.get("final_answer"),
            "esg_scores": result.get("esg_scores", {}),
            "confidence": result.get("confidence", 0),
            "analysis_summary": result.get("analysis_summary", ""),
        }
    except Exception as exc:
        logger.error(f"Analysis error: {exc}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}")


@router.post("/agent/esg-score")
def get_esg_score(req: ESGScoreRequest):
    if runtime.esg_scorer is None and runtime.data_source_manager is None:
        runtime.ensure_optional_services()
    if not runtime.esg_scorer:
        raise HTTPException(status_code=503, detail="ESG Scorer not ready")

    try:
        logger.info(f"[ESG Score] Computing score for {req.company}")

        if not runtime.data_source_manager:
            raise HTTPException(status_code=503, detail="Data Source Manager not ready")

        company_data = runtime.data_source_manager.fetch_company_data(
            req.company,
            ticker=req.ticker,
        )

        company_payload = runtime.serialize_model(company_data) or {}
        esg_report = runtime.esg_scorer.score_esg(
            req.company,
            company_payload,
            peers=req.peers,
        )

        visualizations = {}
        if req.include_visualization and runtime.esg_visualizer:
            visualizations = runtime.esg_visualizer.generate_report_visual(esg_report)

        return {
            "esg_report": runtime.serialize_model(esg_report),
            "visualizations": visualizations if req.include_visualization else None,
            "success": True,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"ESG Score error: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
