import os
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

_client: Client | None = None


def get_client() -> Client:
    """单例：复用同一个 Supabase 连接。"""
    global _client
    if _client is None:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        if not url or not key:
            raise RuntimeError("SUPABASE_URL / SUPABASE_KEY not set in .env")
        _client = create_client(url, key)
    return _client


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
        "session_id": session_id,
        "role": role,
        "content": content,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }).execute()


def get_history(session_id: str, limit: int = 20) -> list[dict]:
    """
    按时间正序返回某会话最近 N 条消息。
    返回格式：[{"role": "user", "content": "..."}, ...]
    """
    resp = (
        get_client()
        .table("chat_history")
        .select("role, content, created_at")
        .eq("session_id", session_id)
        .order("created_at", desc=False)
        .limit(limit)
        .execute()
    )
    return [{"role": r["role"], "content": r["content"]} for r in resp.data]


def delete_session(session_id: str) -> None:
    """删除某会话的全部聊天记录。"""
    get_client().table("chat_history").delete().eq("session_id", session_id).execute()
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
    get_client().table("sessions").insert({
        "session_id": session_id,
        "user_id": user_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }).execute()


def list_sessions(user_id: str) -> list[str]:
    """返回某用户的所有 session_id。"""
    resp = (
        get_client()
        .table("sessions")
        .select("session_id, created_at")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return [r["session_id"] for r in resp.data]
