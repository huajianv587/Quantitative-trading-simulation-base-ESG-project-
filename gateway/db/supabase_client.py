import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from dotenv import load_dotenv
from httpx import Client as HttpxClient, Timeout
from supabase import create_client, Client
from supabase.lib.client_options import SyncClientOptions

# 从项目根目录（当前文件向上两级）加载 .env 文件
# Path(__file__) 是当前文件的绝对路径，.parents[2] 回溯两层到项目根
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

# 模块级单例变量，初始为 None，首次调用 get_client() 时才真正创建连接
_client: Client | None = None
_httpx_client: HttpxClient | None = None


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
    global _client
    if _client is None:                              # 尚未初始化，执行一次性建连
        url = _read_env("SUPABASE_URL")              # 从环境变量读取 Supabase 项目 URL
        # 支持多种API Key命名方式（优先级：SUPABASE_API_KEY > SUPABASE_SERVICE_ROLE_KEY > SUPABASE_KEY）
        key = (_read_env("SUPABASE_API_KEY") or
               _read_env("SUPABASE_SERVICE_ROLE_KEY") or
               _read_env("SUPABASE_KEY"))            # 读取 anon/service_role API Key
        if not url or not key:
            raise RuntimeError("SUPABASE_URL and one of [SUPABASE_API_KEY, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_KEY] must be set in .env")
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
    print(f"Session {session_id} deleted.")


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
