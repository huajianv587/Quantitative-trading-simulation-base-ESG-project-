import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from rag.rag_main import get_query_engine
from db.supabase_client import save_message, get_history, create_session

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


# ── 本地直接运行 ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
