from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

from gateway.config import settings


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


def auth_scope_for_path(path: str) -> str | None:
    normalized = str(path or "")
    if normalized.startswith("/ops"):
        return "ops"
    if normalized.startswith("/admin"):
        return "admin"
    if normalized.startswith("/api/v1/quant/execution") or normalized.startswith("/api/v1/quant/validation"):
        return "execution"
    return None


def configured_keys_for_scope(scope: str) -> list[str]:
    if scope == "ops":
        return [value for value in [settings.OPS_API_KEY, settings.ADMIN_API_KEY] if value]
    if scope == "admin":
        return [value for value in [settings.ADMIN_API_KEY, settings.OPS_API_KEY] if value]
    if scope == "execution":
        return [value for value in [settings.EXECUTION_API_KEY, settings.ADMIN_API_KEY, settings.OPS_API_KEY] if value]
    return []


def auth_posture() -> dict[str, Any]:
    return {
        "execution_api_key_set": bool(settings.EXECUTION_API_KEY),
        "admin_api_key_set": bool(settings.ADMIN_API_KEY),
        "ops_api_key_set": bool(settings.OPS_API_KEY),
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
    localhost_hosts = {"127.0.0.1", "localhost", "::1", "testclient", "testserver"}
    return client_host in localhost_hosts and request_host in localhost_hosts


def is_local_origin(*, client_host: str, request_host: str) -> bool:
    localhost_hosts = {"127.0.0.1", "localhost", "::1", "testclient", "testserver"}
    return str(client_host or "") in localhost_hosts and str(request_host or "") in localhost_hosts


def _scope_requires_auth(scope: str) -> bool:
    del scope
    return bool(getattr(settings, "AUTH_DEFAULT_REQUIRED", False))


def authorize_request(request: Request) -> JSONResponse | None:
    path = request.url.path
    if path == "/ops/metrics" and getattr(settings, "METRICS_PUBLIC", False):
        return None

    scope = auth_scope_for_path(path)
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
