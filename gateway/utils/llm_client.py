from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

import requests

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - optional runtime dependency
    OpenAI = None

from gateway.config import settings
from gateway.utils.cache import get_cache, set_cache
from gateway.utils.logger import get_logger

logger = get_logger(__name__)

# 项目根目录和模型路径配置
PROJECT_ROOT  = Path(__file__).resolve().parents[2]
LOCAL_CKPT    = str(PROJECT_ROOT / "model-serving" / "checkpoint")
LOCAL_BASE    = "Qwen/Qwen2.5-7B-Instruct"
MAX_LOCAL_FAILURES = 3   # 连续失败超过这个数就切到云端
MAX_REMOTE_FAILURES = 3
CLOUD_FALLBACK_ORDER = ("deepseek", "openai")

# ── 单例变量 ──────────────────────────────────────────────────────────────────
_local_model     = None  # 本地模型实例（避免重复加载）
_local_tokenizer = None  # 本地分词器实例
_openai_client   = None  # OpenAI 客户端实例
_deepseek_client = None  # DeepSeek 客户端实例
_local_dependency_error = ""
_local_fail_count = 0    # 本地模型连续失败计数器（熔断器）
_remote_fail_count = 0   # 远端 GPU 服务连续失败计数器（熔断器）
_remote_retry_after = 0.0
_remote_health_cache = {
    "checked_at": 0.0,
    "reachable": None,
    "detail": "",
}

def _disable_local_backend(reason: str) -> None:
    """熔断本地模型后端，避免后续请求重复卡在不可用路径。"""
    global _local_fail_count
    if _local_fail_count < MAX_LOCAL_FAILURES:
        logger.warning(f"[LLM] {reason}")
    _local_fail_count = MAX_LOCAL_FAILURES


def _disable_remote_backend(reason: str) -> None:
    """熔断远端模型服务，避免每次请求都卡在不可用的网络路径。"""
    global _remote_fail_count, _remote_retry_after
    if _remote_fail_count < MAX_REMOTE_FAILURES:
        logger.warning(f"[LLM] {reason}")
    _remote_fail_count = MAX_REMOTE_FAILURES
    cooldown_seconds = max(int(getattr(settings, "REMOTE_LLM_COOLDOWN_SECONDS", 60) or 60), 5)
    _remote_retry_after = time.time() + cooldown_seconds


def _remote_backend_retry_ready() -> bool:
    global _remote_fail_count
    if _remote_fail_count < MAX_REMOTE_FAILURES:
        return True
    if time.time() >= _remote_retry_after:
        _remote_fail_count = max(0, MAX_REMOTE_FAILURES - 1)
        return True
    return False


def _remote_backend_healthy(force: bool = False) -> bool:
    global _remote_health_cache
    if not _remote_backend_configured():
        return False

    ttl_seconds = max(int(getattr(settings, "REMOTE_LLM_HEALTH_TTL_SECONDS", 30) or 30), 1)
    now = time.time()
    checked_at = float(_remote_health_cache.get("checked_at") or 0.0)
    if (
        not force
        and checked_at
        and now - checked_at < ttl_seconds
        and _remote_health_cache.get("reachable") is not None
    ):
        return bool(_remote_health_cache.get("reachable"))

    health_url = f"{settings.REMOTE_LLM_URL.rstrip('/')}/health"
    timeout_seconds = max(float(getattr(settings, "REMOTE_LLM_HEALTH_TIMEOUT", 2.0) or 2.0), 0.5)
    reachable = False
    detail = ""
    try:
        response = requests.get(health_url, timeout=timeout_seconds)
        reachable = response.ok
        detail = f"status={response.status_code}"
    except Exception as exc:
        detail = str(exc)

    _remote_health_cache = {
        "checked_at": now,
        "reachable": reachable,
        "detail": detail[:240],
    }
    return reachable


