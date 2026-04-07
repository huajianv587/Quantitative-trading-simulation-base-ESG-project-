from __future__ import annotations

import requests
import torch
from openai import OpenAI
from pathlib import Path
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel

from gateway.config import settings
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
_local_fail_count = 0    # 本地模型连续失败计数器（熔断器）
_remote_fail_count = 0   # 远端 GPU 服务连续失败计数器（熔断器）

def _disable_local_backend(reason: str) -> None:
    """熔断本地模型后端，避免后续请求重复卡在不可用路径。"""
    global _local_fail_count
    if _local_fail_count < MAX_LOCAL_FAILURES:
        logger.warning(f"[LLM] {reason}")
    _local_fail_count = MAX_LOCAL_FAILURES


def _disable_remote_backend(reason: str) -> None:
    """熔断远端模型服务，避免每次请求都卡在不可用的网络路径。"""
    global _remote_fail_count
    if _remote_fail_count < MAX_REMOTE_FAILURES:
        logger.warning(f"[LLM] {reason}")
    _remote_fail_count = MAX_REMOTE_FAILURES


def _local_backend_supported() -> bool:
    """检查当前环境是否适合加载本地 7B LoRA 模型。"""
    ckpt = Path(LOCAL_CKPT)
    if not ckpt.exists():
        _disable_local_backend(f"Local checkpoint not found: {LOCAL_CKPT}")
        return False

    if not torch.cuda.is_available():
        _disable_local_backend(
            "CUDA unavailable; skipping local Qwen2.5-7B backend on CPU. "
            "Configure OPENAI_API_KEY or DEEPSEEK_API_KEY for CPU deployments, or deploy with GPU."
        )
        return False

    return True


# 启动时检测本地模型是否可用，不适合时直接跳过
_local_backend_supported()


def _backend_mode() -> str:
    mode = str(getattr(settings, "LLM_BACKEND_MODE", "auto") or "auto").strip().lower()
    return mode if mode in {"auto", "local", "remote", "cloud"} else "auto"


def get_runtime_backend_status() -> dict:
    return {
        "app_mode": getattr(settings, "APP_MODE", "local"),
        "llm_backend_mode": _backend_mode(),
        "remote_llm_configured": _remote_backend_configured(),
        "remote_llm_enabled_in_mode": _backend_mode() == "remote",
        "cloud_fallback_order": list(CLOUD_FALLBACK_ORDER),
        "local_llm_cuda_available": torch.cuda.is_available(),
        "local_checkpoint_exists": Path(LOCAL_CKPT).exists(),
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
        timeout=settings.REMOTE_LLM_TIMEOUT,
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
        if not settings.OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY not set in .env")
        _openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
    return _openai_client


def _get_deepseek_client() -> OpenAI:
    """获取 DeepSeek 客户端（单例，使用 OpenAI SDK 兼容接口）。"""
    global _deepseek_client
    if _deepseek_client is None:
        if not settings.DEEPSEEK_API_KEY:
            raise RuntimeError("DEEPSEEK_API_KEY not set in .env")
        _deepseek_client = OpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url="https://api.deepseek.com",
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

    # ── 1. 本地 LoRA 模型 ────────────────────────────────────────────────
    if allow_local and _local_fail_count < MAX_LOCAL_FAILURES:
        try:
            result = _chat_local(messages, max_new_tokens=max_tokens)
            _local_fail_count = 0   # 成功则重置计数
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
        if _remote_fail_count < MAX_REMOTE_FAILURES:
            try:
                result = _chat_remote(messages, max_tokens=max_tokens, temperature=temperature)
                _remote_fail_count = 0
                logger.info("[LLM] Response from remote GPU LLM service.")
                return result
            except Exception as e:
                _remote_fail_count += 1
                logger.warning(
                    f"[LLM] Remote LLM failed ({_remote_fail_count}/{MAX_REMOTE_FAILURES}): {e}"
                )
                if _remote_fail_count >= MAX_REMOTE_FAILURES:
                    logger.error("[LLM] Remote LLM disabled after repeated failures, switching to cloud API.")
        else:
            logger.debug("[LLM] Remote LLM skipped (too many failures), using cloud API.")

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
            return result
        except Exception as e:
            last_error = e
            logger.warning(f"[LLM] {backend_name} failed: {e}")

    if not any_cloud_backend_configured:
        raise RuntimeError(
            "No cloud LLM backend configured. "
            "Set DEEPSEEK_API_KEY or OPENAI_API_KEY for fallback access."
        )

    logger.error(f"[LLM] All LLM backends failed. Last error: {last_error}")
    raise RuntimeError("All LLM backends failed.") from last_error
