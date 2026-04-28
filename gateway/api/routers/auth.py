"""
Auth router - register / login / reset-password.
Primary auth backend is configurable; real-mode acceptance targets Supabase.
Local/dev runtimes can still expose a dev reset token when explicitly allowed.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import sys
import time
from typing import Any
from urllib.parse import parse_qs, urlparse

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from gateway.auth.repository import get_auth_repository
from gateway.config import settings
from gateway.ops.security import is_local_origin
from gateway.utils.email_delivery import send_email_message, smtp_ready

router = APIRouter(prefix="/auth", tags=["auth"])

_LOCAL_DEV_SECRET = "local-dev-auth-secret-change-me"
_TOKEN_TTL = 86400 * 7
_RESET_TTL = 3600


def _auth_secret() -> str:
    secret = str(getattr(settings, "AUTH_SECRET_KEY", "") or os.getenv("AUTH_SECRET_KEY", "") or "").strip()
    if secret:
        return secret
    if str(getattr(settings, "APP_MODE", "local")).lower() == "prod":
        raise RuntimeError("AUTH_SECRET_KEY is required when APP_MODE=prod")
    return _LOCAL_DEV_SECRET


def validate_auth_runtime_config() -> None:
    _auth_secret()


def _hash_iterations() -> int:
    return max(100_000, int(getattr(settings, "AUTH_PASSWORD_PBKDF2_ITERATIONS", 260_000) or 260_000))


def _hash_password(password: str) -> str:
    iterations = _hash_iterations()
    salt = secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), iterations)
    return f"pbkdf2_sha256${iterations}${salt}${hashed.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        if stored.startswith("pbkdf2_sha256$"):
            _, iterations_raw, salt, digest = stored.split("$", 3)
            expected = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(iterations_raw))
            return hmac.compare_digest(expected.hex(), digest)
        salt, digest = stored.split(":", 1)
        expected = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
        return hmac.compare_digest(expected.hex(), digest)
    except Exception:
        return False


def _make_token(user_id: str) -> str:
    payload = f"{user_id}:{int(time.time()) + _TOKEN_TTL}"
    signature = hmac.new(_auth_secret().encode(), payload.encode(), hashlib.sha256).hexdigest()
    import base64

    return base64.urlsafe_b64encode(f"{payload}:{signature}".encode()).decode()


def _verify_token(token: str) -> str | None:
    try:
        import base64

        raw = base64.urlsafe_b64decode(token.encode()).decode()
        user_id, expires, signature = raw.rsplit(":", 2)
        payload = f"{user_id}:{expires}"
        expected = hmac.new(_auth_secret().encode(), payload.encode(), hashlib.sha256).hexdigest()
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


def _repo():
    return get_auth_repository()


def _extract_reset_token(raw: str) -> str:
    token = (raw or "").strip()
    if not token:
        return ""
    if "://" not in token:
        return token
    parsed = urlparse(token)
    params = parse_qs(parsed.query or "")
    if params.get("token"):
        return str(params["token"][0]).strip()
    if parsed.fragment and "token=" in parsed.fragment:
        fragment_params = parse_qs(parsed.fragment.split("?", 1)[-1])
        if fragment_params.get("token"):
            return str(fragment_params["token"][0]).strip()
    return token


def _allow_dev_reset_token(request: Request) -> bool:
    if str(getattr(settings, "APP_MODE", "local")).lower() != "local" and "pytest" not in sys.modules:
        return False
    client_host = str(getattr(request.client, "host", "") or "")
    request_host = str(request.url.hostname or "")
    return is_local_origin(client_host=client_host, request_host=request_host)


@router.get("/status")
def auth_status():
    return _repo().status()


@router.post("/register")
def register(req: RegisterRequest):
    email = req.email.strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Invalid email address")
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    repo = _repo()
    if repo.get_user_by_email(email):
        repo.record_auth_audit(event_type="register", email=email, success=False, detail="duplicate_email")
        raise HTTPException(status_code=409, detail="Email already registered")

    user = repo.register_user(email=email, name=req.name, password_hash=_hash_password(req.password))
    repo_status = repo.status()
    backend_detail = repo_status.get("effective_backend", repo_status.get("backend", "unknown"))
    repo.record_auth_audit(
        event_type="register",
        email=email,
        user_id=user["id"],
        success=True,
        detail=f"{backend_detail}_primary",
    )
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
    repo = _repo()
    user = repo.get_user_by_email(email)
    if not user or not _verify_password(req.password, str(user["password_hash"])):
        repo.record_auth_audit(event_type="login", email=email, success=False, detail="invalid_credentials")
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = _make_token(str(user["id"]))
    repo.record_auth_audit(event_type="login", email=email, user_id=str(user["id"]), success=True, detail="token_issued")
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
def reset_request(payload: ResetRequestPayload, request: Request):
    email = payload.email.strip().lower()
    repo = _repo()
    user = repo.get_user_by_email(email)
    if not user:
        repo.record_auth_audit(event_type="reset_request", email=email, success=True, detail="masked_missing_user")
        return {"message": "If that email is registered, a reset link has been sent."}

    reset_token = secrets.token_urlsafe(32)
    repo.create_reset_token(token=reset_token, email=email, expires_at=int(time.time()) + _RESET_TTL)

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
    if _allow_dev_reset_token(request):
        response["_dev_token"] = reset_token

    repo.record_auth_audit(event_type="reset_request", email=email, user_id=str(user["id"]), success=True, detail="token_created")
    return response


@router.post("/reset-password/confirm")
def reset_confirm(payload: ResetConfirmPayload):
    if len(payload.new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    repo = _repo()
    resolved_token = _extract_reset_token(payload.token)
    token_record = repo.get_reset_token(resolved_token)
    if not token_record:
        repo.record_auth_audit(event_type="reset_confirm", success=False, detail="invalid_token")
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    if int(token_record.get("used") or 0):
        repo.record_auth_audit(event_type="reset_confirm", email=str(token_record["email"]), success=False, detail="token_used")
        raise HTTPException(status_code=400, detail="Reset token already used")
    if int(time.time()) > int(token_record.get("expires_at") or 0):
        repo.record_auth_audit(event_type="reset_confirm", email=str(token_record["email"]), success=False, detail="token_expired")
        raise HTTPException(status_code=400, detail="Reset token has expired")

    updated = repo.update_password(email=str(token_record["email"]), password_hash=_hash_password(payload.new_password))
    if not updated:
        repo.record_auth_audit(event_type="reset_confirm", email=str(token_record["email"]), success=False, detail="user_missing")
        raise HTTPException(status_code=404, detail="User not found")

    repo.consume_reset_token(resolved_token)
    repo.record_auth_audit(
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
    user = _repo().get_user_by_id(user_id)
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
