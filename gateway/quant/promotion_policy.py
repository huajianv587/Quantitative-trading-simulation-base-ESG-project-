from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gateway.config import settings


DEFAULT_PROMOTION_POLICY: dict[str, Any] = {
    "policy_id": "paper_default_v1",
    "version": 1,
    "paper_promoted": {
        "min_valid_days": 60,
        "min_net_return": 0.0,
        "min_excess_return": 0.0,
        "min_sharpe": 0.5,
        "max_drawdown": 0.08,
        "require_no_synthetic": True,
    },
    "live_canary": {
        "min_valid_days": 60,
        "min_net_return": 0.0,
        "min_excess_return": 0.0,
        "min_sharpe": 0.5,
        "max_drawdown": 0.08,
        "min_filled_orders": 0,
        "min_settled_outcomes": 0,
        "max_reject_rate": 1.0,
        "max_avg_slippage_bps": 9999.0,
        "min_calendar_coverage": 0.0,
        "require_no_synthetic": True,
        "require_broker_sync_clean": True,
        "require_kill_switch_released": True,
        "require_alpaca_paper_ready": True,
    },
}


def _resolve_policy_path() -> Path:
    raw = str(getattr(settings, "PROMOTION_POLICY_PATH", "configs/promotion_policy.paper.json") or "").strip()
    path = Path(raw or "configs/promotion_policy.paper.json")
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[2] / path
    return path


def load_promotion_policy() -> dict[str, Any]:
    path = _resolve_policy_path()
    if not path.exists():
        payload = dict(DEFAULT_PROMOTION_POLICY)
        payload["source"] = "default"
        payload["path"] = str(path)
        return payload
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        loaded = {}
    policy = dict(DEFAULT_PROMOTION_POLICY)
    for section in ("paper_promoted", "live_canary"):
        merged = dict(policy.get(section) or {})
        merged.update(dict(loaded.get(section) or {}))
        policy[section] = merged
    for key, value in loaded.items():
        if key not in {"paper_promoted", "live_canary"}:
            policy[key] = value
    policy["source"] = "file"
    policy["path"] = str(path)
    return policy


def evaluate_thresholds(metrics: dict[str, Any], quality: dict[str, Any], policy: dict[str, Any], section: str) -> dict[str, Any]:
    rules = dict(policy.get(section) or {})
    synthetic_count = int(quality.get("synthetic_count") or 0)
    checks = {
        "valid_days": int(metrics.get("valid_days") or 0) >= int(rules.get("min_valid_days", 0) or 0),
        "net_return": float(metrics.get("net_return") or 0.0) > float(rules.get("min_net_return", 0.0) or 0.0),
        "excess_return": float(metrics.get("excess_return") or 0.0) > float(rules.get("min_excess_return", 0.0) or 0.0),
        "sharpe": float(metrics.get("sharpe") or 0.0) >= float(rules.get("min_sharpe", 0.0) or 0.0),
        "max_drawdown": float(metrics.get("max_drawdown") or 0.0) <= float(rules.get("max_drawdown", 1.0) or 1.0),
        "filled_orders": int(quality.get("filled_count") or 0) >= int(rules.get("min_filled_orders", 0) or 0),
        "settled_outcomes": int(quality.get("settled_count") or 0) >= int(rules.get("min_settled_outcomes", 0) or 0),
        "reject_rate": float(quality.get("reject_rate") or 0.0) <= float(rules.get("max_reject_rate", 1.0) or 1.0),
        "avg_slippage_bps": float(quality.get("avg_slippage_bps") or 0.0) <= float(rules.get("max_avg_slippage_bps", 9999.0) or 9999.0),
        "calendar_coverage": float(quality.get("calendar_coverage") or 0.0) >= float(rules.get("min_calendar_coverage", 0.0) or 0.0),
        "no_synthetic": (synthetic_count == 0) if bool(rules.get("require_no_synthetic", True)) else True,
    }
    return {
        "section": section,
        "rules": rules,
        "checks": checks,
        "blockers": [key for key, ok in checks.items() if not ok],
        "passed": all(checks.values()),
    }

