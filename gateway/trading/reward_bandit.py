from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from math import sqrt
from typing import Any

import numpy as np

from gateway.config import settings
from gateway.quant.trading_calendar import TradingCalendarService


HORIZON_WEIGHTS = {"n1": 0.30, "n3": 0.30, "n5": 0.40}
DEFAULT_HORIZONS = (1, 3, 5)
FEATURE_NAMES = [
    "bias",
    "expected_return",
    "confidence",
    "overall_score",
    "risk_score",
    "target_weight",
    "execution_cost_bps",
    "direction",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_dt(value: Any) -> datetime | None:
    if value in {None, ""}:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def parse_date(value: Any) -> date | None:
    parsed = parse_dt(value)
    if parsed is not None:
        return parsed.date()
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def business_date_after(start: date, business_days: int) -> date:
    calendar = TradingCalendarService()
    return date.fromisoformat(calendar.session_after(start, int(business_days)))


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in {None, ""}:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def action_direction(action: str) -> float:
    return -1.0 if str(action or "").strip().lower() in {"short", "sell"} else 1.0


def horizon_key(horizon: int) -> str:
    return f"n{int(horizon)}"


def configured_horizons() -> tuple[int, ...]:
    raw = str(getattr(settings, "RLVR_HORIZONS", "") or "").strip()
    values: list[int] = []
    for token in raw.split(","):
        try:
            horizon = int(token.strip())
        except ValueError:
            continue
        if horizon > 0:
            values.append(horizon)
    return tuple(dict.fromkeys(values)) or DEFAULT_HORIZONS


def configured_horizon_weights(horizons: tuple[int, ...] | None = None) -> dict[str, float]:
    selected = horizons or configured_horizons()
    raw_weights = [
        token.strip()
        for token in str(getattr(settings, "RLVR_WEIGHTS", "") or "").split(",")
        if token.strip()
    ]
    weights: dict[str, float] = {}
    for index, horizon in enumerate(selected):
        weight = HORIZON_WEIGHTS.get(horizon_key(horizon))
        if index < len(raw_weights):
            try:
                weight = float(raw_weights[index])
            except ValueError:
                pass
        weights[horizon_key(horizon)] = float(weight if weight is not None else 1.0)
    total = sum(max(value, 0.0) for value in weights.values())
    if total <= 0:
        even = 1.0 / max(len(selected), 1)
        return {horizon_key(horizon): even for horizon in selected}
    return {key: max(value, 0.0) / total for key, value in weights.items()}


def build_horizon_states(entry_at: str, horizons: tuple[int, ...] | None = None) -> dict[str, dict[str, Any]]:
    entry_date = parse_date(entry_at) or datetime.now(timezone.utc).date()
    calendar = TradingCalendarService()
    entry_session = entry_date.isoformat() if calendar.is_session(entry_date) else calendar.next_session(entry_date) or entry_date.isoformat()
    selected_horizons = horizons or configured_horizons()
    return {
        horizon_key(horizon): {
            "horizon": int(horizon),
            "status": "pending",
            "due_date": calendar.session_after(entry_session, int(horizon)),
            "entry_session_date": entry_session,
            "due_session_date": calendar.session_after(entry_session, int(horizon)),
            "settled_session_date": None,
            "calendar_id": calendar.calendar_id,
            "calendar_status": "pending",
            "close_price": None,
            "close_date": None,
            "return_pct": None,
            "score": None,
            "score_components": {},
            "settled_at": None,
        }
        for horizon in selected_horizons
    }


def compute_reward_score(
    *,
    directional_return: float,
    transaction_cost: float,
    volatility: float,
    esg_score: float | None = None,
) -> dict[str, float]:
    adverse_return = max(0.0, -float(directional_return))
    drawdown_penalty = adverse_return * 0.20
    volatility_penalty = abs(float(directional_return)) * max(float(volatility), 0.0) * 0.10
    esg_bonus = 0.0
    if esg_score is not None:
        esg_bonus = max(-0.002, min(0.002, (float(esg_score) - 50.0) / 25_000.0))
    risk_adjusted_return = float(directional_return) - drawdown_penalty - volatility_penalty
    score = risk_adjusted_return - float(transaction_cost) + esg_bonus
    return {
        "risk_adjusted_return": float(risk_adjusted_return),
        "transaction_cost": float(transaction_cost),
        "drawdown_penalty": float(drawdown_penalty),
        "volatility_penalty": float(volatility_penalty),
        "esg_bonus": float(esg_bonus),
        "score": float(score),
    }


def weighted_score(settlements: dict[str, Any]) -> float | None:
    weights = configured_horizon_weights()
    total = 0.0
    weight_sum = 0.0
    for key, weight in weights.items():
        item = settlements.get(key) or {}
        score = item.get("score")
        if score is None:
            continue
        total += float(score) * weight
        weight_sum += weight
    if weight_sum <= 0:
        return None
    return float(total / weight_sum)


def final_weighted_score(settlements: dict[str, Any]) -> float | None:
    weights = configured_horizon_weights()
    if any((settlements.get(key) or {}).get("score") is None for key in weights):
        return None
    return weighted_score(settlements)


def rlvr_payload(
    settlements: dict[str, Any],
    *,
    bandit_updated_at: str | None = None,
) -> dict[str, Any]:
    weights = configured_horizon_weights()
    horizons = {
        key: {
            **dict(settlements.get(key) or {}),
            "weight": weights.get(key),
        }
        for key in weights
    }
    return {
        "metric": "rlvr",
        "horizons": horizons,
        "weights": weights,
        "partial_score": weighted_score(settlements),
        "final_score": final_weighted_score(settlements),
        "bandit_updated_at": bandit_updated_at,
    }


def attach_rlvr(payload: dict[str, Any]) -> dict[str, Any]:
    settlements = dict(payload.get("settlements") or {})
    existing = dict(payload.get("rlvr") or {})
    bandit_updated_at = payload.get("bandit_updated_at") or existing.get("bandit_updated_at")
    payload["rlvr"] = rlvr_payload(settlements, bandit_updated_at=bandit_updated_at)
    return payload


def candidate_feature_vector(candidate: dict[str, Any]) -> list[float]:
    features = dict(candidate.get("features") or {})
    action = str(candidate.get("action") or features.get("action") or "long")
    execution_cost_bps = safe_float(features.get("estimated_slippage_bps")) + safe_float(features.get("estimated_impact_bps"))
    return [
        1.0,
        safe_float(features.get("expected_return")),
        safe_float(features.get("confidence")),
        safe_float(features.get("overall_score")) / 100.0,
        safe_float(features.get("risk_score")) / 100.0,
        safe_float(features.get("target_weight")),
        execution_cost_bps / 10_000.0,
        action_direction(action),
    ]


def default_bandit_state(alpha: float = 0.6, ridge: float = 1.0) -> dict[str, Any]:
    return {
        "updated_at": utc_now(),
        "algorithm": "linucb",
        "alpha": float(alpha),
        "ridge": float(ridge),
        "feature_names": list(FEATURE_NAMES),
        "arms": {},
    }


def arm_key(candidate: dict[str, Any]) -> str:
    return f"{str(candidate.get('symbol') or '').upper()}:{str(candidate.get('action') or 'long').lower()}"


def _arm_payload(state: dict[str, Any], key: str) -> dict[str, Any]:
    dimension = len(state.get("feature_names") or FEATURE_NAMES)
    arms = state.setdefault("arms", {})
    if key not in arms:
        ridge = safe_float(state.get("ridge"), 1.0)
        arms[key] = {
            "A": (np.eye(dimension, dtype=np.float64) * ridge).tolist(),
            "b": np.zeros(dimension, dtype=np.float64).tolist(),
            "pulls": 0,
            "reward_sum": 0.0,
            "avg_reward": 0.0,
            "last_score": None,
            "updated_at": None,
        }
    return arms[key]


def bandit_score(state: dict[str, Any] | None, candidate: dict[str, Any]) -> float:
    state = deepcopy(state or default_bandit_state())
    x = np.asarray(candidate_feature_vector(candidate), dtype=np.float64)
    key = arm_key(candidate)
    arm = _arm_payload(state, key)
    A = np.asarray(arm["A"], dtype=np.float64)
    b = np.asarray(arm["b"], dtype=np.float64)
    try:
        inv_A = np.linalg.inv(A)
    except np.linalg.LinAlgError:
        inv_A = np.linalg.pinv(A)
    theta = inv_A @ b
    exploitation = float(theta @ x)
    exploration = safe_float(state.get("alpha"), 0.6) * sqrt(max(float(x @ inv_A @ x), 0.0))
    heuristic = (
        safe_float((candidate.get("features") or {}).get("expected_return"))
        + safe_float((candidate.get("features") or {}).get("confidence")) * 0.002
        + safe_float((candidate.get("features") or {}).get("overall_score")) / 20_000.0
    )
    return float(exploitation + exploration + heuristic)


def update_bandit_state(state: dict[str, Any] | None, candidate: dict[str, Any]) -> dict[str, Any]:
    next_state = deepcopy(state or default_bandit_state())
    score = candidate.get("score")
    if score is None:
        return next_state
    key = arm_key(candidate)
    arm = _arm_payload(next_state, key)
    x = np.asarray(candidate_feature_vector(candidate), dtype=np.float64)
    A = np.asarray(arm["A"], dtype=np.float64)
    b = np.asarray(arm["b"], dtype=np.float64)
    reward = float(score)
    A = A + np.outer(x, x)
    b = b + reward * x
    pulls = int(arm.get("pulls") or 0) + 1
    reward_sum = safe_float(arm.get("reward_sum")) + reward
    arm.update(
        {
            "A": A.tolist(),
            "b": b.tolist(),
            "pulls": pulls,
            "reward_sum": reward_sum,
            "avg_reward": reward_sum / max(pulls, 1),
            "last_score": reward,
            "updated_at": utc_now(),
        }
    )
    next_state["updated_at"] = utc_now()
    return next_state


def settle_candidate_with_bars(candidate: dict[str, Any], bars: list[dict[str, Any]]) -> tuple[dict[str, Any], bool]:
    payload = deepcopy(candidate)
    entry_price = safe_float(payload.get("entry_price"))
    entry_date = parse_date(payload.get("entry_at") or payload.get("created_at"))
    if entry_price <= 0 or entry_date is None:
        return payload, False
    calendar = TradingCalendarService()
    entry_session = entry_date.isoformat() if calendar.is_session(entry_date) else calendar.next_session(entry_date) or entry_date.isoformat()

    future_rows = []
    for row in bars:
        row_date = parse_date(row.get("timestamp") or row.get("ts") or row.get("date"))
        close = safe_float(row.get("close"), default=-1.0)
        if row_date is not None and row_date > entry_date and close > 0:
            future_rows.append((row_date, close))
    future_rows.sort(key=lambda item: item[0])

    settlements = dict(payload.get("settlements") or {})
    features = dict(payload.get("features") or {})
    direction = action_direction(str(payload.get("action") or "long"))
    transaction_cost = (
        safe_float(features.get("estimated_slippage_bps"))
        + safe_float(features.get("estimated_impact_bps"))
    ) / 10_000.0
    volatility = safe_float(features.get("predicted_volatility_10d"), default=0.15)
    esg_score = features.get("overall_score") or features.get("esg_score")
    changed = False

    for key, weight in configured_horizon_weights().items():
        item = dict(settlements.get(key) or {"horizon": int(key[1:]), "status": "pending"})
        if item.get("status") == "settled":
            continue
        horizon = int(item.get("horizon") or key[1:])
        due_session = str(item.get("due_session_date") or item.get("due_date") or calendar.session_after(entry_session, horizon))
        due_date = parse_date(due_session)
        if due_date is None:
            item["status"] = "pending"
            item["entry_session_date"] = entry_session
            item["calendar_id"] = calendar.calendar_id
            item["calendar_status"] = "pending"
            settlements[key] = item
            continue
        close_candidate = None
        for row_date, close in future_rows:
            if row_date >= due_date:
                close_candidate = (row_date, close)
                break
        if close_candidate is None:
            latest_date = future_rows[-1][0] if future_rows else None
            item["status"] = "data_missing" if latest_date is not None and latest_date >= due_date else "pending"
            item["entry_session_date"] = entry_session
            item["due_session_date"] = due_date.isoformat()
            item["due_date"] = due_date.isoformat()
            item["calendar_id"] = calendar.calendar_id
            item["calendar_status"] = item["status"]
            settlements[key] = item
            changed = True
            continue
        close_date, close_price = close_candidate
        directional_return = direction * (close_price / entry_price - 1.0)
        components = compute_reward_score(
            directional_return=directional_return,
            transaction_cost=transaction_cost,
            volatility=volatility,
            esg_score=safe_float(esg_score, default=50.0),
        )
        item.update(
            {
                "status": "settled",
                "entry_session_date": entry_session,
                "due_session_date": due_date.isoformat(),
                "settled_session_date": close_date.isoformat(),
                "calendar_id": calendar.calendar_id,
                "calendar_status": "settled",
                "close_price": float(close_price),
                "close_date": close_date.isoformat(),
                "return_pct": float(directional_return),
                "score": components["score"],
                "score_components": components,
                "settled_at": utc_now(),
            }
        )
        settlements[key] = item
        changed = True

    payload["settlements"] = settlements
    payload["partial_score"] = weighted_score(settlements)
    final_score = final_weighted_score(settlements)
    if final_score is not None:
        payload["score"] = final_score
        payload["status"] = "settled"
    elif any((settlements.get(key) or {}).get("status") == "settled" for key in settlements):
        payload["status"] = "partially_settled"
    attach_rlvr(payload)
    return payload, changed
