"""
Auth router — register / login / reset-password
- Register: email + name + password (no email verification)
- Login: email + password → JWT token
- Reset password request: sends email (no-op in dev)
- Reset password confirm: token + new password
Users stored in local JSON file (simple, no extra DB dependency).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr

router = APIRouter(prefix="/auth", tags=["auth"])

# ── Storage ──────────────────────────────────────────────────────
_DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "auth"
_USERS_FILE = _DATA_DIR / "users.json"
_RESET_FILE  = _DATA_DIR / "reset_tokens.json"

_SECRET_KEY = os.getenv("AUTH_SECRET_KEY", "esg-quant-secret-change-in-prod-2026")
_TOKEN_TTL  = 86400 * 7   # 7 days


def _ensure_dir():
    _DATA_DIR.mkdir(parents=True, exist_ok=True)


def _load_users() -> dict[str, Any]:
    _ensure_dir()
    if not _USERS_FILE.exists():
        return {}
    try:
        return json.loads(_USERS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_users(users: dict[str, Any]):
    _ensure_dir()
    _USERS_FILE.write_text(json.dumps(users, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_reset_tokens() -> dict[str, Any]:
    _ensure_dir()
    if not _RESET_FILE.exists():
        return {}
    try:
        return json.loads(_RESET_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_reset_tokens(tokens: dict[str, Any]):
    _ensure_dir()
    _RESET_FILE.write_text(json.dumps(tokens, ensure_ascii=False, indent=2), encoding="utf-8")


# ── Helpers ───────────────────────────────────────────────────────
def _hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return f"{salt}:{h.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        salt, h = stored.split(":", 1)
        expected = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
        return hmac.compare_digest(expected.hex(), h)
    except Exception:
        return False


def _make_token(user_id: str) -> str:
    payload = f"{user_id}:{int(time.time()) + _TOKEN_TTL}"
    sig = hmac.new(_SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
    import base64
    raw = f"{payload}:{sig}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def _verify_token(token: str) -> str | None:
    """Returns user_id if valid, None otherwise."""
    try:
        import base64
        raw = base64.urlsafe_b64decode(token.encode()).decode()
        parts = raw.rsplit(":", 2)
        if len(parts) != 3:
            return None
        user_id, expires, sig = parts
        payload = f"{user_id}:{expires}"
        expected_sig = hmac.new(_SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected_sig, sig):
            return None
        if int(time.time()) > int(expires):
            return None
        return user_id
    except Exception:
        return None


# ── Schemas ───────────────────────────────────────────────────────
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


# ── Routes ───────────────────────────────────────────────────────
@router.post("/register")
def register(req: RegisterRequest):
    email = req.email.strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Invalid email address")
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    users = _load_users()
    if email in users:
        raise HTTPException(status_code=409, detail="Email already registered")

    user_id = secrets.token_urlsafe(12)
    users[email] = {
        "id": user_id,
        "email": email,
        "name": req.name.strip() or email.split("@")[0],
        "password_hash": _hash_password(req.password),
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "role": "user",
    }
    _save_users(users)

    token = _make_token(user_id)
    return {
        "token": token,
        "user": {
            "id": user_id,
            "email": email,
            "name": users[email]["name"],
            "role": "user",
        },
        "message": "Registration successful",
    }


@router.post("/login")
def login(req: LoginRequest):
    email = req.email.strip().lower()
    users = _load_users()
    user = users.get(email)
    if not user or not _verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = _make_token(user["id"])
    return {
        "token": token,
        "user": {
            "id": user["id"],
            "email": email,
            "name": user.get("name", ""),
            "role": user.get("role", "user"),
        },
    }


@router.post("/reset-password/request")
def reset_request(payload: ResetRequestPayload):
    email = payload.email.strip().lower()
    users = _load_users()
    if email not in users:
        # Don't reveal whether email exists
        return {"message": "If that email is registered, a reset link has been sent."}

    reset_token = secrets.token_urlsafe(32)
    tokens = _load_reset_tokens()
    tokens[reset_token] = {
        "email": email,
        "expires": int(time.time()) + 3600,  # 1 hour
        "used": False,
    }
    _save_reset_tokens(tokens)

    # In production: send email. In dev: return token in response for testing.
    import os
    is_dev = os.getenv("APP_MODE", "dev").lower() in ("dev", "development", "local")
    response: dict[str, Any] = {"message": "If that email is registered, a reset link has been sent."}
    if is_dev:
        response["_dev_token"] = reset_token  # Only for development testing

    return response


@router.post("/reset-password/confirm")
def reset_confirm(payload: ResetConfirmPayload):
    if len(payload.new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    tokens = _load_reset_tokens()
    token_data = tokens.get(payload.token)
    if not token_data:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    if token_data.get("used"):
        raise HTTPException(status_code=400, detail="Reset token already used")
    if int(time.time()) > token_data.get("expires", 0):
        raise HTTPException(status_code=400, detail="Reset token has expired")

    email = token_data["email"]
    users = _load_users()
    if email not in users:
        raise HTTPException(status_code=404, detail="User not found")

    users[email]["password_hash"] = _hash_password(payload.new_password)
    _save_users(users)

    token_data["used"] = True
    _save_reset_tokens(tokens)

    return {"message": "Password reset successful. You can now log in."}


@router.get("/verify")
def verify_token(token: str):
    user_id = _verify_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    users = _load_users()
    for email, user in users.items():
        if user["id"] == user_id:
            return {
                "valid": True,
                "user": {"id": user_id, "email": email, "name": user.get("name", ""), "role": user.get("role", "user")},
            }
    raise HTTPException(status_code=404, detail="User not found")
