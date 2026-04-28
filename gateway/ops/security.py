from __future__ import annotations

import threading
import time
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

from gateway.config import settings

MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
LOCALHOST_HOSTS = {"127.0.0.1", "localhost", "::1", "testclient", "testserver"}

PUBLIC_EXACT_PATHS = {
    "/auth/register",
    "/auth/login",
    "/auth/reset-password/request",
    "/auth/reset-password/confirm",
    "/auth/status",
    "/auth/verify",
    "/api/auth/register",
    "/api/auth/login",
    "/api/auth/reset-password/request",
    "/api/auth/reset-password/confirm",
    "/api/auth/status",
    "/api/auth/verify",
    "/livez",
    "/health",
    "/api/health",
    "/openapi.json",
}

PUBLIC_PREFIXES = (
    "/docs",
    "/redoc",
    "/app",
)

SCOPE_KEY_ATTRS: dict[str, tuple[str, ...]] = {
    "admin": ("ADMIN_API_KEY", "OPS_API_KEY"),
    "ops": ("OPS_API_KEY", "ADMIN_API_KEY"),
    "execution": ("EXECUTION_API_KEY", "ADMIN_API_KEY", "OPS_API_KEY"),
    "trading": ("TRADING_API_KEY", "EXECUTION_API_KEY", "ADMIN_API_KEY", "OPS_API_KEY"),
    "scheduler": ("SCHEDULER_API_KEY", "OPS_API_KEY", "ADMIN_API_KEY"),
    "research": ("RESEARCH_API_KEY", "ADMIN_API_KEY", "OPS_API_KEY"),
    "user": ("USER_API_KEY", "ADMIN_API_KEY", "OPS_API_KEY"),
}

_RATE_LIMIT_LOCK = threading.RLock()
_RATE_LIMIT_BUCKETS: dict[tuple[str, str], list[float]] = {}


def extract_api_key(request: Request) -> str:
    header_key = request.headers.get("x-api-key", "").strip()
    if header_key:
        return header_key

    auth_header = request.headers.get("authorization", "").strip()
    if auth_header.lower().startswith("bearer "):
        return auth_header.split(" ", 1)[1].strip()

    if not getattr(settings, "AUTH_BEARER_ONLY", False) and auth_header.lower().startswith("token "):
        return auth_header.split(" ", 1)[1].strip()

    return ""


def is_public_path(path: str) -> bool:
    normalized = str(path or "").split("?", 1)[0].rstrip("/") or "/"
    if normalized in PUBLIC_EXACT_PATHS:
        return True
    return any(normalized == prefix or normalized.startswith(f"{prefix}/") for prefix in PUBLIC_PREFIXES)


def auth_scope_for_path(path: str, method: str | None = None) -> str | None:
    normalized = str(path or "")
    method_name = str(method or "").upper()
    if is_public_path(normalized):
        return None
    if normalized.startswith("/ops"):
        return "ops"
    if normalized.startswith("/admin"):
        return "admin"
    if normalized.startswith("/scheduler"):
        return "scheduler"
    if normalized.startswith("/user"):
        return "user"
    if normalized.startswith("/api/v1/trading") or normalized.startswith("/watchlist"):
        return "trading"
    if (
        normalized.startswith("/api/v1/quant/execution")
        or normalized.startswith("/api/v1/quant/validation")
        or normalized.startswith("/api/v1/quant/workflows")
        or normalized.startswith("/api/v1/quant/paper")
        or normalized.startswith("/api/v1/quant/promotion")
        or normalized.startswith("/api/v1/quant/models")
        or normalized.startswith("/api/v1/quant/deployment")
        or normalized.startswith("/api/v1/quant/observability")
        or normalized.startswith("/api/v1/quant/storage")
        or normalized.startswith("/api/v1/quant/submit-locks")
        or normalized.startswith("/api/v1/quant/session-evidence")
    ):
        return "execution"
    if normalized.startswith("/api/v1/connectors"):
        return "research"
    if normalized.startswith("/api/v1/quant/rl/promote"):
        return "execution"
    if normalized.startswith("/api/v1/quant/rl"):
        return "research"
    if normalized.startswith("/api/v1/quant"):
        return "research"
    if normalized.startswith("/session") or normalized.startswith("/query") or normalized.startswith("/agent"):
        return "user"
    if method_name in MUTATING_METHODS:
        return "user"
    return None


def configured_keys_for_scope(scope: str) -> list[str]:
    values: list[str] = []
    for attr in SCOPE_KEY_ATTRS.get(scope, ()):
        value = str(getattr(settings, attr, "") or "").strip()
        if value and value not in values:
            values.append(value)
    return values


def auth_posture() -> dict[str, Any]:
    return {
        "execution_api_key_set": bool(settings.EXECUTION_API_KEY),
        "admin_api_key_set": bool(settings.ADMIN_API_KEY),
        "ops_api_key_set": bool(settings.OPS_API_KEY),
        "scope_key_sets": {
            scope: bool(configured_keys_for_scope(scope))
            for scope in sorted(SCOPE_KEY_ATTRS)
        },
        "bearer_only": bool(settings.AUTH_BEARER_ONLY),
        "metrics_public": bool(settings.METRICS_PUBLIC),
        "default_required": bool(getattr(settings, "AUTH_DEFAULT_REQUIRED", False)),
        "allow_localhost_dev": bool(getattr(settings, "AUTH_ALLOW_LOCALHOST_DEV", True)),
    }


