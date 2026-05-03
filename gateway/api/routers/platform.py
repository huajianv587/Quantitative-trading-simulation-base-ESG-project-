from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter

from gateway.app_runtime import runtime
from gateway.platform.production_ops import build_release_health, build_schema_health

router = APIRouter(prefix="/api/v1/platform", tags=["platform"])


@router.get("/schema-health")
def schema_health() -> dict[str, Any]:
    return build_schema_health(get_client=runtime.get_client)


@router.get("/release-health")
def release_health() -> dict[str, Any]:
    return build_release_health(
        get_client=runtime.get_client,
        quant_service=runtime.quant_system,
        trading_service=runtime.trading_service,
    )


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _ui_action_path() -> Path:
    return _project_root() / "storage" / "quant" / "ui_action_evidence" / "events.jsonl"


def _safe_text(value: Any, max_len: int = 500) -> str:
    return str(value or "").strip()[:max_len]


def _sanitize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    target = payload.get("target") if isinstance(payload.get("target"), dict) else {}
    context = payload.get("context") if isinstance(payload.get("context"), dict) else {}
    return {
        "event_type": _safe_text(payload.get("event_type") or "click", 32) or "click",
        "route": _safe_text(payload.get("route") or context.get("route") or "", 120),
        "url_hash": _safe_text(payload.get("url_hash") or context.get("url_hash") or "", 160),
        "target": {
            "tag": _safe_text(target.get("tag"), 32),
            "id": _safe_text(target.get("id"), 120),
            "role": _safe_text(target.get("role"), 64),
            "label": _safe_text(target.get("label"), 160),
            "href": _safe_text(target.get("href"), 300),
            "name": _safe_text(target.get("name"), 120),
            "type": _safe_text(target.get("type"), 64),
            "contract": _safe_text(target.get("contract"), 80),
        },
        "outcome": {
            "route_changed": bool((payload.get("outcome") or {}).get("route_changed")),
            "dom_changed": bool((payload.get("outcome") or {}).get("dom_changed")),
            "business_request_count": int((payload.get("outcome") or {}).get("business_request_count") or 0),
        },
        "client": {
            "app_id": _safe_text((payload.get("client") or {}).get("app_id"), 80),
            "viewport": (payload.get("client") or {}).get("viewport") or {},
        },
    }


@router.post("/ui-action/evidence")
def record_ui_action_evidence(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Persist a backend evidence record for UI clicks that do not have a domain API."""
    event = _sanitize_payload(payload or {})
    action_id = f"ui_{uuid4().hex[:12]}"
    generated_at = datetime.now(timezone.utc).isoformat()
    record = {
        "action_id": action_id,
        "status": "ready",
        "generated_at": generated_at,
        "channel": "ui_action_evidence",
        **event,
    }
    path = _ui_action_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        return {
            "status": "ready",
            "action_id": action_id,
            "generated_at": generated_at,
            "channel": "ui_action_evidence",
            "route": record["route"],
            "target": record["target"],
            "storage": {"backend": "local_file", "path": str(path)},
            "display": {
                "title": "操作已连接",
                "message": "该点击已连接后端证据链；业务按钮仍以对应业务 API 结果为准。",
            },
            "next_actions": ["在页面状态区查看最新反馈", "如需审计可读取 ui_action_evidence/events.jsonl"],
        }
    except Exception as exc:
        return {
            "status": "degraded",
            "action_id": action_id,
            "generated_at": generated_at,
            "channel": "ui_action_evidence",
            "route": record["route"],
            "target": record["target"],
            "reason": "ui_action_evidence_write_failed",
            "error": str(exc),
            "missing_config": [],
            "next_actions": ["检查 storage/quant/ui_action_evidence 写权限"],
        }


@router.get("/ui-action/evidence/latest")
def latest_ui_action_evidence(limit: int = 50) -> dict[str, Any]:
    path = _ui_action_path()
    if not path.exists():
        return {
            "status": "degraded",
            "reason": "no_ui_action_evidence_recorded",
            "events": [],
            "storage": {"backend": "local_file", "path": str(path)},
            "next_actions": ["在网页端点击任意按钮或链接以生成证据"],
        }
    lines = path.read_text(encoding="utf-8").splitlines()
    events: list[dict[str, Any]] = []
    for line in lines[-max(1, min(int(limit or 50), 200)):]:
        try:
            parsed = json.loads(line)
            if isinstance(parsed, dict):
                events.append(parsed)
        except Exception:
            continue
    return {
        "status": "ready" if events else "degraded",
        "events": events,
        "count": len(events),
        "storage": {"backend": "local_file", "path": str(path)},
        "next_actions": ["使用 action_id 关联前端反馈和后端证据"],
    }
