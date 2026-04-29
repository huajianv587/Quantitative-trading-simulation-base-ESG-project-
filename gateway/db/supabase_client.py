import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from dotenv import load_dotenv
from httpx import Client as HttpxClient, Timeout
from supabase import create_client, Client
from supabase.lib.client_options import SyncClientOptions
from gateway.utils.logger import get_logger

logger = get_logger(__name__)

try:
    from postgrest.exceptions import APIError as PostgrestAPIError
except Exception:  # pragma: no cover - import path depends on installed supabase stack
    PostgrestAPIError = Exception

# 从项目根目录（当前文件向上两级）加载 .env 文件
# Path(__file__) 是当前文件的绝对路径，.parents[2] 回溯两层到项目根
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

# 模块级单例变量，初始为 None，首次调用 get_client() 时才真正创建连接
_client: Client | None = None
_httpx_client: HttpxClient | None = None
_in_memory_client = None
_in_memory_warning_emitted = False
_table_fallback_warnings: set[str] = set()


class _InMemoryResult:
    def __init__(self, data):
        self.data = data


class _InMemoryTableQuery:
    def __init__(self, database: "_InMemorySupabaseClient", table_name: str):
        self._database = database
        self._table_name = table_name
        self._selected_fields: list[str] | None = None
        self._action = "select"
        self._payload = None
        self._filters: list[tuple[str, str, object]] = []
        self._order: tuple[str, bool] | None = None
        self._limit: int | None = None

    def select(self, fields: str = "*"):
        if fields and fields != "*":
            self._selected_fields = [item.strip() for item in fields.split(",") if item.strip()]
        return self

    def insert(self, payload):
        self._action = "insert"
        self._payload = payload
        return self

    def update(self, payload):
        self._action = "update"
        self._payload = payload
        return self

    def delete(self):
        self._action = "delete"
        return self

    def eq(self, key, value):
        self._filters.append(("eq", key, value))
        return self

    def gte(self, key, value):
        self._filters.append(("gte", key, value))
        return self

    def lte(self, key, value):
        self._filters.append(("lte", key, value))
        return self

    def in_(self, key, values):
        self._filters.append(("in", key, list(values)))
        return self

    def order(self, key, desc: bool = False):
        self._order = (key, desc)
        return self

    def limit(self, value: int):
        self._limit = value
        return self

    def execute(self):
        return self._database._execute_query(self)


class _InMemorySupabaseClient:
    backend = "in_memory"

    def __init__(self):
        self._tables: dict[str, list[dict]] = {}
        self._lock = threading.Lock()

    def table(self, name: str):
        return _InMemoryTableQuery(self, name)

    def _execute_query(self, query: _InMemoryTableQuery) -> _InMemoryResult:
        with self._lock:
            rows = self._tables.setdefault(query._table_name, [])

            if query._action == "insert":
                payloads = query._payload if isinstance(query._payload, list) else [query._payload]
                inserted = []
                for payload in payloads:
                    row = dict(payload or {})
                    row.setdefault("id", str(uuid.uuid4()))
                    inserted.append(row)
                    rows.append(row)
                return _InMemoryResult([dict(item) for item in inserted])

            matched = [row for row in rows if self._matches(row, query._filters)]

            if query._action == "update":
                updated = []
                for row in matched:
                    row.update(dict(query._payload or {}))
                    updated.append(dict(row))
                return _InMemoryResult(updated)

            if query._action == "delete":
                deleted = [dict(row) for row in matched]
                self._tables[query._table_name] = [row for row in rows if row not in matched]
                return _InMemoryResult(deleted)

            result_rows = [dict(row) for row in matched]
            if query._order is not None:
                key, desc = query._order
                result_rows.sort(key=lambda item: item.get(key) or "", reverse=desc)
            if query._limit is not None:
                result_rows = result_rows[:query._limit]
            if query._selected_fields is not None:
                result_rows = [
                    {field: row.get(field) for field in query._selected_fields}
                    for row in result_rows
                ]
            return _InMemoryResult(result_rows)

    @staticmethod
    def _matches(row: dict, filters: list[tuple[str, str, object]]) -> bool:
        for op, key, value in filters:
            current = row.get(key)
            if op == "eq" and current != value:
                return False
            if op == "gte" and (current is None or current < value):
                return False
            if op == "lte" and (current is None or current > value):
                return False
            if op == "in" and current not in value:
                return False
        return True


def _get_in_memory_client():
    global _in_memory_client
    if _in_memory_client is None:
        _in_memory_client = _InMemorySupabaseClient()
    return _in_memory_client


