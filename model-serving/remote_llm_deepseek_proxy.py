from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Response
from openai import OpenAI
from pydantic import BaseModel, Field


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

DEFAULT_HOST = os.getenv("REMOTE_LLM_HOST", "127.0.0.1")
DEFAULT_PORT = int(os.getenv("REMOTE_LLM_PORT", "8010"))
REMOTE_LLM_API_KEY = os.getenv("REMOTE_LLM_API_KEY", "")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

app = FastAPI(title="ESG Remote LLM DeepSeek Proxy")


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    max_tokens: int = Field(default=1024, ge=1, le=4096)
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)


class ChatResponse(BaseModel):
    answer: str
    model_name: str
    provider: str


def _require_auth(authorization: str | None) -> None:
    if not REMOTE_LLM_API_KEY:
        return
    if authorization != f"Bearer {REMOTE_LLM_API_KEY}":
        raise HTTPException(status_code=401, detail="Unauthorized")


def _client() -> OpenAI:
    if not DEEPSEEK_API_KEY:
        raise HTTPException(status_code=503, detail="DEEPSEEK_API_KEY is not configured")
    return OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)


@app.get("/health")
def health(response: Response) -> dict[str, Any]:
    ready = bool(DEEPSEEK_API_KEY)
    if not ready:
        response.status_code = 503
    return {
        "status": "ok" if ready else "missing_deepseek_api_key",
        "provider": "deepseek",
        "model": DEEPSEEK_MODEL,
        "base_url": DEEPSEEK_BASE_URL,
        "api_key_configured": ready,
    }


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest, authorization: str | None = Header(default=None)) -> ChatResponse:
    _require_auth(authorization)
    response = _client().chat.completions.create(
        model=DEEPSEEK_MODEL,
        messages=[message.dict() for message in request.messages],
        temperature=request.temperature,
        max_tokens=request.max_tokens,
    )
    answer = (response.choices[0].message.content or "").strip()
    if not answer:
        raise HTTPException(status_code=502, detail="DeepSeek returned an empty answer")
    return ChatResponse(answer=answer, model_name=DEEPSEEK_MODEL, provider="deepseek")


if __name__ == "__main__":
    uvicorn.run(app, host=DEFAULT_HOST, port=DEFAULT_PORT)
