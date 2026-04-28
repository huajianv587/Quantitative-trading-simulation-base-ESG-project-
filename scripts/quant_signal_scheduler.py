from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from gateway.config import settings
from gateway.quant.service import get_quant_system
from gateway.quant.trading_calendar import TradingCalendarService

load_dotenv()


def now_local() -> datetime:
    return datetime.now(ZoneInfo(getattr(settings, "SCHEDULER_TIMEZONE", "America/New_York")))


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def trading_calendar() -> TradingCalendarService:
    return TradingCalendarService(getattr(settings, "TRADING_CALENDAR_ID", "XNYS"))


def scheduler_session_status(service=None) -> dict[str, Any]:
    if service is not None and hasattr(service, "get_trading_calendar_status"):
        try:
            return dict(service.get_trading_calendar_status())
        except Exception:
            pass
    return trading_calendar().status(at=now_local())


def require_trading_session() -> bool:
    return bool(getattr(settings, "SCHEDULER_REQUIRE_TRADING_SESSION", True))


def scheduler_session_date(service=None) -> str:
    status = scheduler_session_status(service)
    return str(status.get("session_date") or now_local().date().isoformat())


def skip_non_session(stage: str, state: dict[str, Any], service=None) -> dict[str, Any] | None:
    status = scheduler_session_status(service)
    if require_trading_session() and not status.get("is_session"):
        result = {
            "stage": stage,
            "timestamp": now_local().isoformat(),
            "skipped": True,
            "reason": "not_trading_session",
            "skip_reason": "not_trading_session",
            "session_date": status.get("session_date"),
            "calendar_id": status.get("calendar_id"),
            "market_clock_status": status.get("market_clock_status"),
            "next_session": status.get("next_session"),
        }
        update_heartbeat(state, stage=stage, message=result["reason"])
        record_scheduler_event(service, stage=stage, status="skipped", payload=result)
        return result
    return None


def record_scheduler_event(service, *, stage: str, status: str, payload: dict[str, Any]) -> None:
    if service is None or not hasattr(service, "record_scheduler_event"):
        return
    event_payload = dict(payload or {})
    event_payload.setdefault("stage", stage)
    event_payload.setdefault("status", status)
    event_payload.setdefault("error", None)
    event_payload.setdefault("duration_seconds", None)
    event_payload.setdefault("submitted_count", int(event_payload.get("submitted_count") or 0))
    if not event_payload.get("session_date"):
        try:
            session_status = scheduler_session_status(service)
            event_payload["session_date"] = session_status.get("session_date")
            event_payload.setdefault("calendar_id", session_status.get("calendar_id"))
            event_payload.setdefault("market_clock_status", session_status.get("market_clock_status"))
            event_payload.setdefault("next_session", session_status.get("next_session"))
        except Exception:
            event_payload["session_date"] = now_local().date().isoformat()
    try:
        service.record_scheduler_event(stage=stage, status=status, payload=event_payload)
    except Exception:
        return


def finalize_stage_result(result: dict[str, Any], *, started_at: float) -> dict[str, Any]:
    result.setdefault("duration_seconds", round(max(0.0, time.perf_counter() - started_at), 3))
    result.setdefault("error", result.get("reason") if str(result.get("status") or "").lower() in {"failed", "error"} else None)
    result.setdefault("submitted_count", int(result.get("submitted_count") or 0))
    return result


def resolve_path(configured: str | None, fallback: str) -> Path:
    raw = str(configured or "").strip()
    path = Path(raw) if raw else PROJECT_ROOT / fallback
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        probe = path.parent / ".write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return path
    except OSError:
        fallback_dir = Path(tempfile.gettempdir()) / "quant-esg-scheduler"
        fallback_dir.mkdir(parents=True, exist_ok=True)
        return fallback_dir / path.name
    return path


def scheduler_state_path() -> Path:
    return resolve_path(
        getattr(settings, "SCHEDULER_STATE_PATH", ""),
        "storage/quant/scheduler/runtime_state.json",
    )


def scheduler_heartbeat_path() -> Path:
    return resolve_path(
        getattr(settings, "SCHEDULER_HEARTBEAT_PATH", ""),
        "storage/quant/scheduler/heartbeat.json",
    )


def scheduler_lock_path() -> Path:
    return resolve_path(
        getattr(settings, "SCHEDULER_LOCK_PATH", ""),
        "storage/quant/scheduler/worker.lock",
    )


