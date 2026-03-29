import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from rag.rag_main import get_query_engine
from db.supabase_client import save_message, get_history, create_session
from scheduler.orchestrator import get_orchestrator
from agents.graph import run_agent

app = FastAPI(title="ESG Agentic RAG Copilot")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── RAG 启动时初始化，只跑一次 ─────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    print("[Startup] Initializing RAG engine...")
    app.state.query_engine = get_query_engine()
    print("[Startup] RAG engine ready.")


# ── 请求 / 响应模型 ────────────────────────────────────────────────────────
class QueryRequest(BaseModel):
    session_id: str
    question: str

class QueryResponse(BaseModel):
    session_id: str
    question: str
    answer: str


# ── 路由 ───────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    """服务健康检查"""
    return {"status": "ok"}


@app.post("/session")
def new_session(session_id: str, user_id: str | None = None):
    """新建会话，写入 Supabase"""
    create_session(session_id=session_id, user_id=user_id)
    return {"session_id": session_id, "created": True}


@app.post("/query", response_model=QueryResponse)
def query(req: QueryRequest):
    """
    主查询接口：
    1. 拉取历史对话注入上下文
    2. 通过 RAG query_engine 检索 + LLM 回答
    3. 问答记录写入 Supabase
    """
    engine = app.state.query_engine
    if engine is None:
        raise HTTPException(status_code=503, detail="RAG engine not ready.")

    # 拼入历史对话（最近 10 条）
    history = get_history(req.session_id, limit=10)
    context_prefix = ""
    if history:
        lines = [f"{m['role'].upper()}: {m['content']}" for m in history]
        context_prefix = "【对话历史】\n" + "\n".join(lines) + "\n\n【当前问题】\n"

    full_question = context_prefix + req.question
    response = engine.query(full_question)
    answer = str(response)

    # 写入 Supabase
    save_message(req.session_id, "user", req.question)
    save_message(req.session_id, "assistant", answer)

    return QueryResponse(
        session_id=req.session_id,
        question=req.question,
        answer=answer,
    )


@app.get("/history/{session_id}")
def history(session_id: str, limit: int = 20):
    """拉取某会话的聊天记录"""
    return {"session_id": session_id, "messages": get_history(session_id, limit=limit)}


# ── 调度器路由 ─────────────────────────────────────────────────────────────

@app.post("/scheduler/scan")
def trigger_scan(background_tasks: BackgroundTasks):
    """
    触发 ESG 事件扫描流程。
    支持同步和异步执行。

    Returns:
        扫描任务 ID 和初始状态
    """
    orchestrator = get_orchestrator()

    # 在后台执行流程，不阻塞 HTTP 响应
    background_tasks.add_task(orchestrator.run_full_pipeline)

    return {
        "status": "scanning",
        "message": "ESG scan pipeline started in background",
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/scheduler/scan/status")
def get_scan_status():
    """获取最近一次扫描的状态"""
    orchestrator = get_orchestrator()
    status = orchestrator.get_scan_status()

    if status:
        return {"status": "completed", "data": status}
    return {"status": "no_scan_found"}


@app.get("/scheduler/statistics")
def get_scheduler_statistics(days: int = 7):
    """获取调度器统计信息"""
    orchestrator = get_orchestrator()
    stats = orchestrator.get_pipeline_statistics(days=days)

    return {
        "period_days": days,
        "statistics": stats,
    }


@app.post("/agent/analyze")
def analyze_esg(question: str, session_id: str = ""):
    """
    通过 Agent 工作流分析 ESG 问题。

    这是被动查询流程（用户主动提问）。
    """
    try:
        result = run_agent(question, session_id=session_id)

        # 保存到聊天历史
        if session_id:
            save_message(session_id, "user", question)
            save_message(session_id, "assistant", result.get("final_answer", ""))

        return {
            "question": question,
            "answer": result.get("final_answer"),
            "esg_scores": result.get("esg_scores", {}),
            "confidence": result.get("confidence", 0),
            "analysis_summary": result.get("analysis_summary", ""),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {e}")


# ── 本地直接运行 ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    from datetime import datetime
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