def _chat_cache_key(messages: list[dict], temperature: float, max_tokens: int, backend_mode: str) -> str:
    payload = json.dumps(
        {
            "backend_mode": backend_mode,
            "temperature": round(float(temperature), 4),
            "max_tokens": int(max_tokens),
            "messages": messages,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return f"llm_chat::{payload}"


def _load_torch_dependency() -> object | None:
    global _local_dependency_error
    try:
        import torch

        _local_dependency_error = ""
        return torch
    except Exception as exc:  # pragma: no cover - optional runtime dependency
        _local_dependency_error = str(exc)
        return None


def _load_local_dependencies() -> tuple[object | None, object | None, object | None, object | None]:
    global _local_dependency_error
    torch = _load_torch_dependency()
    if torch is None:
        return None, None, None, None
    try:
        from peft import PeftModel
        from transformers import AutoModelForCausalLM, AutoTokenizer

        _local_dependency_error = ""
        return torch, AutoModelForCausalLM, AutoTokenizer, PeftModel
    except Exception as exc:  # pragma: no cover - optional runtime dependency
        _local_dependency_error = str(exc)
        return None, None, None, None


def __getattr__(name: str) -> object:
    if name == "torch":
        torch = _load_torch_dependency()
        if torch is None:
            raise AttributeError(f"torch dependency is unavailable: {_local_dependency_error}")
        return torch
    raise AttributeError(name)


def _local_cuda_available_without_import() -> bool:
    loaded_torch = sys.modules.get("torch")
    if loaded_torch is None:
        return False
    cuda = getattr(loaded_torch, "cuda", None)
    return bool(cuda and cuda.is_available())


def _local_backend_supported() -> bool:
    """检查当前环境是否适合加载本地 7B LoRA 模型。"""
    ckpt = Path(LOCAL_CKPT)
    if not ckpt.exists():
        _disable_local_backend(f"Local checkpoint not found: {LOCAL_CKPT}")
        return False

    torch = _load_torch_dependency()
    if torch is None:
        detail = f" {_local_dependency_error}" if _local_dependency_error else ""
        _disable_local_backend(f"PyTorch unavailable; local backend disabled.{detail}")
        return False

    if not torch.cuda.is_available():
        _disable_local_backend(
            "CUDA unavailable; skipping local Qwen2.5-7B backend on CPU. "
            "Configure OPENAI_API_KEY or DEEPSEEK_API_KEY for CPU deployments, or deploy with GPU."
        )
        return False

    _, AutoModelForCausalLM, AutoTokenizer, PeftModel = _load_local_dependencies()
    if AutoTokenizer is None or AutoModelForCausalLM is None or PeftModel is None:
        detail = f" {_local_dependency_error}" if _local_dependency_error else ""
        _disable_local_backend(f"Transformers/PEFT unavailable; local backend disabled.{detail}")
        return False

    return True


def _backend_mode() -> str:
    mode = str(getattr(settings, "LLM_BACKEND_MODE", "auto") or "auto").strip().lower()
    return mode if mode in {"auto", "local", "remote", "cloud"} else "auto"


def _degraded_fallback_enabled() -> bool:
    return bool(getattr(settings, "DEBUG", False) or getattr(settings, "APP_MODE", "local") in {"local", "hybrid"})


def get_runtime_backend_status() -> dict:
    return {
        "app_mode": getattr(settings, "APP_MODE", "local"),
        "llm_backend_mode": _backend_mode(),
        "remote_llm_configured": _remote_backend_configured(),
        "remote_llm_enabled_in_mode": _backend_mode() == "remote",
        "cloud_fallback_order": list(CLOUD_FALLBACK_ORDER),
        "degraded_llm_fallback_enabled": _degraded_fallback_enabled(),
        "local_llm_cuda_available": _local_cuda_available_without_import(),
        "local_checkpoint_exists": Path(LOCAL_CKPT).exists(),
        "local_dependency_error": _local_dependency_error,
        "openai_sdk_available": OpenAI is not None,
    }


def _remote_backend_configured() -> bool:
    return bool(settings.REMOTE_LLM_URL)


# ── 本地模型 ──────────────────────────────────────────────────────────────

def _load_local_model():
    """
    加载本地 LoRA 微调模型（单例模式）。
    
    流程：
    1. 检查是否已加载（单例）
    2. 加载基座模型 Qwen2.5-7B
    3. 加载 LoRA 适配器
    4. 设置为评估模式
    """
    global _local_model, _local_tokenizer
    if _local_model is not None:
        return _local_model, _local_tokenizer

    if not _local_backend_supported():
        raise RuntimeError(
            "Local Qwen2.5-7B backend is unavailable in this environment."
        )

    ckpt = Path(LOCAL_CKPT)
    logger.info(f"[LLM] Loading local model from {LOCAL_CKPT} ...")
    torch, AutoModelForCausalLM, AutoTokenizer, PeftModel = _load_local_dependencies()
    if torch is None or AutoTokenizer is None or AutoModelForCausalLM is None or PeftModel is None:
        raise RuntimeError("Local LLM dependencies are unavailable.")

    # 加载分词器
    tokenizer = AutoTokenizer.from_pretrained(LOCAL_BASE, trust_remote_code=True)
    tokenizer.pad_token = tokenizer.eos_token

    # 加载基座模型（GPU 环境下使用 float16，并自动分配设备）
    model = AutoModelForCausalLM.from_pretrained(
        LOCAL_BASE,
        torch_dtype=torch.float16,
        device_map="auto",
        trust_remote_code=True,
    )
    # 加载 LoRA 适配器
    model = PeftModel.from_pretrained(model, LOCAL_CKPT)
    model.eval()  # 设置为评估模式

    _local_model, _local_tokenizer = model, tokenizer
    logger.info("[LLM] Local model ready.")
    return model, tokenizer


def _chat_local(messages: list[dict], max_new_tokens: int = 1024) -> str:
    """
    使用本地模型进行推理。
    
    Args:
        messages: 对话消息列表，格式 [{"role": "user", "content": "..."}]
        max_new_tokens: 最大生成 token 数
    
    流程：
    1. 使用 chat_template 格式化 messages → prompt 字符串
    2. tokenize 编码 → input_ids + attention_mask
    3. 模型推理生成
    4. 解码新生成的 token（排除输入部分）
    """
    model, tokenizer = _load_local_model()
    # 将 messages 格式化为 prompt 字符串
    prompt = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )
    # tokenize 编码为 input_ids 和 attention_mask
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    torch = sys.modules.get("torch")
    if torch is None:
        raise RuntimeError("Local LLM torch runtime is unavailable.")
    with torch.no_grad():
        output_ids = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,  # 贪婪解码（确定性输出）
            pad_token_id=tokenizer.eos_token_id,
        )
    # 只解码新生成的部分（排除输入 prompt）
    new_ids = output_ids[0][inputs["input_ids"].shape[1]:]
    return tokenizer.decode(new_ids, skip_special_tokens=True).strip()