def load_json(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return dict(default or {})
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else dict(default or {})
    except Exception:
        return dict(default or {})


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def configured_universe(service) -> list[str]:
    raw = str(getattr(settings, "SCHEDULER_SIGNAL_UNIVERSE", "") or "")
    configured = [item.strip().upper() for item in raw.split(",") if item.strip()]
    if configured:
        return configured
    return [item.symbol for item in service.get_default_universe()]


def extract_actionable_symbols(research_payload: dict[str, Any], max_symbols: int) -> list[str]:
    ranked = [
        signal
        for signal in research_payload.get("signals", [])
        if isinstance(signal, dict)
        and str(signal.get("action", "")).lower() == "long"
        and float(signal.get("expected_return", 0.0) or 0.0) > 0
    ]
    ranked.sort(
        key=lambda signal: (
            -float(signal.get("expected_return", 0.0) or 0.0),
            -float(signal.get("confidence", 0.0) or 0.0),
            -float(signal.get("overall_score", 0.0) or 0.0),
        )
    )
    return [str(signal.get("symbol", "")).upper() for signal in ranked[:max_symbols] if signal.get("symbol")]


def _bars_result_rows(service, bars_result: Any) -> list[dict[str, Any]]:
    converter = getattr(service, "_bars_result_to_rows", None)
    if callable(converter):
        try:
            return converter(bars_result)
        except Exception:
            pass
    if isinstance(bars_result, list):
        return [row for row in bars_result if isinstance(row, dict)]
    bars = getattr(bars_result, "bars", None)
    if hasattr(bars, "to_dict"):
        return bars.to_dict(orient="records")
    return []


def _bar_session_date(row: dict[str, Any]) -> str:
    raw = row.get("timestamp") or row.get("date") or row.get("Datetime") or row.get("Date")
    text = str(raw or "").strip()
    return text[:10] if len(text) >= 10 else ""


def filter_fresh_symbols(
    service,
    symbols: list[str],
    *,
    session_date: str,
    phase: str = "submit",
    session_status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not bool(getattr(settings, "SCHEDULER_SYMBOL_FRESHNESS_ENABLED", True)):
        return {"symbols": symbols, "excluded_symbols": [], "enabled": False}
    if not hasattr(service, "market_data"):
        return {"symbols": symbols, "excluded_symbols": [], "enabled": False, "reason": "market_data_gateway_unavailable"}
    normalized_phase = str(phase or "submit").strip().lower()
    status = dict(session_status or {})
    previous_session = str(status.get("previous_session") or "")
    if not previous_session and hasattr(service, "trading_calendar"):
        try:
            previous_session = str(service.trading_calendar.previous_session(session_date) or "")
        except Exception:
            previous_session = ""
    submit_clock_ok = bool(status.get("effective_market_open") or status.get("market_clock_status") == "open")
    if normalized_phase == "preopen":
        required_date = previous_session or session_date
    elif normalized_phase == "settlement":
        required_date = session_date
    else:
        required_date = (previous_session or session_date) if submit_clock_ok else session_date
    kept: list[str] = []
    excluded: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    for symbol in symbols:
        normalized = str(symbol or "").upper().strip()
        if not normalized:
            continue
        try:
            bars_result = service.market_data.get_daily_bars(normalized, limit=5, force_refresh=False)
            rows = _bars_result_rows(service, bars_result)
            latest_date = ""
            for row in reversed(rows):
                latest_date = _bar_session_date(row)
                if latest_date:
                    break
            fresh_for_preopen = bool(latest_date and latest_date >= (previous_session or session_date))
            fresh_for_submit = bool(latest_date and latest_date >= ((previous_session or session_date) if submit_clock_ok else session_date))
            fresh_for_settlement = bool(latest_date and latest_date >= session_date)
            diagnostic = {
                "symbol": normalized,
                "latest_date": latest_date,
                "phase": normalized_phase,
                "required_date": required_date,
                "fresh_for_preopen": fresh_for_preopen,
                "fresh_for_submit": fresh_for_submit,
                "fresh_for_settlement": fresh_for_settlement,
                "market_clock_status": status.get("market_clock_status"),
            }
            diagnostics.append(diagnostic)
            if latest_date and latest_date >= required_date:
                kept.append(normalized)
            else:
                excluded.append({"symbol": normalized, "reason": "stale_market_data", **diagnostic})
        except Exception as exc:
            excluded.append({"symbol": normalized, "reason": "market_data_error", "error": str(exc)})
    return {
        "symbols": kept,
        "excluded_symbols": excluded,
        "enabled": True,
        "phase": normalized_phase,
        "required_date": required_date,
        "diagnostics": diagnostics,
    }


def due(current_hhmm: str, target_hhmm: str) -> bool:
    return current_hhmm >= target_hhmm


def between(current_hhmm: str, start_hhmm: str, end_hhmm: str) -> bool:
    return start_hhmm <= current_hhmm <= end_hhmm


def max_execution_symbols() -> int:
    return max(1, int(getattr(settings, "SCHEDULER_MAX_EXECUTION_SYMBOLS", 2) or 2))


def scheduler_execution_engine() -> str:
    return str(getattr(settings, "SCHEDULER_EXECUTION_ENGINE", "legacy_execution_plan") or "legacy_execution_plan").strip().lower()


def hybrid_workflow_enabled() -> bool:
    return scheduler_execution_engine() in {"hybrid_paper_workflow", "hybrid", "paper_strategy_workflow"}


def hybrid_workflow_time() -> str:
    return str(getattr(settings, "SCHEDULER_HYBRID_WORKFLOW_TIME", "09:35") or "09:35")


def sync_end_time_for_today() -> str:
    if require_trading_session():
        try:
            return trading_calendar().sync_end_hhmm(now_local())
        except Exception:
            pass
    return str(getattr(settings, "SCHEDULER_SYNC_END_TIME", "16:10") or "16:10")


def scheduler_max_daily_notional_usd() -> float:
    return round(
        max(1.0, float(getattr(settings, "SCHEDULER_MAX_DAILY_NOTIONAL_USD", 1000.0) or 1000.0)),
        2,
    )


def scheduler_per_order_notional() -> float:
    slots = max_execution_symbols()
    total_cap = scheduler_max_daily_notional_usd()
    cap_per_order = round(total_cap / max(1, slots), 2)
    configured = float(getattr(settings, "ALPACA_DEFAULT_TEST_NOTIONAL", cap_per_order) or cap_per_order)
    if configured <= 0:
        configured = cap_per_order
    return round(min(configured, cap_per_order), 2)


def sync_interval_seconds() -> int:
    minutes = max(1, int(getattr(settings, "SCHEDULER_SYNC_INTERVAL_MINUTES", 5) or 5))
    return minutes * 60


def preflight_interval_seconds() -> int:
    minutes = max(1, int(getattr(settings, "DEPLOYMENT_PREFLIGHT_MAX_AGE_MINUTES", 15) or 15))
    return max(60, min(minutes * 30, 900))


def fallback_to_default_universe() -> bool:
    return bool(getattr(settings, "SCHEDULER_FALLBACK_TO_DEFAULT_UNIVERSE", True))


def auto_cancel_enabled() -> bool:
    return bool(getattr(settings, "SCHEDULER_ENABLE_AUTO_CANCEL", True))


def auto_retry_enabled() -> bool:
    return bool(getattr(settings, "SCHEDULER_ENABLE_AUTO_RETRY", True))


def cancel_stale_after_minutes() -> int:
    return max(1, int(getattr(settings, "SCHEDULER_CANCEL_STALE_AFTER_MINUTES", 20) or 20))


def retry_delay_minutes() -> int:
    return max(0, int(getattr(settings, "SCHEDULER_RETRY_DELAY_MINUTES", 2) or 2))


def max_retry_attempts() -> int:
    return max(0, int(getattr(settings, "SCHEDULER_MAX_RETRY_ATTEMPTS", 1) or 1))


def failure_threshold() -> int:
    return max(1, int(getattr(settings, "SCHEDULER_FAILURE_THRESHOLD", 3) or 3))


def daily_digest_enabled(phase: str) -> bool:
    normalized = str(phase or "").strip().lower()
    if normalized == "preopen":
        return bool(getattr(settings, "QUANT_DAILY_DIGEST_PREOPEN_ENABLED", True))
    if normalized == "postclose":
        return bool(getattr(settings, "QUANT_DAILY_DIGEST_POSTCLOSE_ENABLED", True))
    return False


def weekly_digest_enabled() -> bool:
    return bool(getattr(settings, "QUANT_WEEKLY_DIGEST_ENABLED", True))


def weekly_digest_due_for_session(session_date: str) -> bool:
    raw = str(getattr(settings, "QUANT_WEEKLY_DIGEST_DAY", "friday") or "friday").strip().lower()
    day_map = {
        "monday": 0,
        "mon": 0,
        "tuesday": 1,
        "tue": 1,
        "wednesday": 2,
        "wed": 2,
        "thursday": 3,
        "thu": 3,
        "friday": 4,
        "fri": 4,
        "saturday": 5,
        "sat": 5,
        "sunday": 6,
        "sun": 6,
    }
    try:
        target = int(raw)
    except ValueError:
        target = day_map.get(raw, 4)
    try:
        return datetime.fromisoformat(str(session_date)[:10]).weekday() == max(0, min(target, 6))
    except ValueError:
        return now_local().weekday() == max(0, min(target, 6))


def paper_submit_circuit_breaker(state: dict[str, Any]) -> dict[str, Any]:
    breaker = dict((state.get("circuit_breakers", {}) or {}).get("paper_submit") or {})
    breaker.setdefault("enabled", False)
    breaker.setdefault("reason", "")
    return breaker


def set_paper_submit_circuit_breaker(
    service,
    state: dict[str, Any],
    *,
    enabled: bool,
    reason: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    breaker = {
        "enabled": bool(enabled),
        "reason": reason,
        "details": details or {},
        "updated_at": now_utc().isoformat(),
        "source": "quant_signal_scheduler",
    }
    state.setdefault("circuit_breakers", {})["paper_submit"] = breaker
    method = getattr(service, "set_paper_submit_circuit_breaker", None)
    if method is not None:
        try:
            breaker = method(enabled=enabled, reason=reason, details=details or {}, source="quant_signal_scheduler")
            state.setdefault("circuit_breakers", {})["paper_submit"] = breaker
        except Exception as exc:
            breaker["persist_warning"] = str(exc)
    return breaker


def update_failure_counter(
    service,
    state: dict[str, Any],
    *,
    key: str,
    failed: bool,
    detail: str = "",
) -> dict[str, Any]:
    counters = state.setdefault("failure_counters", {})
    counter = dict(counters.get(key) or {"count": 0})
    if failed:
        counter["count"] = int(counter.get("count") or 0) + 1
        counter["last_failed_at"] = now_utc().isoformat()
        counter["last_detail"] = detail
    else:
        counter["count"] = 0
        counter["last_recovered_at"] = now_utc().isoformat()
        counter["last_detail"] = detail
    counters[key] = counter
    if failed and int(counter.get("count") or 0) >= failure_threshold():
        set_paper_submit_circuit_breaker(
            service,
            state,
            enabled=True,
            reason=f"{key}_failure_threshold_reached",
            details={"failure_key": key, "count": counter.get("count"), "detail": detail},
        )
    return counter


def maybe_release_paper_submit_circuit_breaker(service, state: dict[str, Any]) -> dict[str, Any] | None:
    breaker = paper_submit_circuit_breaker(state)
    if not breaker.get("enabled"):
        return None
    counters = state.get("failure_counters", {}) or {}
    if any(int((counter or {}).get("count") or 0) > 0 for counter in counters.values()):
        return None
    return set_paper_submit_circuit_breaker(
        service,
        state,
        enabled=False,
        reason="failure_counters_recovered",
        details={"recovered_at": now_utc().isoformat()},
    )


def _mentions_any(payload: Any, tokens: tuple[str, ...]) -> bool:
    try:
        text = json.dumps(payload, ensure_ascii=False).lower()
    except Exception:
        text = str(payload).lower()
    return any(token in text for token in tokens)


def parse_timestamp(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def order_reference_time(record: dict[str, Any]) -> datetime | None:
    snapshot = dict(record.get("last_broker_snapshot") or {})
    payload = dict(record.get("submitted_payload") or {})
    for candidate in (
        snapshot.get("submitted_at"),
        snapshot.get("created_at"),
        payload.get("submitted_at"),
        payload.get("created_at"),
    ):
        parsed = parse_timestamp(candidate)
        if parsed is not None:
            return parsed
    for event in reversed(record.get("events", []) or []):
        parsed = parse_timestamp((event or {}).get("created_at"))
        if parsed is not None:
            return parsed
    return None


def minutes_since(reference: datetime | None) -> float | None:
    if reference is None:
        return None
    return max(0.0, (now_utc() - reference).total_seconds() / 60.0)


def _is_cancelable_state(service, state: str) -> bool:
    return bool(service._can_cancel_state(state))  # noqa: SLF001


def _is_retryable_state(service, state: str) -> bool:
    return bool(service._can_retry_state(state))  # noqa: SLF001


def manage_execution_cycle(service, state: dict[str, Any]) -> dict[str, Any]:
    session_status = scheduler_session_status(service)
    session_date = str(session_status.get("session_date") or now_local().date().isoformat())
    execution_id = str((state.get("execution", {}) or {}).get("execution_id") or "").strip()
    broker_id = getattr(settings, "QUANT_BROKER_DEFAULT", "alpaca")
    if not execution_id:
        return {
            "stage": "manage",
            "timestamp": now_local().isoformat(),
            "session_date": session_date,
            "calendar_id": session_status.get("calendar_id"),
            "market_clock_status": session_status.get("market_clock_status"),
            "skipped": True,
            "reason": "No execution_id available for order management.",
        }

    account_view = service.get_execution_account(broker=broker_id)
    market_clock = dict(account_view.get("market_clock") or {})
    if market_clock.get("is_open") is not True:
        return {
            "stage": "manage",
            "timestamp": now_local().isoformat(),
            "execution_id": execution_id,
            "session_date": session_date,
            "calendar_id": session_status.get("calendar_id"),
            "market_clock_status": session_status.get("market_clock_status"),
            "skipped": True,
            "reason": "Market is closed; order management stays in monitor-only mode.",
            "market_clock": market_clock,
            "warnings": account_view.get("warnings", []),
        }

    journal = service.get_execution_journal(execution_id)
    actions: list[dict[str, Any]] = []
    warnings: list[str] = []
    retry_budget = max_retry_attempts()

    for record in journal.get("records", []):
        state_name = str(record.get("current_state") or "").lower()
        order_id = str(record.get("order_id") or "").strip()
        if not order_id:
            continue
        age_minutes = minutes_since(order_reference_time(record))
        if auto_cancel_enabled() and _is_cancelable_state(service, state_name):
            if age_minutes is not None and age_minutes >= cancel_stale_after_minutes():
                canceled = service.cancel_execution_order(
                    order_id=order_id,
                    broker=broker_id,
                    execution_id=execution_id,
                )
                current_record = dict(canceled.get("journal_record") or {})
                actions.append(
                    {
                        "action": "cancel",
                        "order_id": order_id,
                        "symbol": current_record.get("symbol") or record.get("symbol"),
                        "age_minutes": round(age_minutes, 2),
                        "result_state": current_record.get("current_state"),
                    }
                )
                record = current_record or record
                state_name = str(record.get("current_state") or "").lower()

        if auto_retry_enabled() and _is_retryable_state(service, state_name):
            if int(record.get("retry_count", 0) or 0) >= retry_budget:
                warnings.append(f"{order_id} reached retry limit {retry_budget}.")
                continue
            age_minutes = minutes_since(order_reference_time(record))
            if age_minutes is None or age_minutes >= retry_delay_minutes():
                retried = service.retry_execution_order(
                    order_id=order_id,
                    broker=broker_id,
                    execution_id=execution_id,
                    per_order_notional=scheduler_per_order_notional(),
                    order_type="market",
                    time_in_force="day",
                    extended_hours=False,
                )
                current_record = dict(retried.get("journal_record") or {})
                actions.append(
                    {
                        "action": "retry",
                        "order_id": order_id,
                        "symbol": current_record.get("symbol") or record.get("symbol"),
                        "retry_count": current_record.get("retry_count"),
                        "result_state": current_record.get("current_state"),
                    }
                )

    result = {
        "stage": "manage",
        "timestamp": now_local().isoformat(),
        "execution_id": execution_id,
        "session_date": session_date,
        "calendar_id": session_status.get("calendar_id"),
        "market_clock_status": session_status.get("market_clock_status"),
        "market_clock": market_clock,
        "actions": actions,
        "action_count": len(actions),
        "warnings": warnings,
        "skipped": not actions,
    }
    return result


def update_heartbeat(state: dict[str, Any], *, stage: str, message: str) -> None:
    state["heartbeat_count"] = int(state.get("heartbeat_count") or 0) + 1
    payload = {
        "updated_at": now_utc().isoformat(),
        "local_time": now_local().isoformat(),
        "hostname": socket.gethostname(),
        "pid": os.getpid(),
        "status": "running",
        "stage": stage,
        "message": message,
        "execution_engine": scheduler_execution_engine(),
        "hybrid_workflow_enabled": hybrid_workflow_enabled(),
        "unattended_paper_mode": bool(getattr(settings, "UNATTENDED_PAPER_MODE", False)),
        "auto_submit": bool(getattr(settings, "SCHEDULER_AUTO_SUBMIT", False)),
        "synthetic_evidence_policy": str(getattr(settings, "SYNTHETIC_EVIDENCE_POLICY", "block") or "block"),
        "max_execution_symbols": max_execution_symbols(),
        "per_order_notional": scheduler_per_order_notional(),
        "heartbeat_count": state["heartbeat_count"],
        "last_trade_date": state.get("trade_date"),
        "last_session_date": state.get("session_date") or state.get("trade_date"),
        "calendar_id": getattr(settings, "TRADING_CALENDAR_ID", "XNYS"),
        "last_preopen_at": state.get("preopen", {}).get("ran_at"),
        "last_execution_at": state.get("execution", {}).get("ran_at"),
        "last_hybrid_workflow_at": state.get("hybrid_workflow", {}).get("ran_at"),
        "last_sync_at": state.get("sync", {}).get("ran_at"),
        "execution_id": state.get("execution", {}).get("execution_id"),
        "circuit_breakers": state.get("circuit_breakers", {}),
        "failure_counters": state.get("failure_counters", {}),
    }
    write_json(scheduler_heartbeat_path(), payload)


def run_preopen_cycle(service, state: dict[str, Any]) -> dict[str, Any]:
    skipped = skip_non_session("preopen", state, service)
    if skipped is not None:
        return skipped
    session_status = scheduler_session_status(service)
    universe = configured_universe(service)
    trade_date = str(session_status.get("session_date") or now_local().date().isoformat())
    research = service.run_research_pipeline(
        universe_symbols=universe,
        benchmark=service.default_benchmark,
        research_question="Generate pre-open momentum and ESG blended signals for the trading day.",
        capital_base=service.default_capital,
        horizon_days=10,
    )
    candidate_symbols = extract_actionable_symbols(research, max_execution_symbols())
    used_fallback_universe = False
    if not candidate_symbols and fallback_to_default_universe():
        full_universe = [item.symbol for item in service.get_default_universe()]
        if full_universe != universe:
            universe = full_universe
            research = service.run_research_pipeline(
                universe_symbols=universe,
                benchmark=service.default_benchmark,
                research_question="Fallback to the default quant universe for pre-open momentum selection.",
                capital_base=service.default_capital,
                horizon_days=10,
            )
            candidate_symbols = extract_actionable_symbols(research, max_execution_symbols())
            used_fallback_universe = True

    freshness = filter_fresh_symbols(
        service,
        candidate_symbols,
        session_date=trade_date,
        phase="preopen",
        session_status=session_status,
    )
    candidate_symbols = freshness["symbols"]

    validation = service.run_alpha_validation(
        strategy_name="Momentum MA Cross",
        benchmark=service.default_benchmark,
        universe_symbols=universe,
        capital_base=service.default_capital,
        in_sample_days=180,
        out_of_sample_days=45,
        walk_forward_windows=2,
    )

    snapshot = {
        "trade_date": trade_date,
        "session_date": trade_date,
        "calendar_id": session_status.get("calendar_id"),
        "market_clock_status": session_status.get("market_clock_status"),
        "next_session": session_status.get("next_session"),
        "ran_at": now_utc().isoformat(),
        "universe": universe,
        "research_id": research.get("research_id"),
        "validation_id": validation.get("validation_id"),
        "candidate_symbols": candidate_symbols,
        "candidate_count": len(candidate_symbols),
        "excluded_symbols": freshness["excluded_symbols"],
        "used_fallback_universe": used_fallback_universe,
        "signal_engine": getattr(settings, "SIGNAL_ENGINE_DEFAULT", "hybrid_momentum"),
        "top_signals": [
            {
                "symbol": signal.get("symbol"),
                "action": signal.get("action"),
                "expected_return": signal.get("expected_return"),
                "confidence": signal.get("confidence"),
            }
            for signal in research.get("signals", [])[:10]
        ],
        "validation_summary": {
            "validation_id": validation.get("validation_id"),
            "in_sample_sharpe": validation.get("in_sample_sharpe"),
            "out_of_sample_sharpe": validation.get("out_of_sample_sharpe"),
            "robustness_score": validation.get("robustness_score"),
        },
    }
    state["trade_date"] = trade_date
    state["session_date"] = trade_date
    state["preopen"] = snapshot
    state.setdefault("execution", {})
    state.setdefault("sync", {})
    write_json(scheduler_state_path(), state)
    update_heartbeat(state, stage="preopen", message="Pre-open research cycle completed.")
    result = {"stage": "preopen", "timestamp": now_local().isoformat(), **snapshot}
    record_scheduler_event(service, stage="preopen", status="completed", payload=result)
    result["daily_digest"] = run_daily_digest_cycle(service, state, phase="preopen")
    return result


def run_daily_digest_cycle(service, state: dict[str, Any], *, phase: str = "postclose") -> dict[str, Any]:
    started_at = time.perf_counter()
    normalized = str(phase or "postclose").strip().lower()
    if normalized not in {"preopen", "postclose"}:
        normalized = "postclose"
    session_status = scheduler_session_status(service)
    session_date = str(session_status.get("session_date") or now_local().date().isoformat())
    if not daily_digest_enabled(normalized):
        result = {
            "stage": "daily_digest",
            "phase": normalized,
            "session_date": session_date,
            "skipped": True,
            "reason": "daily_digest_disabled",
        }
        finalize_stage_result(result, started_at=started_at)
        record_scheduler_event(service, stage=f"daily_digest_{normalized}", status="skipped", payload=result)
        return result
    phase_state = state.setdefault("daily_digests", {}).setdefault(session_date, {}).get(normalized, {})
    if phase_state.get("sent_at"):
        result = {
            "stage": "daily_digest",
            "phase": normalized,
            "session_date": session_date,
            "skipped": True,
            "reason": "daily_digest_already_sent_for_session",
            "digest_id": phase_state.get("digest_id"),
        }
        finalize_stage_result(result, started_at=started_at)
        record_scheduler_event(service, stage=f"daily_digest_{normalized}", status="skipped", payload=result)
        return result
    method = getattr(service, "send_quant_daily_digest", None)
    if method is None:
        result = {
            "stage": "daily_digest",
            "phase": normalized,
            "session_date": session_date,
            "skipped": True,
            "reason": "send_quant_daily_digest_unavailable",
        }
        finalize_stage_result(result, started_at=started_at)
        record_scheduler_event(service, stage=f"daily_digest_{normalized}", status="skipped", payload=result)
        return result
    try:
        payload = method(phase=normalized, session_date=session_date)
        delivery = payload.get("delivery") or {}
        result = {
            "stage": "daily_digest",
            "phase": normalized,
            "session_date": session_date,
            "digest_id": payload.get("digest_id"),
            "sent_count": delivery.get("sent_count", 0),
            "failed_count": delivery.get("failed_count", 0),
            "channels": delivery.get("channels", []),
            "storage": payload.get("storage"),
        }
        finalize_stage_result(result, started_at=started_at)
        state.setdefault("daily_digests", {}).setdefault(session_date, {})[normalized] = {
            "sent_at": now_utc().isoformat(),
            **result,
        }
        write_json(scheduler_state_path(), state)
        update_heartbeat(state, stage=f"daily_digest_{normalized}", message=f"{normalized} digest sent.")
        record_scheduler_event(service, stage=f"daily_digest_{normalized}", status="completed", payload=result)
        return result
    except Exception as exc:
        result = {
            "stage": "daily_digest",
            "phase": normalized,
            "session_date": session_date,
            "status": "failed",
            "error": str(exc),
        }
        finalize_stage_result(result, started_at=started_at)
        record_scheduler_event(service, stage=f"daily_digest_{normalized}", status="failed", payload=result)
        return result


def run_weekly_digest_cycle(service, state: dict[str, Any]) -> dict[str, Any]:
    started_at = time.perf_counter()
    session_status = scheduler_session_status(service)
    session_date = str(session_status.get("session_date") or now_local().date().isoformat())[:10]
    if not weekly_digest_enabled():
        result = {
            "stage": "weekly_digest",
            "session_date": session_date,
            "skipped": True,
            "reason": "weekly_digest_disabled",
        }
        finalize_stage_result(result, started_at=started_at)
        record_scheduler_event(service, stage="weekly_digest", status="skipped", payload=result)
        return result
    if not weekly_digest_due_for_session(session_date):
        result = {
            "stage": "weekly_digest",
            "session_date": session_date,
            "skipped": True,
            "reason": "weekly_digest_not_due_for_session",
        }
        finalize_stage_result(result, started_at=started_at)
        record_scheduler_event(service, stage="weekly_digest", status="skipped", payload=result)
        return result
    week_key = datetime.fromisoformat(session_date).strftime("%G-W%V")
    sent_state = state.setdefault("weekly_digests", {}).get(week_key, {})
    if sent_state.get("sent_at"):
        result = {
            "stage": "weekly_digest",
            "session_date": session_date,
            "week_key": week_key,
            "skipped": True,
            "reason": "weekly_digest_already_sent_for_week",
            "digest_id": sent_state.get("digest_id"),
        }
        finalize_stage_result(result, started_at=started_at)
        record_scheduler_event(service, stage="weekly_digest", status="skipped", payload=result)
        return result
    method = getattr(service, "send_quant_weekly_digest", None)
    if method is None:
        result = {
            "stage": "weekly_digest",
            "session_date": session_date,
            "week_key": week_key,
            "skipped": True,
            "reason": "send_quant_weekly_digest_unavailable",
        }
        finalize_stage_result(result, started_at=started_at)
        record_scheduler_event(service, stage="weekly_digest", status="skipped", payload=result)
        return result
    try:
        payload = method(
            session_date=session_date,
            window_days=int(getattr(settings, "QUANT_WEEKLY_DIGEST_WINDOW_DAYS", 7) or 7),
        )
        delivery = payload.get("delivery") or {}
        result = {
            "stage": "weekly_digest",
            "session_date": session_date,
            "week_key": week_key,
            "digest_id": payload.get("digest_id"),
            "sent_count": delivery.get("sent_count", 0),
            "failed_count": delivery.get("failed_count", 0),
            "channels": delivery.get("channels", []),
            "storage": payload.get("storage"),
        }
        finalize_stage_result(result, started_at=started_at)
        state.setdefault("weekly_digests", {})[week_key] = {
            "sent_at": now_utc().isoformat(),
            **result,
        }
        write_json(scheduler_state_path(), state)
        update_heartbeat(state, stage="weekly_digest", message="Weekly digest sent.")
        record_scheduler_event(service, stage="weekly_digest", status="completed", payload=result)
        return result
    except Exception as exc:
        result = {
            "stage": "weekly_digest",
            "session_date": session_date,
            "status": "failed",
            "error": str(exc),
        }
        finalize_stage_result(result, started_at=started_at)
        record_scheduler_event(service, stage="weekly_digest", status="failed", payload=result)
        return result


def _execution_universe_from_state(service, state: dict[str, Any]) -> list[str]:
    trade_date = scheduler_session_date(service)
    if state.get("trade_date") == trade_date or (state.get("preopen", {}) or {}).get("session_date") == trade_date:
        candidates = [
            str(item).upper()
            for item in (state.get("preopen", {}) or {}).get("candidate_symbols", [])
            if str(item).strip()
        ]
        if candidates:
            return candidates
    return configured_universe(service)


def run_execution_cycle(service, state: dict[str, Any]) -> dict[str, Any]:
    skipped = skip_non_session("execution", state, service)
    if skipped is not None:
        return skipped
    session_status = scheduler_session_status(service)
    trade_date = str(session_status.get("session_date") or now_local().date().isoformat())
    if (state.get("hybrid_workflow", {}) or {}).get("session_date", (state.get("hybrid_workflow", {}) or {}).get("trade_date")) == trade_date:
        result = {
            "stage": "execution",
            "timestamp": now_local().isoformat(),
            "trade_date": trade_date,
            "session_date": trade_date,
            "calendar_id": session_status.get("calendar_id"),
            "market_clock_status": session_status.get("market_clock_status"),
            "next_session": session_status.get("next_session"),
            "skipped": True,
            "reason": "hybrid_workflow_already_ran_for_trade_date",
            "skip_reason": "hybrid_workflow_already_ran_for_session",
            "execution_engine": scheduler_execution_engine(),
            "workflow_id": (state.get("hybrid_workflow", {}) or {}).get("workflow_id"),
            "execution_id": (state.get("hybrid_workflow", {}) or {}).get("execution_id"),
        }
        update_heartbeat(state, stage="execution", message=result["reason"])
        record_scheduler_event(service, stage="execution", status="skipped", payload=result)
        return result
    universe = _execution_universe_from_state(service, state)
    freshness = filter_fresh_symbols(
        service,
        universe,
        session_date=trade_date,
        phase="submit",
        session_status=session_status,
    )
    universe = freshness["symbols"]
    if not universe:
        result = {
            "stage": "execution",
            "timestamp": now_local().isoformat(),
            "trade_date": trade_date,
            "session_date": trade_date,
            "calendar_id": session_status.get("calendar_id"),
            "skipped": True,
            "reason": "all_candidate_symbols_stale",
            "excluded_symbols": freshness["excluded_symbols"],
        }
        update_heartbeat(state, stage="execution", message=result["reason"])
        record_scheduler_event(service, stage="execution", status="skipped", payload=result)
        return result
    max_orders = max_execution_symbols()
    per_order_notional = scheduler_per_order_notional()
    payload = service.create_execution_plan(
        benchmark=service.default_benchmark,
        capital_base=service.default_capital,
        universe_symbols=universe,
        broker=getattr(settings, "QUANT_BROKER_DEFAULT", "alpaca"),
        mode="paper",
        submit_orders=bool(getattr(settings, "SCHEDULER_AUTO_SUBMIT", False)),
        max_orders=max_orders,
        per_order_notional=per_order_notional,
        order_type="market",
        time_in_force="day",
        extended_hours=False,
        strategy_id="legacy_execution_plan",
    )
    snapshot = {
        "trade_date": trade_date,
        "session_date": trade_date,
        "calendar_id": session_status.get("calendar_id"),
        "market_clock_status": session_status.get("market_clock_status"),
        "next_session": session_status.get("next_session"),
        "ran_at": now_utc().isoformat(),
        "universe": universe,
        "excluded_symbols": freshness["excluded_symbols"],
        "execution_id": payload.get("execution_id"),
        "submitted": bool(payload.get("submitted")),
        "broker_status": payload.get("broker_status"),
        "auto_submit_enabled": bool(getattr(settings, "SCHEDULER_AUTO_SUBMIT", False)),
        "max_orders": max_orders,
        "per_order_notional": per_order_notional,
        "max_daily_notional_usd": scheduler_max_daily_notional_usd(),
        "ready": bool(payload.get("ready")),
        "warnings": payload.get("warnings", []),
        "journal_state": payload.get("state_machine", {}).get("state"),
        "orders": [
            {
                "symbol": order.get("symbol"),
                "status": order.get("status"),
                "client_order_id": order.get("client_order_id"),
                "broker_order_id": order.get("broker_order_id"),
            }
            for order in payload.get("orders", [])
        ],
    }
    state["trade_date"] = snapshot["trade_date"]
    state["session_date"] = snapshot["session_date"]
    state["execution"] = snapshot
    write_json(scheduler_state_path(), state)
    update_heartbeat(state, stage="execution", message="Execution cycle completed.")
    result = {"stage": "execution", "timestamp": now_local().isoformat(), **snapshot}
    record_scheduler_event(service, stage="execution", status="completed", payload=result)
    return result


def run_hybrid_workflow_cycle(service, state: dict[str, Any]) -> dict[str, Any]:
    skipped = skip_non_session("hybrid_workflow", state, service)
    if skipped is not None:
        return skipped
    session_status = scheduler_session_status(service)
    trade_date = str(session_status.get("session_date") or now_local().date().isoformat())
    existing_hybrid = state.get("hybrid_workflow", {}) or {}
    if existing_hybrid.get("session_date", existing_hybrid.get("trade_date")) == trade_date:
        result = {
            "stage": "hybrid_workflow",
            "timestamp": now_local().isoformat(),
            "trade_date": trade_date,
            "session_date": trade_date,
            "calendar_id": session_status.get("calendar_id"),
            "market_clock_status": session_status.get("market_clock_status"),
            "next_session": session_status.get("next_session"),
            "skipped": True,
            "reason": "hybrid_workflow_already_ran_for_trade_date",
            "skip_reason": "hybrid_workflow_already_ran_for_session",
            "workflow_id": existing_hybrid.get("workflow_id"),
            "execution_id": existing_hybrid.get("execution_id"),
        }
        update_heartbeat(state, stage="hybrid_workflow", message=result["reason"])
        record_scheduler_event(service, stage="hybrid_workflow", status="skipped", payload=result)
        return result

    existing_execution = state.get("execution", {}) or {}
    if existing_execution.get("session_date", existing_execution.get("trade_date")) == trade_date and existing_execution.get("execution_id"):
        result = {
            "stage": "hybrid_workflow",
            "timestamp": now_local().isoformat(),
            "trade_date": trade_date,
            "session_date": trade_date,
            "calendar_id": session_status.get("calendar_id"),
            "market_clock_status": session_status.get("market_clock_status"),
            "next_session": session_status.get("next_session"),
            "skipped": True,
            "reason": "execution_cycle_already_ran_for_trade_date",
            "skip_reason": "execution_cycle_already_ran_for_session",
            "execution_id": existing_execution.get("execution_id"),
        }
        update_heartbeat(state, stage="hybrid_workflow", message=result["reason"])
        record_scheduler_event(service, stage="hybrid_workflow", status="skipped", payload=result)
        return result

    universe = _execution_universe_from_state(service, state)
    freshness = filter_fresh_symbols(
        service,
        universe,
        session_date=trade_date,
        phase="submit",
        session_status=session_status,
    )
    universe = freshness["symbols"]
    if not universe:
        result = {
            "stage": "hybrid_workflow",
            "timestamp": now_local().isoformat(),
            "trade_date": trade_date,
            "session_date": trade_date,
            "calendar_id": session_status.get("calendar_id"),
            "skipped": True,
            "reason": "all_candidate_symbols_stale",
            "excluded_symbols": freshness["excluded_symbols"],
        }
        update_heartbeat(state, stage="hybrid_workflow", message=result["reason"])
        record_scheduler_event(service, stage="hybrid_workflow", status="skipped", payload=result)
        return result
    max_orders = max_execution_symbols()
    per_order_notional = scheduler_per_order_notional()
    breaker = paper_submit_circuit_breaker(state)
    submit_orders = not bool(breaker.get("enabled"))
    payload = service.run_hybrid_paper_strategy_workflow(
        universe_symbols=universe,
        benchmark=service.default_benchmark,
        capital_base=service.default_capital,
        submit_orders=submit_orders,
        mode="paper",
        broker=getattr(settings, "QUANT_BROKER_DEFAULT", "alpaca"),
        max_orders=max_orders,
        per_order_notional=per_order_notional,
        allow_synthetic_execution=False,
        force_refresh=False,
    )
    snapshot = {
        "trade_date": trade_date,
        "session_date": trade_date,
        "calendar_id": session_status.get("calendar_id"),
        "market_clock_status": session_status.get("market_clock_status"),
        "next_session": session_status.get("next_session"),
        "ran_at": now_utc().isoformat(),
        "execution_engine": "hybrid_paper_workflow",
        "universe": universe,
        "excluded_symbols": freshness["excluded_symbols"],
        "submit_orders_requested": submit_orders,
        "paper_submit_circuit_breaker": breaker,
        "workflow_id": payload.get("workflow_id"),
        "workflow_status": payload.get("status"),
        "execution_id": payload.get("execution_id"),
        "submitted_count": int(payload.get("submitted_count") or 0),
        "blockers": payload.get("blockers", []),
        "warnings": payload.get("warnings", []),
        "next_actions": payload.get("next_actions", []),
        "paper_performance_snapshot_id": payload.get("paper_performance_snapshot_id"),
        "outcome_summary": payload.get("outcome_summary", {}),
        "max_orders": max_orders,
        "per_order_notional": per_order_notional,
    }
    state["trade_date"] = trade_date
    state["session_date"] = trade_date
    state["hybrid_workflow"] = snapshot
    state["execution"] = {
        "trade_date": trade_date,
        "session_date": trade_date,
        "ran_at": snapshot["ran_at"],
        "source": "hybrid_paper_workflow",
        "execution_id": payload.get("execution_id"),
        "submitted": int(payload.get("submitted_count") or 0) > 0,
        "broker_status": (payload.get("steps", {}).get("paper_execution") or {}).get("broker_status"),
        "ready": payload.get("status") in {"submitted", "planned"},
        "warnings": payload.get("warnings", []),
        "orders": payload.get("order_summary", []),
    }
    write_json(scheduler_state_path(), state)
    update_heartbeat(state, stage="hybrid_workflow", message="Hybrid paper workflow cycle completed.")
    result = {"stage": "hybrid_workflow", "timestamp": now_local().isoformat(), **snapshot}
    blockers_and_warnings = {"blockers": snapshot.get("blockers", []), "warnings": snapshot.get("warnings", [])}
    update_failure_counter(
        service,
        state,
        key="workflow_failure",
        failed=str(snapshot.get("workflow_status") or "").lower() in {"blocked", "failed", "error"},
        detail=str(snapshot.get("workflow_status") or ""),
    )
    update_failure_counter(
        service,
        state,
        key="rl_checkpoint_missing",
        failed=_mentions_any(blockers_and_warnings, ("rl checkpoint", "checkpoint artifact", "train_or_sync_rl_checkpoint")),
        detail="RL checkpoint missing in workflow evidence.",
    )
    update_failure_counter(
        service,
        state,
        key="broker_submit_error",
        failed=submit_orders and _mentions_any(blockers_and_warnings, ("alpaca", "broker", "account", "paper credentials")),
        detail="Broker submit gate reported a blocker.",
    )
    update_failure_counter(
        service,
        state,
        key="market_data_stale",
        failed=_mentions_any(blockers_and_warnings, ("stale", "market data", "synthetic")),
        detail="Workflow reported stale or ineligible market data.",
    )
    maybe_release_paper_submit_circuit_breaker(service, state)
    write_json(scheduler_state_path(), state)
    record_scheduler_event(service, stage="hybrid_workflow", status=str(payload.get("status") or "completed"), payload=result)
    return result


def run_post_sync_automation(
    service,
    state: dict[str, Any],
    *,
    trade_date: str,
    execution_id: str,
    include_backfill: bool = False,
) -> dict[str, Any]:
    started_at = time.perf_counter()
    result: dict[str, Any] = {"ran": [], "warnings": []}

    def call(name: str, method_name: str, **kwargs: Any) -> None:
        method = getattr(service, method_name, None)
        if method is None:
            result["warnings"].append(f"{method_name}_unavailable")
            return
        try:
            payload = method(**kwargs)
            result["ran"].append(name)
            result[name] = payload
        except Exception as exc:
            result["warnings"].append(f"{name}_failed:{exc}")

    call("outcome_settlement", "settle_paper_outcomes", limit=200)
    call("alpaca_paper_reconcile", "reconcile_alpaca_paper_orders", session_date=trade_date)
    if include_backfill:
        call(
            "paper_performance_backfill",
            "backfill_paper_performance",
            days=int(getattr(settings, "PAPER_EVIDENCE_BACKFILL_DAYS", 120) or 120),
            broker=getattr(settings, "QUANT_BROKER_DEFAULT", "alpaca"),
            mode="paper",
            force_refresh=False,
        )
    if execution_id:
        call(
            "paper_performance_snapshot",
            "capture_paper_performance_snapshot",
            execution_id=execution_id,
            broker=getattr(settings, "QUANT_BROKER_DEFAULT", "alpaca"),
            mode="paper",
            force_refresh=False,
        )
    call("promotion_evaluation", "evaluate_promotion", window_days=90, persist=True)
    call("digest_retry", "retry_failed_daily_digest_deliveries", limit=20)
    call("storage_backup", "backup_quant_storage", session_date=trade_date)
    call("observability_evaluation", "evaluate_paper_workflow_observability", window_days=30)
    result["trade_date"] = trade_date
    result["execution_id"] = execution_id
    finalize_stage_result(result, started_at=started_at)
    state.setdefault("automation", {})[trade_date] = {
        "ran_at": now_utc().isoformat(),
        "execution_id": execution_id,
        "ran": result["ran"],
        "warnings": result["warnings"],
    }
    return result


def run_observability_cycle(service, state: dict[str, Any]) -> dict[str, Any]:
    started_at = time.perf_counter()
    method = getattr(service, "evaluate_paper_workflow_observability", None)
    if method is None:
        result = {
            "stage": "observability",
            "timestamp": now_local().isoformat(),
            "skipped": True,
            "reason": "evaluate_paper_workflow_observability_unavailable",
        }
    else:
        payload = method(window_days=30)
        result = {
            "stage": "observability",
            "timestamp": now_local().isoformat(),
            "alert_count": (payload.get("summary") or {}).get("alert_count", 0),
            "workflow_count": (payload.get("summary") or {}).get("workflow_count", 0),
            "payload": payload,
        }
    state.setdefault("observability", {})
    finalize_stage_result(result, started_at=started_at)
    state["observability"].update({"ran_at": now_utc().isoformat(), **result})
    write_json(scheduler_state_path(), state)
    update_heartbeat(state, stage="observability", message="Paper workflow observability evaluated.")
    record_scheduler_event(service, stage="observability", status="completed" if not result.get("skipped") else "skipped", payload=result)
    return result


def run_shadow_retrain_cycle(service, state: dict[str, Any]) -> dict[str, Any]:
    started_at = time.perf_counter()
    method = getattr(service, "run_shadow_retrain", None)
    if method is None:
        result = {
            "stage": "shadow_retrain",
            "timestamp": now_local().isoformat(),
            "skipped": True,
            "reason": "run_shadow_retrain_unavailable",
        }
    else:
        payload = method(model_key="rl_checkpoint", force=False)
        result = {
            "stage": "shadow_retrain",
            "timestamp": now_local().isoformat(),
            "run_id": payload.get("run_id"),
            "status": payload.get("status"),
            "blockers": payload.get("blockers", []),
            "payload": payload,
        }
    finalize_stage_result(result, started_at=started_at)
    state.setdefault("shadow_retrain", {})["latest"] = {"ran_at": now_utc().isoformat(), **result}
    write_json(scheduler_state_path(), state)
    update_heartbeat(state, stage="shadow_retrain", message="Shadow retrain cycle evaluated.")
    record_scheduler_event(service, stage="shadow_retrain", status=str(result.get("status") or "skipped"), payload=result)
    return result


def run_preflight_cycle(service, state: dict[str, Any]) -> dict[str, Any]:
    started_at = time.perf_counter()
    method = getattr(service, "evaluate_deployment_preflight", None)
    if method is None:
        result = {
            "stage": "preflight",
            "timestamp": now_local().isoformat(),
            "skipped": True,
            "reason": "evaluate_deployment_preflight_unavailable",
        }
    else:
        payload = method(profile="paper_cloud")
        result = {
            "stage": "preflight",
            "timestamp": now_local().isoformat(),
            "ready": bool(payload.get("ready")),
            "blockers": payload.get("blockers", []),
            "warnings": payload.get("warnings", []),
            "payload": payload,
        }
    finalize_stage_result(result, started_at=started_at)
    state["preflight"] = {"ran_at": now_utc().isoformat(), **result}
    write_json(scheduler_state_path(), state)
    update_heartbeat(state, stage="preflight", message="Paper cloud preflight evaluated.")
    record_scheduler_event(service, stage="preflight", status="completed" if not result.get("skipped") else "skipped", payload=result)
    return result


def run_recovery_cycle(service, state: dict[str, Any]) -> dict[str, Any]:
    started_at = time.perf_counter()
    session_status = scheduler_session_status(service)
    trade_date = str(session_status.get("session_date") or now_local().date().isoformat())
    execution_id = str(
        (state.get("hybrid_workflow", {}) or {}).get("execution_id")
        or (state.get("execution", {}) or {}).get("execution_id")
        or ""
    ).strip()
    required = {
        "outcome_settlement",
        "alpaca_paper_reconcile",
        "paper_performance_backfill",
        "promotion_evaluation",
        "digest_retry",
        "storage_backup",
        "observability_evaluation",
    }
    if execution_id:
        required.add("paper_performance_snapshot")
    current = (state.get("automation", {}) or {}).get(trade_date, {})
    already_ran = set(current.get("ran") or [])
    if required.issubset(already_ran):
        result = {
            "stage": "recovery",
            "timestamp": now_local().isoformat(),
            "session_date": trade_date,
            "execution_id": execution_id,
            "skipped": True,
            "reason": "post_sync_automation_already_complete",
        }
    else:
        automation = run_post_sync_automation(
            service,
            state,
            trade_date=trade_date,
            execution_id=execution_id,
            include_backfill=True,
        )
        result = {
            "stage": "recovery",
            "timestamp": now_local().isoformat(),
            "session_date": trade_date,
            "execution_id": execution_id,
            "recovered": sorted(required.intersection(set(automation.get("ran") or []))),
            "automation": automation,
        }
        if not execution_id:
            result["warning"] = "missing_execution_id_non_submit_recovery_only"
    finalize_stage_result(result, started_at=started_at)
    state.setdefault("recovery", {})[trade_date] = {
        "ran_at": now_utc().isoformat(),
        **result,
    }
    write_json(scheduler_state_path(), state)
    update_heartbeat(state, stage="recovery", message=str(result.get("reason") or "Recovered missing post-sync automation."))
    record_scheduler_event(service, stage="recovery", status="completed" if not result.get("skipped") else "skipped", payload=result)
    return result


def run_sync_cycle(service, state: dict[str, Any]) -> dict[str, Any]:
    skipped = skip_non_session("sync", state, service)
    if skipped is not None:
        return skipped
    session_status = scheduler_session_status(service)
    trade_date = str(session_status.get("session_date") or now_local().date().isoformat())
    execution_id = str(
        (state.get("hybrid_workflow", {}) or {}).get("execution_id")
        or (state.get("execution", {}) or {}).get("execution_id")
        or ""
    ).strip()
    if not execution_id:
        result = {
            "stage": "sync",
            "timestamp": now_local().isoformat(),
            "skipped": True,
            "reason": "No execution_id available for intraday sync.",
            "skip_reason": "missing_execution_id",
            "session_date": trade_date,
            "calendar_id": session_status.get("calendar_id"),
            "market_clock_status": session_status.get("market_clock_status"),
            "next_session": session_status.get("next_session"),
        }
        state["trade_date"] = trade_date
        state["session_date"] = trade_date
        state["sync"] = {"trade_date": trade_date, "session_date": trade_date, "ran_at": now_utc().isoformat(), **result}
        write_json(scheduler_state_path(), state)
        update_heartbeat(state, stage="sync", message=result["reason"])
        record_scheduler_event(service, stage="sync", status="skipped", payload=result)
        return result

    payload = service.sync_execution_journal(
        execution_id=execution_id,
        broker=getattr(settings, "QUANT_BROKER_DEFAULT", "alpaca"),
    )
    management = manage_execution_cycle(service, state)
    if management.get("action_count", 0) > 0:
        payload = service.sync_execution_journal(
            execution_id=execution_id,
            broker=getattr(settings, "QUANT_BROKER_DEFAULT", "alpaca"),
        )
    snapshot = {
        "trade_date": trade_date,
        "session_date": trade_date,
        "calendar_id": session_status.get("calendar_id"),
        "market_clock_status": session_status.get("market_clock_status"),
        "next_session": session_status.get("next_session"),
        "ran_at": now_utc().isoformat(),
        "execution_id": execution_id,
        "records_synced": payload.get("records_synced", 0),
        "state_transitions": payload.get("state_transitions", 0),
        "journal_state": payload.get("state_machine", {}).get("state"),
        "cancelable_order_ids": payload.get("cancelable_order_ids", []),
        "retryable_order_ids": payload.get("retryable_order_ids", []),
        "warnings": payload.get("warnings", []),
        "management": management,
    }
    state["sync"] = snapshot
    state["trade_date"] = trade_date
    state["session_date"] = trade_date
    write_json(scheduler_state_path(), state)
    update_heartbeat(state, stage="sync", message="Intraday journal sync completed.")
    result = {"stage": "sync", "timestamp": now_local().isoformat(), **snapshot}
    automation = run_post_sync_automation(service, state, trade_date=trade_date, execution_id=execution_id)
    result["automation"] = automation
    update_failure_counter(
        service,
        state,
        key="broker_sync_error",
        failed=bool(snapshot.get("warnings")),
        detail="; ".join(str(item) for item in snapshot.get("warnings", [])[:3]),
    )
    update_failure_counter(
        service,
        state,
        key="post_sync_automation_failure",
        failed=bool(automation.get("warnings")),
        detail="; ".join(str(item) for item in automation.get("warnings", [])[:3]),
    )
    performance_snapshot = automation.get("paper_performance_snapshot") or {}
    update_failure_counter(
        service,
        state,
        key="equity_anomaly",
        failed=_mentions_any(performance_snapshot.get("warnings", []), ("equity", "anomaly")),
        detail="Paper performance snapshot reported equity anomaly.",
    )
    maybe_release_paper_submit_circuit_breaker(service, state)
    write_json(scheduler_state_path(), state)
    update_heartbeat(state, stage="post_sync_automation", message="Post-sync paper automation completed.")
    record_scheduler_event(service, stage="sync", status="completed", payload=result)
    return result


def stale_lock_seconds() -> int:
    minutes = max(15, int(getattr(settings, "SCHEDULER_LOCK_STALE_MINUTES", 240) or 240))
    return minutes * 60


def worker_lock_is_active(lock_path: Path) -> bool:
    owner = load_json(lock_path, default={})
    owner_host = str(owner.get("hostname") or "").strip()
    if owner_host and owner_host != socket.gethostname():
        return False
    try:
        owner_pid = int(owner.get("pid") or 0)
    except (TypeError, ValueError):
        return False
    if owner_pid <= 0:
        return False
    try:
        os.kill(owner_pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False


@contextmanager
def worker_lock(ignore_lock: bool = False) -> Iterator[None]:
    lock_path = scheduler_lock_path()
    if ignore_lock:
        yield
        return

    try:
        descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {"pid": os.getpid(), "hostname": socket.gethostname(), "created_at": now_utc().isoformat()},
                    ensure_ascii=False,
                )
            )
    except FileExistsError:
        age = time.time() - lock_path.stat().st_mtime
        if age > stale_lock_seconds() or not worker_lock_is_active(lock_path):
            lock_path.unlink(missing_ok=True)
            with worker_lock(ignore_lock=False):
                yield
            return
        raise SystemExit(f"Scheduler lock already exists at {lock_path}. Use --ignore-lock only when you know the worker is not running.")

    try:
        yield
    finally:
        lock_path.unlink(missing_ok=True)


def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def run_loop(service, poll_seconds: int) -> None:
    state = load_json(scheduler_state_path(), default={"trade_date": ""})
    last_sync_at = 0.0
    last_preflight_at = 0.0
    while True:
        current = now_local()
        session_status = scheduler_session_status(service)
        current_date = str(session_status.get("session_date") or current.date().isoformat())
        current_hhmm = current.strftime("%H:%M")
        update_heartbeat(state, stage="idle", message="Scheduler heartbeat is healthy.")

        if time.time() - last_preflight_at >= preflight_interval_seconds():
            result = run_preflight_cycle(service, state)
            emit(result)
            state = load_json(scheduler_state_path(), default=state)
            last_preflight_at = time.time()

        if (not require_trading_session()) or session_status.get("is_session"):
            preopen_state = state.get("preopen", {}) or {}
            if current_date != preopen_state.get("session_date", preopen_state.get("trade_date")) and due(current_hhmm, getattr(settings, "SCHEDULER_PREOPEN_SIGNAL_TIME", "09:00")):
                result = run_preopen_cycle(service, state)
                emit(result)
                state = load_json(scheduler_state_path(), default=state)

            execution_state = state.get("execution", {}) or {}
            hybrid_state = state.get("hybrid_workflow", {}) or {}
            if hybrid_workflow_enabled() and current_date != hybrid_state.get("session_date", hybrid_state.get("trade_date")) and due(current_hhmm, hybrid_workflow_time()):
                result = run_hybrid_workflow_cycle(service, state)
                emit(result)
                state = load_json(scheduler_state_path(), default=state)
            elif (not hybrid_workflow_enabled()) and current_date != execution_state.get("session_date", execution_state.get("trade_date")) and due(current_hhmm, getattr(settings, "SCHEDULER_EXECUTION_TIME", "09:31")):
                result = run_execution_cycle(service, state)
                emit(result)
                state = load_json(scheduler_state_path(), default=state)

            if (
                state.get("trade_date") == current_date
                and state.get("execution", {}).get("execution_id")
                and between(
                    current_hhmm,
                    getattr(settings, "SCHEDULER_EXECUTION_TIME", "09:31"),
                    sync_end_time_for_today(),
                )
                and time.time() - last_sync_at >= sync_interval_seconds()
            ):
                result = run_sync_cycle(service, state)
                emit(result)
                state = load_json(scheduler_state_path(), default=state)
                last_sync_at = time.time()

            recovery_state = (state.get("recovery", {}) or {}).get(current_date, {})
            if (
                state.get("trade_date") == current_date
                and state.get("execution", {}).get("execution_id")
                and not recovery_state.get("ran_at")
                and due(current_hhmm, hybrid_workflow_time())
            ):
                result = run_recovery_cycle(service, state)
                emit(result)
                state = load_json(scheduler_state_path(), default=state)

            digest_state = (state.get("daily_digests", {}) or {}).get(current_date, {})
            if (
                state.get("trade_date") == current_date
                and state.get("execution", {}).get("execution_id")
                and not (digest_state.get("postclose") or {}).get("sent_at")
                and due(current_hhmm, sync_end_time_for_today())
            ):
                result = run_daily_digest_cycle(service, state, phase="postclose")
                emit(result)
                state = load_json(scheduler_state_path(), default=state)

            week_key = now_local().strftime("%G-W%V")
            weekly_state = (state.get("weekly_digests", {}) or {}).get(week_key, {})
            if (
                state.get("trade_date") == current_date
                and not weekly_state.get("sent_at")
                and due(current_hhmm, sync_end_time_for_today())
                and weekly_digest_due_for_session(current_date)
            ):
                result = run_weekly_digest_cycle(service, state)
                emit(result)
                state = load_json(scheduler_state_path(), default=state)

        time.sleep(max(5, int(poll_seconds)))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once-preopen", action="store_true")
    parser.add_argument("--once-execute", action="store_true")
    parser.add_argument("--once-hybrid-workflow", action="store_true")
    parser.add_argument("--once-sync", action="store_true")
    parser.add_argument("--once-recover", action="store_true")
    parser.add_argument("--once-preflight", action="store_true")
    parser.add_argument("--once-observability", action="store_true")
    parser.add_argument("--once-shadow-retrain", action="store_true")
    parser.add_argument("--once-digest", action="store_true")
    parser.add_argument("--once-weekly-digest", action="store_true")
    parser.add_argument("--digest-phase", choices=["preopen", "postclose"], default="postclose")
    parser.add_argument("--print-state", action="store_true")
    parser.add_argument("--poll-seconds", type=int, default=20)
    parser.add_argument("--ignore-lock", action="store_true")
    args = parser.parse_args()

    state = load_json(scheduler_state_path(), default={"trade_date": ""})
    if args.print_state:
        emit(state)
        return 0

    service = get_quant_system()
    with worker_lock(ignore_lock=args.ignore_lock):
        if args.once_preopen:
            emit(run_preopen_cycle(service, state))
            return 0
        if args.once_execute:
            emit(run_execution_cycle(service, state))
            return 0
        if args.once_hybrid_workflow:
            emit(run_hybrid_workflow_cycle(service, state))
            return 0
        if args.once_sync:
            emit(run_sync_cycle(service, state))
            return 0
        if args.once_recover:
            emit(run_recovery_cycle(service, state))
            return 0
        if args.once_preflight:
            emit(run_preflight_cycle(service, state))
            return 0
        if args.once_observability:
            emit(run_observability_cycle(service, state))
            return 0
        if args.once_shadow_retrain:
            emit(run_shadow_retrain_cycle(service, state))
            return 0
        if args.once_digest:
            emit(run_daily_digest_cycle(service, state, phase=args.digest_phase))
            return 0
        if args.once_weekly_digest:
            emit(run_weekly_digest_cycle(service, state))
            return 0

        run_loop(service, poll_seconds=args.poll_seconds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
