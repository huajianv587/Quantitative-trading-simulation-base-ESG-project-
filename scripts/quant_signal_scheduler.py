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

load_dotenv()


def now_local() -> datetime:
    return datetime.now(ZoneInfo(getattr(settings, "SCHEDULER_TIMEZONE", "America/New_York")))


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


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


def due(current_hhmm: str, target_hhmm: str) -> bool:
    return current_hhmm >= target_hhmm


def between(current_hhmm: str, start_hhmm: str, end_hhmm: str) -> bool:
    return start_hhmm <= current_hhmm <= end_hhmm


def max_execution_symbols() -> int:
    return max(1, int(getattr(settings, "SCHEDULER_MAX_EXECUTION_SYMBOLS", 2) or 2))


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
    execution_id = str((state.get("execution", {}) or {}).get("execution_id") or "").strip()
    broker_id = getattr(settings, "QUANT_BROKER_DEFAULT", "alpaca")
    if not execution_id:
        return {
            "stage": "manage",
            "timestamp": now_local().isoformat(),
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
        "market_clock": market_clock,
        "actions": actions,
        "action_count": len(actions),
        "warnings": warnings,
        "skipped": not actions,
    }
    return result


def update_heartbeat(state: dict[str, Any], *, stage: str, message: str) -> None:
    payload = {
        "updated_at": now_utc().isoformat(),
        "local_time": now_local().isoformat(),
        "hostname": socket.gethostname(),
        "pid": os.getpid(),
        "stage": stage,
        "message": message,
        "last_trade_date": state.get("trade_date"),
        "last_preopen_at": state.get("preopen", {}).get("ran_at"),
        "last_execution_at": state.get("execution", {}).get("ran_at"),
        "last_sync_at": state.get("sync", {}).get("ran_at"),
        "execution_id": state.get("execution", {}).get("execution_id"),
    }
    write_json(scheduler_heartbeat_path(), payload)


def run_preopen_cycle(service, state: dict[str, Any]) -> dict[str, Any]:
    universe = configured_universe(service)
    trade_date = now_local().date().isoformat()
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
        "ran_at": now_utc().isoformat(),
        "universe": universe,
        "research_id": research.get("research_id"),
        "validation_id": validation.get("validation_id"),
        "candidate_symbols": candidate_symbols,
        "candidate_count": len(candidate_symbols),
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
    state["preopen"] = snapshot
    state.setdefault("execution", {})
    state.setdefault("sync", {})
    write_json(scheduler_state_path(), state)
    update_heartbeat(state, stage="preopen", message="Pre-open research cycle completed.")
    return {"stage": "preopen", "timestamp": now_local().isoformat(), **snapshot}


def _execution_universe_from_state(service, state: dict[str, Any]) -> list[str]:
    trade_date = now_local().date().isoformat()
    if state.get("trade_date") == trade_date:
        candidates = [
            str(item).upper()
            for item in (state.get("preopen", {}) or {}).get("candidate_symbols", [])
            if str(item).strip()
        ]
        if candidates:
            return candidates
    return configured_universe(service)


def run_execution_cycle(service, state: dict[str, Any]) -> dict[str, Any]:
    universe = _execution_universe_from_state(service, state)
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
    )
    snapshot = {
        "trade_date": now_local().date().isoformat(),
        "ran_at": now_utc().isoformat(),
        "universe": universe,
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
    state["execution"] = snapshot
    write_json(scheduler_state_path(), state)
    update_heartbeat(state, stage="execution", message="Execution cycle completed.")
    return {"stage": "execution", "timestamp": now_local().isoformat(), **snapshot}


def run_sync_cycle(service, state: dict[str, Any]) -> dict[str, Any]:
    execution_id = str((state.get("execution", {}) or {}).get("execution_id") or "").strip()
    if not execution_id:
        result = {
            "stage": "sync",
            "timestamp": now_local().isoformat(),
            "skipped": True,
            "reason": "No execution_id available for intraday sync.",
        }
        state["sync"] = {"trade_date": now_local().date().isoformat(), "ran_at": now_utc().isoformat(), **result}
        write_json(scheduler_state_path(), state)
        update_heartbeat(state, stage="sync", message=result["reason"])
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
        "trade_date": now_local().date().isoformat(),
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
    write_json(scheduler_state_path(), state)
    update_heartbeat(state, stage="sync", message="Intraday journal sync completed.")
    return {"stage": "sync", "timestamp": now_local().isoformat(), **snapshot}


def stale_lock_seconds() -> int:
    minutes = max(15, int(getattr(settings, "SCHEDULER_LOCK_STALE_MINUTES", 240) or 240))
    return minutes * 60


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
        if age > stale_lock_seconds():
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
    while True:
        current = now_local()
        current_date = current.date().isoformat()
        current_hhmm = current.strftime("%H:%M")
        update_heartbeat(state, stage="idle", message="Scheduler heartbeat is healthy.")

        if current.weekday() < 5:
            preopen_state = state.get("preopen", {}) or {}
            if current_date != preopen_state.get("trade_date") and due(current_hhmm, getattr(settings, "SCHEDULER_PREOPEN_SIGNAL_TIME", "09:00")):
                result = run_preopen_cycle(service, state)
                emit(result)
                state = load_json(scheduler_state_path(), default=state)

            execution_state = state.get("execution", {}) or {}
            if current_date != execution_state.get("trade_date") and due(current_hhmm, getattr(settings, "SCHEDULER_EXECUTION_TIME", "09:31")):
                result = run_execution_cycle(service, state)
                emit(result)
                state = load_json(scheduler_state_path(), default=state)

            if (
                state.get("trade_date") == current_date
                and state.get("execution", {}).get("execution_id")
                and between(
                    current_hhmm,
                    getattr(settings, "SCHEDULER_EXECUTION_TIME", "09:31"),
                    getattr(settings, "SCHEDULER_SYNC_END_TIME", "16:10"),
                )
                and time.time() - last_sync_at >= sync_interval_seconds()
            ):
                result = run_sync_cycle(service, state)
                emit(result)
                state = load_json(scheduler_state_path(), default=state)
                last_sync_at = time.time()

        time.sleep(max(5, int(poll_seconds)))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once-preopen", action="store_true")
    parser.add_argument("--once-execute", action="store_true")
    parser.add_argument("--once-sync", action="store_true")
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
        if args.once_sync:
            emit(run_sync_cycle(service, state))
            return 0

        run_loop(service, poll_seconds=args.poll_seconds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