def _is_missing_table_error(exc: Exception) -> bool:
    if isinstance(exc, PostgrestAPIError):
        code = str(getattr(exc, "code", "") or "").upper()
        message = str(getattr(exc, "message", "") or exc).lower()
    else:
        code = str(getattr(exc, "code", "") or "").upper()
        message = str(exc).lower()
    if code in {"PGRST205", "42P01"}:
        return True
    return (
        "could not find the table" in message
        or "schema cache" in message
        or "relation" in message and "does not exist" in message
    )


def _warn_table_fallback(table_name: str, exc: Exception) -> None:
    if table_name in _table_fallback_warnings:
        return
    _table_fallback_warnings.add(table_name)
    logger.warning(
        "[Supabase] Table '%s' unavailable, degrading to in-memory fallback for lightweight features: %s",
        table_name,
        exc,
    )


def _run_table_insert(client: Any, table_name: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
    response = client.table(table_name).insert(payload).execute()
    return list(response.data or [])


def _run_table_update(
    client: Any,
    table_name: str,
    payload: dict[str, Any],
    *,
    match: dict[str, Any],
) -> list[dict[str, Any]]:
    query = client.table(table_name).update(payload)
    for key, value in match.items():
        query = query.eq(key, value)
    response = query.execute()
    return list(response.data or [])


def _run_table_list(
    client: Any,
    table_name: str,
    *,
    limit: int,
    order_by: str,
    desc: bool,
    filters: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    query = client.table(table_name).select("*")
    for key, value in (filters or {}).items():
        query = query.eq(key, value)
    response = query.order(order_by, desc=desc).limit(limit).execute()
    return list(response.data or [])


def _with_table_fallback(table_name: str, operation):
    try:
        return operation(get_client())
    except Exception as exc:
        if not _is_missing_table_error(exc):
            raise
        _warn_table_fallback(table_name, exc)
        return operation(_get_in_memory_client())


def _build_client_options() -> SyncClientOptions:
    """Provide an explicit shared httpx client to avoid deprecated implicit kwargs."""
    global _httpx_client
    if _httpx_client is None:
        _httpx_client = HttpxClient(
            timeout=Timeout(30.0),
            follow_redirects=True,
        )
    return SyncClientOptions(httpx_client=_httpx_client)


def _read_env(name: str) -> str:
    """Read an env var and normalize common formatting issues."""
    value = os.getenv(name, "")
    if value is None:
        return ""
    value = value.strip().strip("\"'").strip()

    # Some shells / compose setups accidentally inject "NAME=value" as the value.
    prefix = f"{name}="
    if value.upper().startswith(prefix.upper()):
        value = value[len(prefix):].strip().strip("\"'").strip()

    return value


def _mask_value(value: str, visible: int = 8) -> str:
    """Mask sensitive or noisy env values in logs/errors."""
    if not value:
        return "<empty>"
    if len(value) <= visible:
        return value
    return f"{value[:visible]}...({len(value)} chars)"


def _validate_url(name: str, value: str) -> str:
    """Validate a URL env var early so callers get actionable errors."""
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise RuntimeError(f"{name} is invalid: {_mask_value(value)}")
    return value


def get_client() -> Client:
    """单例：复用同一个 Supabase 连接。"""
    global _client, _in_memory_warning_emitted
    if _client is None:                              # 尚未初始化，执行一次性建连
        url = _read_env("SUPABASE_URL")              # 从环境变量读取 Supabase 项目 URL
        # 支持多种API Key命名方式（优先级：SUPABASE_API_KEY > SUPABASE_SERVICE_ROLE_KEY > SUPABASE_KEY）
        key = (_read_env("SUPABASE_API_KEY") or
               _read_env("SUPABASE_SERVICE_ROLE_KEY") or
               _read_env("SUPABASE_KEY"))            # 读取 anon/service_role API Key
        if not url or not key:
            if not _in_memory_warning_emitted:
                logger.warning(
                    "[Supabase] Missing SUPABASE_URL/API key. "
                    "Using in-memory fallback client for local runtime.",
                )
                _in_memory_warning_emitted = True
            _client = _get_in_memory_client()
            return _client
        url = _validate_url("SUPABASE_URL", url)
        try:
            _client = create_client(                # 创建并缓存客户端，后续调用直接复用
                url,
                key,
                options=_build_client_options(),
            )
        except Exception as exc:
            raise RuntimeError(
                "Failed to initialize Supabase client "
                f"(SUPABASE_URL={_mask_value(url)}, key={_mask_value(key)}): {exc}"
            ) from exc
    return _client


# 为了向后兼容，提供 supabase_client 别名（懒加载代理）
class _ClientProxy:
    """懒加载代理，首次访问时才初始化连接"""
    def __getattr__(self, name):
        return getattr(get_client(), name)

supabase_client = _ClientProxy()


# ---------------------------------------------------------------------------
# 聊天记录
# 对应 Supabase 表：chat_history
#   id          uuid primary key default gen_random_uuid()
#   session_id  text not null
#   role        text not null          -- 'user' | 'assistant'
#   content     text not null
#   created_at  timestamptz default now()
# ---------------------------------------------------------------------------

def save_message(session_id: str, role: str, content: str) -> None:
    """将一条对话消息写入 chat_history 表。"""
    get_client().table("chat_history").insert({
        "session_id": session_id,              # 关联到哪个会话
        "role": role,                          # 消息发送方：'user' 或 'assistant'
        "content": content,                    # 消息正文
        "created_at": datetime.now(timezone.utc).isoformat(),  # UTC 时间戳，ISO 8601 格式
    }).execute()                               # .execute() 真正发出 HTTP 请求到 Supabase


def get_history(session_id: str, limit: int = 20) -> list[dict]:
    """
    按时间正序返回某会话最近 N 条消息。
    返回格式：[{"role": "user", "content": "..."}, ...]
    """
    resp = (
        get_client()
        .table("chat_history")
        .select("role, content, created_at")   # 只取需要的三列，节省带宽
        .eq("session_id", session_id)          # WHERE session_id = ?  过滤当前会话
        .order("created_at", desc=False)       # 正序排列，保证消息顺序与对话顺序一致
        .limit(limit)                          # 最多返回 N 条，防止历史过长撑爆 context
        .execute()
    )
    # resp.data 是原始行列表，这里只保留 role/content 供 LLM 使用，丢弃 created_at
    return [{"role": r["role"], "content": r["content"]} for r in resp.data]


def delete_session(session_id: str) -> None:
    """删除会话记录；chat_history 由数据库外键 CASCADE 自动清理。
    前提：Supabase 外键 chat_history_session_id_fkey 的 ON DELETE 必须设为 CASCADE。
    """
    get_client().table("sessions").delete().eq("session_id", session_id).execute()
    # DELETE FROM sessions WHERE session_id = ?
    # → 数据库自动 CASCADE DELETE chat_history 里对应的所有消息
    logger.info("Session %s deleted.", session_id)


# ---------------------------------------------------------------------------
# 会话管理
# 对应 Supabase 表：sessions
#   id          uuid primary key default gen_random_uuid()
#   session_id  text unique not null
#   user_id     text
#   created_at  timestamptz default now()
# ---------------------------------------------------------------------------

def create_session(session_id: str, user_id: str | None = None) -> None:
    payload = {
        "session_id": session_id,              # 前端生成的唯一会话 ID（如 UUID）
        "user_id": user_id,                    # 可选，关联到具体用户；匿名时为 None
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        get_client().table("sessions").insert(payload).execute()
    except Exception as exc:
        # 让创建会话接口具备幂等性，页面刷新或重复初始化时不因为唯一键冲突失败。
        error_text = str(exc).lower()
        if "duplicate" in error_text or "unique" in error_text or "already exists" in error_text:
            return
        raise


def list_sessions(user_id: str) -> list[str]:
    """返回某用户的所有 session_id。"""
    resp = (
        get_client()
        .table("sessions")
        .select("session_id, created_at")
        .eq("user_id", user_id)                # 过滤特定用户
        .order("created_at", desc=True)        # 最新会话排在前面
        .execute()
    )
    return [r["session_id"] for r in resp.data]  # 只返回 session_id 列表
def save_table_row(table_name: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Generic helper for lightweight feature modules."""
    return _with_table_fallback(table_name, lambda client: _run_table_insert(client, table_name, payload))


def update_table_row(
    table_name: str,
    payload: dict[str, Any],
    *,
    match: dict[str, Any],
) -> list[dict[str, Any]]:
    """Generic helper for lightweight feature modules that need targeted updates."""
    return _with_table_fallback(
        table_name,
        lambda client: _run_table_update(client, table_name, payload, match=match),
    )


def list_table_rows(
    table_name: str,
    *,
    limit: int = 20,
    order_by: str = "created_at",
    desc: bool = True,
    filters: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    return _with_table_fallback(
        table_name,
        lambda client: _run_table_list(
            client,
            table_name,
            limit=limit,
            order_by=order_by,
            desc=desc,
            filters=filters,
        ),
    )


def latest_table_row(
    table_name: str,
    *,
    order_by: str = "created_at",
    filters: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    rows = list_table_rows(
        table_name,
        limit=1,
        order_by=order_by,
        desc=True,
        filters=filters,
    )
    return rows[0] if rows else None