def _chat_remote(messages: list[dict], max_tokens: int = 1024, temperature: float = 0.2) -> str:
    """调用远端 GPU LoRA 服务（通常通过 SSH 隧道映射到本地端口）。"""
    if not _remote_backend_configured():
        raise RuntimeError("REMOTE_LLM_URL not set in .env")

    base_url = settings.REMOTE_LLM_URL.rstrip("/")
    headers = {"Content-Type": "application/json"}
    if settings.REMOTE_LLM_API_KEY:
        headers["Authorization"] = f"Bearer {settings.REMOTE_LLM_API_KEY}"

    response = requests.post(
        f"{base_url}/chat",
        json={
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        },
        headers=headers,
        timeout=(
            max(float(getattr(settings, "REMOTE_LLM_CONNECT_TIMEOUT", 2.0) or 2.0), 0.5),
            max(float(getattr(settings, "REMOTE_LLM_TIMEOUT", 180) or 180), 1.0),
        ),
    )
    response.raise_for_status()

    payload = response.json()
    answer = str(payload.get("answer", "")).strip()
    if not answer:
        raise RuntimeError("Remote LLM service returned an empty answer.")
    return answer


# ── 云端客户端 ────────────────────────────────────────────────────────────

def _get_openai_client() -> OpenAI:
    """获取 OpenAI 客户端（单例）。"""
    global _openai_client
    if _openai_client is None:
        if OpenAI is None:
            raise RuntimeError("openai package is not installed")
        if not settings.OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY not set in .env")
        _openai_client = OpenAI(
            api_key=settings.OPENAI_API_KEY,
            timeout=max(float(getattr(settings, "CLOUD_LLM_TIMEOUT_SECONDS", 20.0) or 20.0), 1.0),
            max_retries=max(int(getattr(settings, "CLOUD_LLM_MAX_RETRIES", 1) or 1), 0),
        )
    return _openai_client


