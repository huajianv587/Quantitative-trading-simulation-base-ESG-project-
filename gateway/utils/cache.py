import hashlib
import time
from typing import Any
from gateway.utils.logger import get_logger

logger = get_logger(__name__)

TTL_SECONDS = 3600   # 缓存有效期 1 小时

# 进程内内存缓存，结构: { md5_key: {"value": Any, "expires_at": float} }
# 进程重启后缓存清零；无持久化，无跨进程共享
_store: dict[str, dict[str, Any]] = {}


def _make_key(text: str) -> str:
    """标准化问题文本后做 MD5，作为缓存 key。"""
    normalized = text.strip().lower()   # 去首尾空格并转小写，使语义相同的问题映射到同一 key
    return hashlib.md5(normalized.encode("utf-8")).hexdigest()  # MD5 压缩为 32 位十六进制串


def set_cache(
    question: str,
    value: Any,
    ttl_hours: float | None = None,
    ttl_seconds: float | None = None,
) -> None:
    """
    将任意可序列化问答结果写入缓存，TTL 为 1 小时。
    """
    key = _make_key(question)
    expires_in = TTL_SECONDS
    if ttl_seconds is not None:
        expires_in = ttl_seconds
    elif ttl_hours is not None:
        expires_in = ttl_hours * 3600

    _store[key] = {
        "value": value,
        "expires_at": time.time() + expires_in,    # 绝对过期时间点（非滑动窗口）
    }
    logger.debug(f"[Cache] Set: {key}")


def get_cache(question: str) -> Any | None:
    """
    查询缓存，命中且未过期则返回缓存 payload，否则返回 None。
    """
    key = _make_key(question)
    entry = _store.get(key)             # 未命中直接返回 None
    if entry is None:
        return None
    if time.time() > entry["expires_at"]:   # 惰性删除：读取时才检查过期，避免后台轮询开销
        del _store[key]
        logger.debug(f"[Cache] Expired: {key}")
        return None
    logger.debug(f"[Cache] Hit: {key}")
    return entry["value"]


def clear_cache() -> None:
    """清空全部缓存（调试 / 数据更新后调用）。"""
    count = len(_store)
    _store.clear()      # 知识库更新或调试时手动调用，强制刷新全部缓存条目
    logger.info(f"[Cache] Cleared {count} entries.")
