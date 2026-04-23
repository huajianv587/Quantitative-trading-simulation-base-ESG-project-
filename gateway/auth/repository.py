from __future__ import annotations

import os
import secrets
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from gateway.config import settings
from gateway.db.supabase_client import get_client
from gateway.utils.logger import get_logger

logger = get_logger(__name__)


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _truthy(value: str | bool | None, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _new_id() -> str:
    return str(uuid.uuid4())


class AuthRepository:
    def __init__(
        self,
        db_path: str | Path | None = None,
        *,
        primary_backend: str | None = None,
        allow_sqlite_fallback: bool | None = None,
    ) -> None:
        base = Path(__file__).resolve().parents[2]
        target = Path(db_path) if db_path else base / "storage" / "auth" / "auth.sqlite3"
        if not target.is_absolute():
            target = base / target
        target.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = target
        self._lock = threading.RLock()
        self.primary_backend = (primary_backend or os.getenv("AUTH_PRIMARY_BACKEND") or getattr(settings, "AUTH_PRIMARY_BACKEND", "sqlite")).strip().lower()
        if self.primary_backend not in {"sqlite", "supabase"}:
            self.primary_backend = "sqlite"
        default_fallback = bool(getattr(settings, "AUTH_ALLOW_SQLITE_FALLBACK", True))
        env_fallback = os.getenv("AUTH_ALLOW_SQLITE_FALLBACK")
        self.allow_sqlite_fallback = _truthy(env_fallback, default_fallback) if allow_sqlite_fallback is None else bool(allow_sqlite_fallback)
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

    def _imap_ready(self) -> bool:
        host = os.getenv("IMAP_HOST") or getattr(settings, "IMAP_HOST", "")
        user = os.getenv("IMAP_USER") or getattr(settings, "IMAP_USER", "")
        password = os.getenv("IMAP_PASSWORD") or getattr(settings, "IMAP_PASSWORD", "")
        return bool(host and user and password)

    def _smtp_ready(self) -> bool:
        host = os.getenv("SMTP_HOST") or getattr(settings, "SMTP_HOST", "")
        port = os.getenv("SMTP_PORT") or str(getattr(settings, "SMTP_PORT", "") or "")
        user = os.getenv("SMTP_USER") or getattr(settings, "SMTP_USER", "")
        password = os.getenv("SMTP_PASSWORD") or getattr(settings, "SMTP_PASSWORD", "")
        return bool(host and port and user and password)

    def _supabase_client(self):
        return get_client()

    def _supabase_configured(self) -> bool:
        return bool(getattr(settings, "SUPABASE_URL", "") and getattr(settings, "SUPABASE_KEY", ""))

    def _supabase_ready(self) -> bool:
        if not self._supabase_configured():
            return False
        try:
            client = self._supabase_client()
            if getattr(client, "backend", "") == "in_memory":
                return False
            client.table("users").select("id").limit(1).execute()
            return True
        except Exception as exc:
            logger.debug("AuthRepository supabase readiness check failed: %s", exc)
            return False

    def _sqlite_status_counts(self) -> tuple[int, int]:
        with self._connect() as connection:
            user_count = int(connection.execute("select count(*) from users").fetchone()[0])
            reset_count = int(connection.execute("select count(*) from password_reset_tokens").fetchone()[0])
        return user_count, reset_count

    def _supabase_count(self, table_name: str) -> int:
        rows = self._supabase_client().table(table_name).select("*").execute().data or []
        return len(rows)

    def status(self) -> dict[str, Any]:
        sqlite_user_count, sqlite_reset_count = self._sqlite_status_counts()
        supabase_ready = self._supabase_ready()
        effective_backend = self.primary_backend
        user_count = sqlite_user_count
        reset_count = sqlite_reset_count
        if self.primary_backend == "supabase":
            if supabase_ready:
                effective_backend = "supabase"
                try:
                    user_count = self._supabase_count("users")
                    reset_count = self._supabase_count("password_reset_tokens")
                except Exception as exc:
                    logger.warning("AuthRepository status falling back to sqlite counts: %s", exc)
                    effective_backend = "sqlite_fallback" if self.allow_sqlite_fallback else "supabase_unavailable"
            else:
                effective_backend = "sqlite_fallback" if self.allow_sqlite_fallback else "supabase_unavailable"

        return {
            "backend": effective_backend,
            "primary_backend": self.primary_backend,
            "effective_backend": effective_backend,
            "sqlite_fallback_enabled": bool(self.allow_sqlite_fallback),
            "sqlite_ready": True,
            "db_path": str(self.db_path),
            "user_count": user_count,
            "reset_token_count": reset_count,
            "supabase_ready": supabase_ready,
            "supabase_backend": getattr(self._supabase_client(), "backend", "supabase") if self._supabase_configured() else "not_configured",
            "smtp_ready": self._smtp_ready(),
            "imap_ready": self._imap_ready(),
            "reset_delivery_mode": "email_imap_roundtrip" if self._smtp_ready() and self._imap_ready() else ("email_only" if self._smtp_ready() else "dev_token"),
        }

    def _sqlite_get_user_by_email(self, email: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute("select * from users where email = ?", (email.lower().strip(),)).fetchone()
        return self._row_to_dict(row)

    def _sqlite_get_user_by_id(self, user_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute("select * from users where id = ?", (user_id,)).fetchone()
        return self._row_to_dict(row)

    def _sqlite_register_user(self, *, email: str, name: str, password_hash: str, role: str = "user") -> dict[str, Any]:
        now = _iso_now()
        payload = {
            "id": _new_id(),
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
        return payload

    def _sqlite_update_password(self, *, email: str, password_hash: str) -> dict[str, Any] | None:
        now = _iso_now()
        with self._lock, self._connect() as connection:
            connection.execute(
                "update users set password_hash = ?, updated_at = ? where email = ?",
                (password_hash, now, email.lower().strip()),
            )
            row = connection.execute("select * from users where email = ?", (email.lower().strip(),)).fetchone()
            connection.commit()
        return self._row_to_dict(row)

    def _sqlite_create_reset_token(self, *, token: str, email: str, expires_at: int) -> dict[str, Any]:
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
        return payload

    def _sqlite_get_reset_token(self, token: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute("select * from password_reset_tokens where token = ?", (token,)).fetchone()
        return self._row_to_dict(row)

    def _sqlite_consume_reset_token(self, token: str) -> dict[str, Any] | None:
        now = _iso_now()
        with self._lock, self._connect() as connection:
            connection.execute(
                "update password_reset_tokens set used = 1, used_at = ? where token = ?",
                (now, token),
            )
            row = connection.execute("select * from password_reset_tokens where token = ?", (token,)).fetchone()
            connection.commit()
        return self._row_to_dict(row)

    def _sqlite_record_auth_audit(
        self,
        *,
        event_type: str,
        email: str | None = None,
        user_id: str | None = None,
        success: bool,
        detail: str | None = None,
    ) -> dict[str, Any]:
        payload = {
            "audit_id": _new_id(),
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
        return payload

    def _sqlite_record_mailbox_delivery(
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
            "log_id": _new_id(),
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
        return payload

    def _supabase_select_one(self, table: str, *, filters: dict[str, Any]) -> dict[str, Any] | None:
        query = self._supabase_client().table(table).select("*")
        for key, value in filters.items():
            query = query.eq(key, value)
        rows = list(query.limit(1).execute().data or [])
        return rows[0] if rows else None

    def _supabase_insert(self, table: str, payload: dict[str, Any]) -> dict[str, Any]:
        rows = list(self._supabase_client().table(table).insert(payload).execute().data or [])
        return rows[0] if rows else payload

    def _supabase_update(self, table: str, *, match: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any] | None:
        query = self._supabase_client().table(table).update(payload)
        for key, value in match.items():
            query = query.eq(key, value)
        rows = list(query.execute().data or [])
        return rows[0] if rows else None

    def _run_with_backend(
        self,
        operation_name: str,
        *,
        sqlite_call: Callable[[], Any],
        supabase_call: Callable[[], Any],
        fallback_read_call: Callable[[], Any] | None = None,
    ) -> Any:
        if self.primary_backend == "sqlite":
            return sqlite_call()

        try:
            if not self._supabase_configured():
                raise RuntimeError("supabase_not_configured")
            client = self._supabase_client()
            if getattr(client, "backend", "") == "in_memory":
                raise RuntimeError("supabase_client_in_memory")
            result = supabase_call()
            if result is None and fallback_read_call is not None and self.allow_sqlite_fallback:
                return fallback_read_call()
            return result
        except Exception as exc:
            if not self.allow_sqlite_fallback:
                raise
            logger.warning("AuthRepository %s degraded to sqlite fallback: %s", operation_name, exc)
            return sqlite_call()

    def get_user_by_email(self, email: str) -> dict[str, Any] | None:
        normalized = email.lower().strip()
        return self._run_with_backend(
            "get_user_by_email",
            sqlite_call=lambda: self._sqlite_get_user_by_email(normalized),
            supabase_call=lambda: self._supabase_select_one("users", filters={"email": normalized}),
            fallback_read_call=lambda: self._sqlite_get_user_by_email(normalized),
        )

    def get_user_by_id(self, user_id: str) -> dict[str, Any] | None:
        return self._run_with_backend(
            "get_user_by_id",
            sqlite_call=lambda: self._sqlite_get_user_by_id(user_id),
            supabase_call=lambda: self._supabase_select_one("users", filters={"id": user_id}),
            fallback_read_call=lambda: self._sqlite_get_user_by_id(user_id),
        )

    def register_user(self, *, email: str, name: str, password_hash: str, role: str = "user") -> dict[str, Any]:
        now = _iso_now()
        payload = {
            "id": _new_id(),
            "user_id": None,
            "email": email.lower().strip(),
            "name": name.strip() or email.split("@")[0],
            "password_hash": password_hash,
            "role": role,
            "created_at": now,
            "updated_at": now,
        }
        payload["user_id"] = payload["id"]
        return self._run_with_backend(
            "register_user",
            sqlite_call=lambda: self._sqlite_register_user(email=payload["email"], name=payload["name"], password_hash=password_hash, role=role),
            supabase_call=lambda: self._supabase_insert("users", payload),
        )

    def update_password(self, *, email: str, password_hash: str) -> dict[str, Any] | None:
        normalized = email.lower().strip()
        now = _iso_now()
        return self._run_with_backend(
            "update_password",
            sqlite_call=lambda: self._sqlite_update_password(email=normalized, password_hash=password_hash),
            supabase_call=lambda: self._supabase_update(
                "users",
                match={"email": normalized},
                payload={"password_hash": password_hash, "updated_at": now},
            ),
            fallback_read_call=lambda: self._sqlite_update_password(email=normalized, password_hash=password_hash),
        )

    def create_reset_token(self, *, token: str, email: str, expires_at: int) -> dict[str, Any]:
        payload = {
            "token": token,
            "email": email.lower().strip(),
            "expires_at": int(expires_at),
            "used": 0,
            "created_at": _iso_now(),
            "used_at": None,
        }
        return self._run_with_backend(
            "create_reset_token",
            sqlite_call=lambda: self._sqlite_create_reset_token(token=payload["token"], email=payload["email"], expires_at=payload["expires_at"]),
            supabase_call=lambda: self._supabase_insert("password_reset_tokens", payload),
        )

    def get_reset_token(self, token: str) -> dict[str, Any] | None:
        return self._run_with_backend(
            "get_reset_token",
            sqlite_call=lambda: self._sqlite_get_reset_token(token),
            supabase_call=lambda: self._supabase_select_one("password_reset_tokens", filters={"token": token}),
            fallback_read_call=lambda: self._sqlite_get_reset_token(token),
        )

    def consume_reset_token(self, token: str) -> dict[str, Any] | None:
        now = _iso_now()
        return self._run_with_backend(
            "consume_reset_token",
            sqlite_call=lambda: self._sqlite_consume_reset_token(token),
            supabase_call=lambda: self._supabase_update(
                "password_reset_tokens",
                match={"token": token},
                payload={"used": 1, "used_at": now},
            ),
            fallback_read_call=lambda: self._sqlite_consume_reset_token(token),
        )

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
            "audit_id": _new_id(),
            "event_type": event_type,
            "email": email.lower().strip() if email else None,
            "user_id": user_id,
            "success": 1 if success else 0,
            "detail": detail,
            "created_at": _iso_now(),
        }
        return self._run_with_backend(
            "record_auth_audit",
            sqlite_call=lambda: self._sqlite_record_auth_audit(
                event_type=event_type,
                email=email,
                user_id=user_id,
                success=success,
                detail=detail,
            ),
            supabase_call=lambda: self._supabase_insert("auth_audit", payload),
        )

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
            "log_id": _new_id(),
            "recipient": recipient,
            "subject": subject,
            "status": status,
            "detail": detail,
            "metadata_json": json.dumps(metadata or {}, ensure_ascii=False),
            "created_at": _iso_now(),
        }
        return self._run_with_backend(
            "record_mailbox_delivery",
            sqlite_call=lambda: self._sqlite_record_mailbox_delivery(
                recipient=recipient,
                subject=subject,
                status=status,
                detail=detail,
                metadata=metadata,
            ),
            supabase_call=lambda: self._supabase_insert("mailbox_delivery_logs", payload),
        )


_REPOSITORY: AuthRepository | None = None


def get_auth_repository() -> AuthRepository:
    global _REPOSITORY
    if _REPOSITORY is None:
        _REPOSITORY = AuthRepository()
    return _REPOSITORY


def reset_auth_repository() -> None:
    global _REPOSITORY
    _REPOSITORY = None