def _get_deepseek_client() -> OpenAI:
    """获取 DeepSeek 客户端（单例，使用 OpenAI SDK 兼容接口）。"""
    global _deepseek_client
    if _deepseek_client is None:
        if OpenAI is None:
            raise RuntimeError("openai package is not installed")
        if not settings.DEEPSEEK_API_KEY:
            raise RuntimeError("DEEPSEEK_API_KEY not set in .env")
        _deepseek_client = OpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url="https://api.deepseek.com",
            timeout=max(float(getattr(settings, "CLOUD_LLM_TIMEOUT_SECONDS", 20.0) or 20.0), 1.0),
            max_retries=max(int(getattr(settings, "CLOUD_LLM_MAX_RETRIES", 1) or 1), 0),
        )
    return _deepseek_client


def _chat_openai(messages: list[dict], max_tokens: int = 1024, temperature: float = 0.2) -> str:
    """
    调用 OpenAI GPT-4o API（最终兜底）。
    
    Args:
        messages: 对话消息列表
        max_tokens: 最大生成 token 数
        temperature: 温度参数（0.0=确定性，1.0+=高随机性）
    """
    client = _get_openai_client()
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content.strip()


def _chat_deepseek(messages: list[dict], max_tokens: int = 1024, temperature: float = 0.2) -> str:
    """
    调用 DeepSeek API（首选云端后端）。
    
    Args:
        messages: 对话消息列表
        max_tokens: 最大生成 token 数
        temperature: 温度参数
    """
    client = _get_deepseek_client()
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content.strip()


def _cloud_backend_candidates():
    return (
        ("DeepSeek", bool(settings.DEEPSEEK_API_KEY), _chat_deepseek),
        ("OpenAI GPT-4o", bool(settings.OPENAI_API_KEY), _chat_openai),
    )


def _last_user_message(messages: list[dict]) -> str:
    for message in reversed(messages):
        if str(message.get("role", "")).lower() == "user":
            return str(message.get("content", "")).strip()
    return str(messages[-1].get("content", "")).strip() if messages else ""


def _system_prompt(messages: list[dict]) -> str:
    for message in messages:
        if str(message.get("role", "")).lower() == "system":
            return str(message.get("content", "")).strip()
    return ""


def _truncate_text(text: str, max_chars: int = 360) -> str:
    clean = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(clean) <= max_chars:
        return clean
    shortened = clean[:max_chars].rsplit(" ", 1)[0].strip()
    return shortened or clean[:max_chars].strip()


def _extract_field(content: str, label: str) -> str:
    match = re.search(rf"{re.escape(label)}\s*:\s*(.+?)(?:\n[A-Z][^:\n]{{0,40}}:|\Z)", content, re.DOTALL)
    if not match:
        return ""
    return match.group(1).strip()


def _extract_company_name(text: str) -> str:
    candidate = re.search(r"\b(Tesla|Microsoft|Apple|DBS|Singtel|Grab|NVIDIA|Amazon|Google|Alphabet)\b", text, re.IGNORECASE)
    if candidate:
        return candidate.group(1)

    generic = re.search(r"\b([A-Z][A-Za-z&.-]{1,30})\b", text)
    if generic:
        return generic.group(1)
    return "Target Company"


def _heuristic_router_label(question: str) -> str:
    question_lower = question.lower()
    analysis_markers = (
        "score",
        "评分",
        "analy",
        "compare",
        "对比",
        "风险",
        "performance",
        "表现",
        "评级",
    )
    factual_markers = ("what", "when", "which", "最新", "news", "事件", "recent", "list")
    if any(marker in question_lower for marker in analysis_markers):
        return "esg_analysis"
    if any(marker in question_lower for marker in factual_markers):
        return "factual"
    return "general"


def _score_from_text(text: str, positive_terms: tuple[str, ...], negative_terms: tuple[str, ...], baseline: int) -> int:
    lower = text.lower()
    score = baseline
    score += sum(4 for term in positive_terms if term in lower)
    score -= sum(5 for term in negative_terms if term in lower)
    return max(25, min(92, score))


