"""
Auth router - register / login / reset-password
- Local SQLite is the primary development auth store.
- Supabase mirror is best-effort and optional.
- Reset flow keeps the existing dev-token convenience for local testing.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import sys
import time
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from gateway.auth.repository import get_auth_repository
from gateway.utils.email_delivery import send_email_message, smtp_ready

router = APIRouter(prefix="/auth", tags=["auth"])

_SECRET_KEY = os.getenv("AUTH_SECRET_KEY", "esg-quant-secret-change-in-prod-2026")
_TOKEN_TTL = 86400 * 7
_RESET_TTL = 3600
_repo = get_auth_repository()


def _hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return f"{salt}:{hashed.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        salt, digest = stored.split(":", 1)
        expected = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
        return hmac.compare_digest(expected.hex(), digest)
    except Exception:
        return False


def _make_token(user_id: str) -> str:
    payload = f"{user_id}:{int(time.time()) + _TOKEN_TTL}"
    signature = hmac.new(_SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
    import base64

    return base64.urlsafe_b64encode(f"{payload}:{signature}".encode()).decode()


def _verify_token(token: str) -> str | None:
    try:
        import base64

        raw = base64.urlsafe_b64decode(token.encode()).decode()
        user_id, expires, signature = raw.rsplit(":", 2)
        payload = f"{user_id}:{expires}"
        expected = hmac.new(_SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature):
            return None
        if int(time.time()) > int(expires):
            return None
        return user_id
    except Exception:
        return None


class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str = ""


class LoginRequest(BaseModel):
    email: str
    password: str


class ResetRequestPayload(BaseModel):
    email: str


class ResetConfirmPayload(BaseModel):
    token: str
    new_password: str


@router.get("/status")
def auth_status():
    return _repo.status()


@router.post("/register")
def register(req: RegisterRequest):
    email = req.email.strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Invalid email address")
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    if _repo.get_user_by_email(email):
        _repo.record_auth_audit(event_type="register", email=email, success=False, detail="duplicate_email")
        raise HTTPException(status_code=409, detail="Email already registered")

    user = _repo.register_user(email=email, name=req.name, password_hash=_hash_password(req.password))
    _repo.record_auth_audit(event_type="register", email=email, user_id=user["id"], success=True, detail="sqlite_primary")
    token = _make_token(user["id"])
    return {
        "token": token,
        "user": {
            "id": user["id"],
            "email": user["email"],
            "name": user["name"],
            "role": user["role"],
        },
        "message": "Registration successful",
    }


@router.post("/login")
def login(req: LoginRequest):
    email = req.email.strip().lower()
    user = _repo.get_user_by_email(email)
    if not user or not _verify_password(req.password, str(user["password_hash"])):
        _repo.record_auth_audit(event_type="login", email=email, success=False, detail="invalid_credentials")
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = _make_token(str(user["id"]))
    _repo.record_auth_audit(event_type="login", email=email, user_id=str(user["id"]), success=True, detail="token_issued")
    return {
        "token": token,
        "user": {
            "id": user["id"],
            "email": user["email"],
            "name": user.get("name", ""),
            "role": user.get("role", "user"),
        },
    }


@router.post("/reset-password/request")
def reset_request(payload: ResetRequestPayload):
    email = payload.email.strip().lower()
    user = _repo.get_user_by_email(email)
    if not user:
        _repo.record_auth_audit(event_type="reset_request", email=email, success=True, detail="masked_missing_user")
        return {"message": "If that email is registered, a reset link has been sent."}

    reset_token = secrets.token_urlsafe(32)
    _repo.create_reset_token(token=reset_token, email=email, expires_at=int(time.time()) + _RESET_TTL)

    is_dev = os.getenv("APP_MODE", "dev").lower() in ("dev", "development", "local") or "pytest" in sys.modules
    response: dict[str, Any] = {"message": "If that email is registered, a reset link has been sent."}
    if smtp_ready():
        app_url = os.getenv("APP_PUBLIC_BASE_URL", "http://127.0.0.1:9000/app#/reset-password")
        email_result = send_email_message(
            recipient=email,
            subject="Quant Terminal password reset",
            text_body=(
                "A password reset was requested for your Quant Terminal account.\n\n"
                f"Reset token: {reset_token}\n"
                f"Reset page: {app_url}\n\n"
                "If you did not request this change, you can ignore this email."
            ),
            html_body=(
                "<html><body>"
                "<h2>Quant Terminal password reset</h2>"
                "<p>A password reset was requested for your account.</p>"
                f"<p><strong>Reset token:</strong> {reset_token}</p>"
                f'<p><a href="{app_url}">Open reset page</a></p>'
                "<p>If you did not request this change, you can ignore this email.</p>"
                "</body></html>"
            ),
        )
        response["email_delivery"] = "sent" if email_result.get("ok") else "failed"
        if not email_result.get("ok"):
            response["email_error"] = str(email_result.get("detail", "unknown_error"))
    if is_dev:
        response["_dev_token"] = reset_token

    _repo.record_auth_audit(event_type="reset_request", email=email, user_id=str(user["id"]), success=True, detail="token_created")
    return response


@router.post("/reset-password/confirm")
def reset_confirm(payload: ResetConfirmPayload):
    if len(payload.new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    token_record = _repo.get_reset_token(payload.token)
    if not token_record:
        _repo.record_auth_audit(event_type="reset_confirm", success=False, detail="invalid_token")
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    if int(token_record.get("used") or 0):
        _repo.record_auth_audit(event_type="reset_confirm", email=str(token_record["email"]), success=False, detail="token_used")
        raise HTTPException(status_code=400, detail="Reset token already used")
    if int(time.time()) > int(token_record.get("expires_at") or 0):
        _repo.record_auth_audit(event_type="reset_confirm", email=str(token_record["email"]), success=False, detail="token_expired")
        raise HTTPException(status_code=400, detail="Reset token has expired")

    updated = _repo.update_password(email=str(token_record["email"]), password_hash=_hash_password(payload.new_password))
    if not updated:
        _repo.record_auth_audit(event_type="reset_confirm", email=str(token_record["email"]), success=False, detail="user_missing")
        raise HTTPException(status_code=404, detail="User not found")

    _repo.consume_reset_token(payload.token)
    _repo.record_auth_audit(
        event_type="reset_confirm",
        email=str(updated["email"]),
        user_id=str(updated["id"]),
        success=True,
        detail="password_updated",
    )
    return {"message": "Password reset successful. You can now log in."}


@router.get("/verify")
def verify_token(token: str):
    user_id = _verify_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = _repo.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "valid": True,
        "user": {
            "id": user["id"],
            "email": user["email"],
            "name": user.get("name", ""),
            "role": user.get("role", "user"),
        },
    }
