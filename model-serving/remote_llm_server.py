from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import torch
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from gateway.utils.logger import get_logger


logger = get_logger(__name__)

DEFAULT_BASE_MODEL = os.getenv("REMOTE_LLM_BASE_MODEL", "Qwen/Qwen2.5-7B-Instruct")
DEFAULT_ADAPTER_PATH = Path(
    os.getenv("REMOTE_LLM_ADAPTER_PATH", str(PROJECT_ROOT / "model-serving" / "checkpoint"))
)
DEFAULT_HOST = os.getenv("REMOTE_LLM_HOST", "127.0.0.1")
DEFAULT_PORT = int(os.getenv("REMOTE_LLM_PORT", "8010"))
REMOTE_LLM_API_KEY = os.getenv("REMOTE_LLM_API_KEY", "")
ALLOW_CPU = os.getenv("REMOTE_LLM_ALLOW_CPU", "").lower() in {"1", "true", "yes", "on"}

if not torch.cuda.is_available() and not ALLOW_CPU:
    raise RuntimeError(
        "CUDA is required for remote_llm_server.py. "
        "Set REMOTE_LLM_ALLOW_CPU=true only for debugging."
    )

_model = None
_tokenizer = None


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
    device: str


app = FastAPI(title="ESG Remote LLM Service")


def _load_model():
    global _model, _tokenizer
    if _model is not None and _tokenizer is not None:
        return _model, _tokenizer

    if not DEFAULT_ADAPTER_PATH.exists():
        raise FileNotFoundError(f"Adapter checkpoint not found: {DEFAULT_ADAPTER_PATH}")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    torch_dtype = torch.float16 if device == "cuda" else torch.float32

    logger.info(
        "[Remote LLM] Loading base model %s with adapter %s on %s",
        DEFAULT_BASE_MODEL,
        DEFAULT_ADAPTER_PATH,
        device,
    )

    tokenizer = AutoTokenizer.from_pretrained(DEFAULT_BASE_MODEL, trust_remote_code=True)
    tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        DEFAULT_BASE_MODEL,
        torch_dtype=torch_dtype,
        device_map="auto" if device == "cuda" else None,
        trust_remote_code=True,
    )
    if device != "cuda":
        model = model.to(device)

    model = PeftModel.from_pretrained(model, str(DEFAULT_ADAPTER_PATH))
    model.eval()

    _model, _tokenizer = model, tokenizer
    logger.info("[Remote LLM] Model ready.")
    return _model, _tokenizer


def _require_auth(authorization: str | None) -> None:
    if not REMOTE_LLM_API_KEY:
        return
    if authorization != f"Bearer {REMOTE_LLM_API_KEY}":
        raise HTTPException(status_code=401, detail="Unauthorized")


def _generate(messages: list[dict[str, Any]], max_tokens: int, temperature: float) -> str:
    model, tokenizer = _load_model()
    prompt = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)

    generation_kwargs: dict[str, Any] = {
        "max_new_tokens": max_tokens,
        "pad_token_id": tokenizer.eos_token_id,
    }
    if temperature > 0:
        generation_kwargs["do_sample"] = True
        generation_kwargs["temperature"] = temperature
    else:
        generation_kwargs["do_sample"] = False

    with torch.no_grad():
        output_ids = model.generate(**inputs, **generation_kwargs)

    new_ids = output_ids[0][inputs["input_ids"].shape[1]:]
    return tokenizer.decode(new_ids, skip_special_tokens=True).strip()


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "cuda": torch.cuda.is_available(),
        "base_model": DEFAULT_BASE_MODEL,
        "adapter_path": str(DEFAULT_ADAPTER_PATH),
        "model_loaded": _model is not None,
    }


@app.post("/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    authorization: str | None = Header(default=None),
) -> ChatResponse:
    _require_auth(authorization)
    answer = _generate(
        [message.model_dump() for message in request.messages],
        max_tokens=request.max_tokens,
        temperature=request.temperature,
    )
    return ChatResponse(
        answer=answer,
        model_name=DEFAULT_BASE_MODEL,
        device="cuda" if torch.cuda.is_available() else "cpu",
    )


if __name__ == "__main__":
    uvicorn.run(app, host=DEFAULT_HOST, port=DEFAULT_PORT)