def _build_analyst_payload(question: str, context: str) -> dict:
    evidence = _truncate_text(context or "No retrieved context available.", 220)
    env_score = _score_from_text(
        context,
        ("emission", "renewable", "climate", "carbon", "energy", "water"),
        ("pollution", "lawsuit", "spill", "violation"),
        72,
    )
    social_score = _score_from_text(
        context,
        ("safety", "employee", "diversity", "community", "training"),
        ("injury", "strike", "breach", "labor"),
        69,
    )
    governance_score = _score_from_text(
        context,
        ("board", "oversight", "audit", "compliance", "governance", "transparency"),
        ("fraud", "corruption", "restatement", "investigation"),
        71,
    )
    overall = round(env_score * 0.35 + social_score * 0.35 + governance_score * 0.30, 1)
    risk_level = "low" if overall >= 75 else "medium" if overall >= 55 else "high"
    company = _extract_company_name(question or context)

    def indicator_block(value: str, score: int, trend: str = "stable") -> dict:
        return {"value": value, "score": score, "trend": trend}

    return {
        "environmental": {
            "score": env_score,
            "indicators": {
                "carbon_emissions": indicator_block("Narrative evidence extracted from context", env_score - 2, "improving"),
                "energy_use": indicator_block("Operational efficiency trend noted", env_score, "improving"),
                "water_use": indicator_block("Limited disclosure in fallback mode", max(40, env_score - 8), "stable"),
                "waste_mgmt": indicator_block("Context-driven proxy signal", max(45, env_score - 5), "stable"),
            },
            "evidence": evidence,
        },
        "social": {
            "score": social_score,
            "indicators": {
                "employee_safety": indicator_block("Workforce and safety references detected", social_score, "stable"),
                "diversity": indicator_block("Diversity and inclusion references detected", max(40, social_score - 2), "stable"),
                "community": indicator_block("Community investment proxy signal", max(40, social_score - 4), "stable"),
                "supply_chain": indicator_block("Supply chain coverage limited in fallback mode", max(38, social_score - 6), "unknown"),
            },
            "evidence": evidence,
        },
        "governance": {
            "score": governance_score,
            "indicators": {
                "board_composition": indicator_block("Board and oversight references detected", governance_score, "stable"),
                "transparency": indicator_block("Disclosure quality proxy signal", max(42, governance_score - 1), "stable"),
                "anti_corruption": indicator_block("No major red flags found in context", max(45, governance_score - 3), "stable"),
                "shareholder": indicator_block("Shareholder rights not fully disclosed in fallback mode", max(40, governance_score - 5), "unknown"),
            },
            "evidence": evidence,
        },
        "overall_score": overall,
        "risk_level": risk_level,
        "summary": (
            f"{company} shows a provisional ESG profile generated in degraded local mode. "
            f"Environmental signals are {'stronger' if env_score >= social_score else 'mixed'}, "
            f"while governance disclosure appears {'stable' if governance_score >= 65 else 'watch-list worthy'}."
        ),
    }


def _build_verifier_payload(answer: str) -> dict:
    return {
        "is_grounded": bool(answer),
        "confidence": 0.66 if answer else 0.45,
        "issues": [] if answer else ["missing_answer"],
        "verified_answer": answer or "No grounded answer available in degraded mode.",
        "needs_retry": False,
    }


def _build_extractor_payload(raw_content: str) -> dict:
    company = _extract_company_name(raw_content)
    lower = raw_content.lower()
    if any(term in lower for term in ("carbon", "climate", "renewable", "emission")):
        event_type = "emission_reduction"
        impact_area = "E"
    elif any(term in lower for term in ("safety", "employee", "diversity", "community")):
        event_type = "diversity_initiative"
        impact_area = "S"
    elif any(term in lower for term in ("board", "audit", "governance", "sec", "compliance")):
        event_type = "governance_change"
        impact_area = "G"
    else:
        event_type = "other"
        impact_area = "E"

    severity = "high" if any(term in lower for term in ("lawsuit", "violation", "critical", "fraud")) else "medium"
    return {
        "title": _truncate_text(raw_content, 80) or f"{company} ESG event",
        "description": _truncate_text(raw_content, 220) or f"Structured event extracted for {company}.",
        "company": company,
        "event_type": event_type,
        "key_metrics": {"fallback_mode": "heuristic_extraction"},
        "impact_area": impact_area,
        "severity": severity,
        "evidence": _truncate_text(raw_content, 180),
    }