def authorize_api_key(scope: str, presented: str) -> bool:
    allowed_keys = configured_keys_for_scope(scope)
    if not allowed_keys:
        return not bool(getattr(settings, "AUTH_DEFAULT_REQUIRED", False))
    return bool(presented and presented in allowed_keys)


def _is_local_request(request: Request) -> bool:
    client_host = str(getattr(request.client, "host", "") or "")
    request_host = str(request.url.hostname or "")
    return client_host in LOCALHOST_HOSTS and request_host in LOCALHOST_HOSTS


def is_local_origin(*, client_host: str, request_host: str) -> bool:
    return str(client_host or "") in LOCALHOST_HOSTS and str(request_host or "") in LOCALHOST_HOSTS


def _scope_requires_auth(scope: str) -> bool:
    del scope
    return bool(getattr(settings, "AUTH_DEFAULT_REQUIRED", False))


def _rate_limit_bucket(request: Request) -> tuple[str, int, int] | None:
    path = request.url.path
    method = request.method.upper()
    if path in {"/auth/login", "/api/auth/login"}:
        return ("auth_login", int(getattr(settings, "AUTH_LOGIN_RATE_LIMIT_MAX", 12) or 12), int(getattr(settings, "AUTH_RATE_LIMIT_WINDOW_SECONDS", 60) or 60))
    if path in {"/auth/reset-password/request", "/api/auth/reset-password/request"}:
        return ("auth_reset", int(getattr(settings, "AUTH_RESET_RATE_LIMIT_MAX", 6) or 6), int(getattr(settings, "AUTH_RATE_LIMIT_WINDOW_SECONDS", 60) or 60))
    if path.startswith("/api/v1/connectors") or path.startswith("/api/v1/quant/intelligence"):
        return ("external_scan", int(getattr(settings, "EXTERNAL_SCAN_RATE_LIMIT_MAX", 30) or 30), int(getattr(settings, "EXTERNAL_SCAN_RATE_LIMIT_WINDOW_SECONDS", 60) or 60))
    if method in MUTATING_METHODS and auth_scope_for_path(path, method) is not None:
        return ("mutation", int(getattr(settings, "API_MUTATION_RATE_LIMIT_MAX", 120) or 120), int(getattr(settings, "API_MUTATION_RATE_LIMIT_WINDOW_SECONDS", 60) or 60))
    return None


def _rate_limit_request(request: Request) -> JSONResponse | None:
    bucket = _rate_limit_bucket(request)
    if bucket is None:
        return None
    if bool(getattr(settings, "AUTH_ALLOW_LOCALHOST_DEV", True)) and _is_local_request(request):
        return None

    bucket_name, limit, window_seconds = bucket
    now = time.time()
    client_host = str(getattr(request.client, "host", "") or "unknown")
    api_key_hint = extract_api_key(request)[-8:]
    key = (bucket_name, f"{client_host}:{api_key_hint}")
    window_start = now - max(1, window_seconds)
    with _RATE_LIMIT_LOCK:
        hits = [timestamp for timestamp in _RATE_LIMIT_BUCKETS.get(key, []) if timestamp >= window_start]
        if len(hits) >= max(1, limit):
            _RATE_LIMIT_BUCKETS[key] = hits
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded.",
                    "bucket": bucket_name,
                    "retry_after_seconds": max(1, int(window_seconds)),
                },
                headers={"Retry-After": str(max(1, int(window_seconds)))},
            )
        hits.append(now)
        _RATE_LIMIT_BUCKETS[key] = hits
    return None


def auth_coverage_for_app(app: Any) -> dict[str, Any]:
    mutating_total = 0
    mutating_scoped = 0
    unscoped_mutating: list[dict[str, str]] = []
    scopes: dict[str, int] = {}
    for route in getattr(app, "routes", []) or []:
        path = str(getattr(route, "path", "") or "")
        methods = set(getattr(route, "methods", set()) or set())
        for method in sorted(methods & MUTATING_METHODS):
            if is_public_path(path):
                continue
            mutating_total += 1
            scope = auth_scope_for_path(path, method)
            if scope is None:
                unscoped_mutating.append({"method": method, "path": path})
                continue
            mutating_scoped += 1
            scopes[scope] = scopes.get(scope, 0) + 1
    return {
        "mutating_routes_total": mutating_total,
        "mutating_routes_scoped": mutating_scoped,
        "unscoped_mutating_count": len(unscoped_mutating),
        "unscoped_mutating_routes": unscoped_mutating[:50],
        "scope_counts": scopes,
    }


def authorize_request(request: Request) -> JSONResponse | None:
    rate_limited = _rate_limit_request(request)
    if rate_limited is not None:
        return rate_limited

    path = request.url.path
    if path == "/ops/metrics" and getattr(settings, "METRICS_PUBLIC", False):
        return None

    scope = auth_scope_for_path(path, request.method)
    if scope is None:
        return None

    if bool(getattr(settings, "AUTH_ALLOW_LOCALHOST_DEV", True)) and _is_local_request(request):
        return None

    allowed_keys = configured_keys_for_scope(scope)
    if not allowed_keys:
        if not _scope_requires_auth(scope):
            return None
        return JSONResponse(
            status_code=401,
            content={
                "detail": f"{scope} scope requires API key configuration before remote access is allowed.",
                "scope": scope,
            },
        )

    presented = extract_api_key(request)
    if presented and presented in allowed_keys:
        return None

    return JSONResponse(
        status_code=401,
        content={
            "detail": f"Missing or invalid API key for {scope} scope.",
            "scope": scope,
        },
    )
