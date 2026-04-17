from __future__ import annotations

import secrets
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gateway.db.supabase_client import get_client
from gateway.utils.logger import get_logger

logger = get_logger(__name__)


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class AuthRepository:
    def __init__(self, db_path: str | Path | None = None) -> None:
        base = Path(__file__).resolve().parents[2]
        target = Path(db_path) if db_path else base / "storage" / "auth" / "auth.sqlite3"
        if not target.is_absolute():
            target = base / target
        target.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = target
        self._lock = threading.RLock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_db(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                create table if not exists users (
                    id text primary key,
                    email text not null unique,
                    name text not null,
                    password_hash text not null,
                    role text not null default 'user',
                    created_at text not null,
                    updated_at text
                );

                create table if not exists password_reset_tokens (
                    token text primary key,
                    email text not null,
                    expires_at integer not null,
                    used integer not null default 0,
                    created_at text not null,
                    used_at text
                );

                create table if not exists auth_audit (
                    audit_id text primary key,
                    event_type text not null,
                    email text,
                    user_id text,
                    success integer not null,
                    detail text,
                    created_at text not null
                );

                create table if not exists mailbox_delivery_logs (
                    log_id text primary key,
                    recipient text not null,
                    subject text not null,
                    status text not null,
                    detail text,
                    metadata_json text,
                    created_at text not null
                );

                create table if not exists ui_audit_events (
                    event_id text primary key,
                    event_type text not null,
                    target text,
                    before_json text,
                    after_json text,
                    metadata_json text,
                    created_at text not null
                );

                create index if not exists idx_users_email on users(email);
                create index if not exists idx_reset_email on password_reset_tokens(email);
                create index if not exists idx_auth_audit_email on auth_audit(email, created_at desc);
                create index if not exists idx_mailbox_recipient on mailbox_delivery_logs(recipient, created_at desc);
                """
            )
            connection.commit()

    @staticmethod
    def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
        return dict(row) if row is not None else None

    def status(self) -> dict[str, Any]:
        with self._connect() as connection:
            user_count = int(connection.execute("select count(*) from users").fetchone()[0])
            reset_count = int(connection.execute("select count(*) from password_reset_tokens").fetchone()[0])
        return {
            "backend": "sqlite",
            "db_path": str(self.db_path),
            "user_count": user_count,
            "reset_token_count": reset_count,
        }

    def get_user_by_email(self, email: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute("select * from users where email = ?", (email.lower().strip(),)).fetchone()
        return self._row_to_dict(row)

    def get_user_by_id(self, user_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute("select * from users where id = ?", (user_id,)).fetchone()
        return self._row_to_dict(row)

    def register_user(self, *, email: str, name: str, password_hash: str, role: str = "user") -> dict[str, Any]:
        now = _iso_now()
        payload = {
            "id": secrets.token_urlsafe(12),
            "email": email.lower().strip(),
            "name": name.strip() or email.split("@")[0],
            "password_hash": password_hash,
            "role": role,
            "created_at": now,
            "updated_at": now,
        }
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                insert into users (id, email, name, password_hash, role, created_at, updated_at)
                values (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["id"],
                    payload["email"],
                    payload["name"],
                    payload["password_hash"],
                    payload["role"],
                    payload["created_at"],
                    payload["updated_at"],
                ),
            )
            connection.commit()
        self._mirror("users", payload)
        return payload

    def update_password(self, *, email: str, password_hash: str) -> dict[str, Any] | None:
        now = _iso_now()
        with self._lock, self._connect() as connection:
            connection.execute(
                "update users set password_hash = ?, updated_at = ? where email = ?",
                (password_hash, now, email.lower().strip()),
            )
            row = connection.execute("select * from users where email = ?", (email.lower().strip(),)).fetchone()
            connection.commit()
        payload = self._row_to_dict(row)
        if payload:
            self._mirror("users", payload)
        return payload

    def create_reset_token(self, *, token: str, email: str, expires_at: int) -> dict[str, Any]:
        payload = {
            "token": token,
            "email": email.lower().strip(),
            "expires_at": int(expires_at),
            "used": 0,
            "created_at": _iso_now(),
            "used_at": None,
        }
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                insert into password_reset_tokens (token, email, expires_at, used, created_at, used_at)
                values (?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["token"],
                    payload["email"],
                    payload["expires_at"],
                    payload["used"],
                    payload["created_at"],
                    payload["used_at"],
                ),
            )
            connection.commit()
        self._mirror("password_reset_tokens", payload)
        return payload

    def get_reset_token(self, token: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute("select * from password_reset_tokens where token = ?", (token,)).fetchone()
        return self._row_to_dict(row)

    def consume_reset_token(self, token: str) -> dict[str, Any] | None:
        now = _iso_now()
        with self._lock, self._connect() as connection:
            connection.execute(
                "update password_reset_tokens set used = 1, used_at = ? where token = ?",
                (now, token),
            )
            row = connection.execute("select * from password_reset_tokens where token = ?", (token,)).fetchone()
            connection.commit()
        payload = self._row_to_dict(row)
        if payload:
            self._mirror("password_reset_tokens", payload)
        return payload

    def record_auth_audit(
        self,
        *,
        event_type: str,
        email: str | None = None,
        user_id: str | None = None,
        success: bool,
        detail: str | None = None,
    ) -> dict[str, Any]:
        payload = {
            "audit_id": secrets.token_urlsafe(12),
            "event_type": event_type,
            "email": email.lower().strip() if email else None,
            "user_id": user_id,
            "success": 1 if success else 0,
            "detail": detail,
            "created_at": _iso_now(),
        }
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                insert into auth_audit (audit_id, event_type, email, user_id, success, detail, created_at)
                values (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["audit_id"],
                    payload["event_type"],
                    payload["email"],
                    payload["user_id"],
                    payload["success"],
                    payload["detail"],
                    payload["created_at"],
                ),
            )
            connection.commit()
        self._mirror("auth_audit", payload)
        return payload

    def record_mailbox_delivery(
        self,
        *,
        recipient: str,
        subject: str,
        status: str,
        detail: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        import json

        payload = {
            "log_id": secrets.token_urlsafe(12),
            "recipient": recipient,
            "subject": subject,
            "status": status,
            "detail": detail,
            "metadata_json": json.dumps(metadata or {}, ensure_ascii=False),
            "created_at": _iso_now(),
        }
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                insert into mailbox_delivery_logs (log_id, recipient, subject, status, detail, metadata_json, created_at)
                values (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["log_id"],
                    payload["recipient"],
                    payload["subject"],
                    payload["status"],
                    payload["detail"],
                    payload["metadata_json"],
                    payload["created_at"],
                ),
            )
            connection.commit()
        self._mirror("mailbox_delivery_logs", payload)
        return payload

    def _mirror(self, table: str, payload: dict[str, Any]) -> None:
        try:
            client = get_client()
            if getattr(client, "backend", "") == "in_memory":
                client.table(table).insert(payload).execute()
                return
            client.table(table).insert(payload).execute()
        except Exception as exc:
            logger.debug("AuthRepository supabase mirror skipped for %s: %s", table, exc)


_REPOSITORY: AuthRepository | None = None


def get_auth_repository() -> AuthRepository:
    global _REPOSITORY
    if _REPOSITORY is None:
        _REPOSITORY = AuthRepository()
    return _REPOSITORY