def _build_risk_payload(prompt: str) -> dict:
    severity_text = _extract_field(prompt, "Current severity").lower()
    event_type = _extract_field(prompt, "Event type")
    base_score = {
        "low": 32,
        "medium": 56,
        "high": 74,
        "critical": 88,
    }.get(severity_text, 56)
    return {
        "risk_level": "critical" if base_score >= 85 else "high" if base_score >= 70 else "medium" if base_score >= 45 else "low",
        "score": base_score,
        "reasoning": f"Fallback local scoring interpreted '{event_type or 'event'}' with severity '{severity_text or 'medium'}'.",
        "affected_dimensions": {
            "environmental": min(100, base_score if "E" in prompt else max(25, base_score - 10)),
            "social": min(100, base_score if "S" in prompt else max(25, base_score - 8)),
            "governance": min(100, base_score if "G" in prompt else max(25, base_score - 6)),
        },
        "recommendation": "Treat this as a provisional local estimate and confirm with a live model once keys or remote LLM are available.",
    }


def _chat_degraded(messages: list[dict], max_tokens: int = 1024, temperature: float = 0.2) -> str:
    system = _system_prompt(messages).lower()
    user = _last_user_message(messages)

    if "query classifier" in system:
        return _heuristic_router_label(user)

    if "esg search expert" in system:
        original = user.split(":", 1)[-1].strip() if ":" in user else user
        return _truncate_text(original, 160)

    if "professional esg analyst" in system:
        question = _extract_field(user, "Company/Topic") or user
        context = _extract_field(user, "Retrieved context")
        return json.dumps(_build_analyst_payload(question, context), ensure_ascii=False)

    if "esg fact-checker" in system:
        answer = _extract_field(user, "Answer to verify")
        return json.dumps(_build_verifier_payload(answer), ensure_ascii=False)

    if "event extraction expert" in system:
        raw_content = _extract_field(user, "Raw content")
        return json.dumps(_build_extractor_payload(raw_content), ensure_ascii=False)

    if "risk assessment expert" in system:
        return json.dumps(_build_risk_payload(user), ensure_ascii=False)

    # Generic fallback: echo a concise synthesis so RAG and summaries keep moving.
    summary = _truncate_text(user, min(max_tokens * 4, 480))
    if not summary:
        summary = "Fallback local response generated without a live LLM backend."
    return (
        "Fallback local response:\n"
        f"{summary}"
    )


# ── 统一入口（带 fallback 链）────────────────────────────────────────────

def chat(
    messages: list[dict],
    temperature: float = 0.2,
    max_tokens: int = 1024,
) -> str:
    """
    统一 LLM 调用接口，带四级 fallback 机制。
    
    默认调用链：本地 LoRA 模型 → DeepSeek → OpenAI GPT-4o
    远端 GPU LoRA 服务仅在 LLM_BACKEND_MODE=remote 时启用。
    
    Args:
        messages: 对话消息列表，格式：
                  [{"role": "system", "content": "你是ESG助手"},
                   {"role": "user", "content": "什么是ESG？"}]
        temperature: 温度参数，控制随机性（0.0-1.0+）
                     0.2 适合分析任务（稳定输出）
        max_tokens: 最大生成 token 数（约 1 token ≈ 0.5 个中文字）
    
    Returns:
        生成的文本回复
    
    熔断机制：
        本地模型连续失败 3 次后自动切换到云端
    
    用法:
        from gateway.utils.llm_client import chat
        reply = chat([{"role": "user", "content": "What is ESG?"}])
    """
    global _local_fail_count, _remote_fail_count
    backend_mode = _backend_mode()
    allow_local = backend_mode in {"auto", "local"}
    allow_remote = backend_mode == "remote"
    allow_cloud = backend_mode in {"auto", "local", "remote", "cloud"}
    cache_key = _chat_cache_key(messages, temperature, max_tokens, backend_mode)
    cached = get_cache(cache_key)
    if cached:
        return str(cached)

    # ── 1. 本地 LoRA 模型 ────────────────────────────────────────────────
    if allow_local and _local_fail_count < MAX_LOCAL_FAILURES:
        try:
            result = _chat_local(messages, max_new_tokens=max_tokens)
            _local_fail_count = 0   # 成功则重置计数
            set_cache(cache_key, result, ttl_seconds=getattr(settings, "LLM_RESPONSE_CACHE_TTL_SECONDS", 900))
            return result
        except Exception as e:
            _local_fail_count += 1
            logger.warning(
                f"[LLM] Local model failed ({_local_fail_count}/{MAX_LOCAL_FAILURES}): {e}"
            )
            if _local_fail_count >= MAX_LOCAL_FAILURES:
                logger.error("[LLM] Local model disabled after repeated failures, switching to cloud.")
    elif allow_local:
        logger.debug("[LLM] Local model skipped (too many failures), using cloud.")

    # ── 2. 远端 GPU LoRA 服务（仅 remote 模式）───────────────────────────
    if allow_remote and _remote_backend_configured():
        if _remote_backend_retry_ready():
            if not _remote_backend_healthy():
                _disable_remote_backend("Remote LLM health probe failed; temporarily using fallback backend.")
            else:
                try:
                    result = _chat_remote(messages, max_tokens=max_tokens, temperature=temperature)
                    _remote_fail_count = 0
                    set_cache(cache_key, result, ttl_seconds=getattr(settings, "LLM_RESPONSE_CACHE_TTL_SECONDS", 900))
                    logger.info("[LLM] Response from remote GPU LLM service.")
                    return result
                except Exception as e:
                    _remote_fail_count += 1
                    logger.warning(
                        f"[LLM] Remote LLM failed ({_remote_fail_count}/{MAX_REMOTE_FAILURES}): {e}"
                    )
                    if _remote_fail_count >= MAX_REMOTE_FAILURES:
                        _disable_remote_backend("Remote LLM disabled after repeated failures, switching to cloud API.")
        else:
            retry_after = max(_remote_retry_after - time.time(), 0.0)
            logger.debug(f"[LLM] Remote LLM circuit open for another {retry_after:.1f}s; using cloud API.")

    if not allow_cloud:
        raise RuntimeError(
            "No enabled LLM backend succeeded. "
            f"LLM_BACKEND_MODE={backend_mode!r} currently disables cloud fallback."
        )

    # ── 3. 云端后端：DeepSeek → OpenAI ────────────────────────────────────
    last_error = None
    any_cloud_backend_configured = False

    for backend_name, is_configured, backend_func in _cloud_backend_candidates():
        if not is_configured:
            logger.debug(f"[LLM] {backend_name} skipped (not configured).")
            continue

        any_cloud_backend_configured = True
        try:
            result = backend_func(messages, max_tokens=max_tokens, temperature=temperature)
            logger.info(f"[LLM] Response from {backend_name}.")
            set_cache(cache_key, result, ttl_seconds=getattr(settings, "LLM_RESPONSE_CACHE_TTL_SECONDS", 900))
            return result
        except Exception as e:
            last_error = e
            logger.warning(f"[LLM] {backend_name} failed: {e}")

    if _degraded_fallback_enabled():
        if not any_cloud_backend_configured:
            logger.warning("[LLM] No live LLM backend configured. Using degraded local fallback.")
        elif last_error is not None:
            logger.warning(f"[LLM] All live LLM backends failed. Using degraded local fallback. Last error: {last_error}")
        result = _chat_degraded(messages, max_tokens=max_tokens, temperature=temperature)
        set_cache(
            cache_key,
            result,
            ttl_seconds=min(int(getattr(settings, "LLM_RESPONSE_CACHE_TTL_SECONDS", 900) or 900), 300),
        )
        return result

    if not any_cloud_backend_configured:
        raise RuntimeError(
            "No cloud LLM backend configured. "
            "Set DEEPSEEK_API_KEY or OPENAI_API_KEY for fallback access."
        )

    logger.error(f"[LLM] All LLM backends failed. Last error: {last_error}")
    raise RuntimeError("All LLM backends failed.") from last_error
