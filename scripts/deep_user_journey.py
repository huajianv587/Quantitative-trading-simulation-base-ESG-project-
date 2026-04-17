from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")
OUTPUT_DIR = PROJECT_ROOT / "test-results" / "deep-user-audit"


def resolve_python_executable() -> str | None:
    candidates = [
        PROJECT_ROOT / ".venv" / "Scripts" / "python.exe",
        PROJECT_ROOT / ".venv" / "bin" / "python",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    if sys.executable and Path(sys.executable).exists():
        return sys.executable
    return shutil.which("python")


def emit_json(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def wait_for_health(base_url: str, timeout: int) -> tuple[bool, dict | str]:
    deadline = time.time() + timeout
    last_error: str = "not started"
    while time.time() < deadline:
        try:
            response = requests.get(f"{base_url}/health/ready", timeout=5)
            response.raise_for_status()
            return True, response.json()
        except Exception as exc:
            last_error = str(exc)
            time.sleep(2)
    return False, last_error


def stop_process(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


def tail_log(path: Path, limit: int = 120) -> str:
    if not path.exists():
        return ""
    return "\n".join(path.read_text(encoding="utf-8", errors="ignore").splitlines()[-limit:])


def api_key_for_path(path: str) -> str:
    normalized = str(path or "")
    if normalized.startswith("/ops"):
        return os.getenv("OPS_API_KEY") or os.getenv("ADMIN_API_KEY") or ""
    if normalized.startswith("/admin"):
        return os.getenv("ADMIN_API_KEY") or os.getenv("OPS_API_KEY") or ""
    if normalized.startswith("/api/v1/quant/execution") or normalized.startswith("/api/v1/quant/validation"):
        return os.getenv("EXECUTION_API_KEY") or os.getenv("ADMIN_API_KEY") or os.getenv("OPS_API_KEY") or ""
    return ""


def request_json(method: str, url: str, *, timeout: int, body: dict | None = None, path: str = "") -> tuple[int, dict | str]:
    headers = {}
    api_key = api_key_for_path(path)
    if api_key:
        headers["x-api-key"] = api_key
        headers["Authorization"] = f"Bearer {api_key}"
    response = requests.request(method, url, json=body, timeout=timeout, headers=headers)
    try:
        payload = response.json()
    except Exception:
        payload = response.text
    return response.status_code, payload


def payload_preview(payload: Any) -> str:
    if isinstance(payload, (dict, list)):
        return json.dumps(payload, ensure_ascii=False)[:1200]
    return str(payload)[:1200]


def mark_step(result: dict, step: str, status: int, payload: Any, ok: bool | None = None) -> None:
    result["steps"].append(
        {
            "step": step,
            "status_code": status,
            "ok": bool(status == 200 if ok is None else ok),
            "payload_preview": payload_preview(payload),
        }
    )


def run_user_flow(base_url: str, request_timeout: int, run_id: str, user_index: int) -> dict:
    email = f"deep.audit.{run_id}.{user_index}@example.com"
    password = f"Init-{run_id}-{user_index}!"
    new_password = f"Reset-{run_id}-{user_index}!"
    result = {
        "run_id": run_id,
        "user_index": user_index,
        "email": email,
        "user_id": None,
        "subscription_id": None,
        "subscription_observed": False,
        "steps": [],
    }

    status, payload = request_json(
        "POST",
        f"{base_url}/auth/register",
        timeout=request_timeout,
        body={"email": email, "password": password, "name": f"Audit User {user_index}"},
        path="/auth/register",
    )
    mark_step(result, "register", status, payload)
    token = payload.get("token") if isinstance(payload, dict) else None
    user_id = payload.get("user", {}).get("id") if isinstance(payload, dict) else None
    result["user_id"] = user_id

    status, payload = request_json(
        "POST",
        f"{base_url}/auth/login",
        timeout=request_timeout,
        body={"email": email, "password": password},
        path="/auth/login",
    )
    mark_step(result, "login_initial", status, payload)
    login_token = payload.get("token") if isinstance(payload, dict) else token

    if login_token:
        query = urlencode({"token": login_token})
        status, payload = request_json(
            "GET",
            f"{base_url}/auth/verify?{query}",
            timeout=request_timeout,
            path="/auth/verify",
        )
        mark_step(result, "verify_token", status, payload)

    status, payload = request_json(
        "POST",
        f"{base_url}/auth/reset-password/request",
        timeout=request_timeout,
        body={"email": email},
        path="/auth/reset-password/request",
    )
    mark_step(result, "reset_request", status, payload)
    reset_token = payload.get("_dev_token") if isinstance(payload, dict) else None

    if reset_token:
        status, payload = request_json(
            "POST",
            f"{base_url}/auth/reset-password/confirm",
            timeout=request_timeout,
            body={"token": reset_token, "new_password": new_password},
            path="/auth/reset-password/confirm",
        )
        mark_step(result, "reset_confirm", status, payload)

        status, payload = request_json(
            "POST",
            f"{base_url}/auth/login",
            timeout=request_timeout,
            body={"email": email, "password": new_password},
            path="/auth/login",
        )
        mark_step(result, "login_after_reset", status, payload)
    else:
        mark_step(result, "reset_confirm", 0, {"detail": "reset token unavailable in non-local mode"}, ok=False)

    mark_step(result, "logout_simulated", 200, {"detail": "client-side logout simulated by discarding token"})

    status, payload = request_json("GET", f"{base_url}/api/v1/quant/platform/overview", timeout=request_timeout, path="/api/v1/quant/platform/overview")
    mark_step(result, "dashboard_overview", status, payload)

    status, payload = request_json(
        "POST",
        f"{base_url}/api/v1/quant/research/run",
        timeout=request_timeout,
        body={
            "universe": ["AAPL", "MSFT", "NVDA"],
            "benchmark": "SPY",
            "research_question": f"User {user_index} deep journey research run",
            "capital_base": 250000,
            "horizon_days": 10,
        },
        path="/api/v1/quant/research/run",
    )
    mark_step(result, "research_run", status, payload)

    status, payload = request_json(
        "POST",
        f"{base_url}/api/v1/quant/portfolio/optimize",
        timeout=request_timeout,
        body={
            "universe": ["COST", "WMT", "PG"],
            "benchmark": "SPY",
            "capital_base": 250000,
            "research_question": f"User {user_index} portfolio build",
        },
        path="/api/v1/quant/portfolio/optimize",
    )
    mark_step(result, "portfolio_optimize", status, payload)

    status, payload = request_json(
        "POST",
        f"{base_url}/api/v1/quant/backtests/run",
        timeout=request_timeout,
        body={
            "strategy_name": "ESG Multi-Factor Long-Only",
            "universe": ["AAPL", "MSFT"],
            "benchmark": "SPY",
            "capital_base": 250000,
            "lookback_days": 60,
        },
        path="/api/v1/quant/backtests/run",
    )
    mark_step(result, "backtest_run", status, payload)

    status, payload = request_json(
        "POST",
        f"{base_url}/api/v1/quant/execution/paper",
        timeout=request_timeout,
        body={
            "universe": ["AAPL", "MSFT"],
            "benchmark": "SPY",
            "capital_base": 250000,
            "mode": "paper",
            "submit_orders": False,
            "max_orders": 1,
            "per_order_notional": 1.0,
        },
        path="/api/v1/quant/execution/paper",
    )
    mark_step(result, "execution_plan", status, payload)

    status, payload = request_json(
        "POST",
        f"{base_url}/api/v1/quant/validation/run",
        timeout=request_timeout,
        body={
            "strategy_name": "ESG Multi-Factor Long-Only",
            "universe": ["AAPL", "MSFT"],
            "benchmark": "SPY",
            "capital_base": 250000,
            "in_sample_days": 120,
            "out_of_sample_days": 30,
            "walk_forward_windows": 2,
        },
        path="/api/v1/quant/validation/run",
    )
    mark_step(result, "validation_run", status, payload)

    status, payload = request_json(
        "POST",
        f"{base_url}/admin/reports/generate",
        timeout=request_timeout,
        body={"report_type": "daily", "companies": ["Tesla", "Microsoft"], "async": False},
        path="/admin/reports/generate",
    )
    mark_step(result, "report_generate", status, payload)

    subscription_query = urlencode({"user_id": user_id or f"user_{user_index}"})
    status, payload = request_json(
        "POST",
        f"{base_url}/user/reports/subscribe?{subscription_query}",
        timeout=request_timeout,
        body={
            "report_types": ["daily"],
            "companies": ["Tesla", "Microsoft"],
            "alert_threshold": {"overall_score": 40},
            "push_channels": ["email", "in_app"],
            "frequency": "daily",
        },
        path="/user/reports/subscribe",
    )
    mark_step(result, "subscription_create", status, payload)
    subscription_id = payload.get("subscription_id") if isinstance(payload, dict) else None
    result["subscription_id"] = subscription_id

    status, payload = request_json(
        "GET",
        f"{base_url}/user/reports/subscriptions?{subscription_query}",
        timeout=request_timeout,
        path="/user/reports/subscriptions",
    )
    mark_step(result, "subscription_list", status, payload)
    if isinstance(payload, dict):
        result["subscription_observed"] = bool(payload.get("subscriptions"))

    if subscription_id:
        status, payload = request_json(
            "PUT",
            f"{base_url}/user/reports/subscriptions/{subscription_id}",
            timeout=request_timeout,
            body={"frequency": "weekly"},
            path="/user/reports/subscriptions",
        )
        mark_step(result, "subscription_update", status, payload)

        status, payload = request_json(
            "DELETE",
            f"{base_url}/user/reports/subscriptions/{subscription_id}",
            timeout=request_timeout,
            path="/user/reports/subscriptions",
        )
        mark_step(result, "subscription_delete", status, payload)

    result["ok"] = all(step["ok"] for step in result["steps"])
    return result


def write_sqlite(report_path: Path, results: list[dict]) -> Path:
    sqlite_path = report_path.with_suffix(".sqlite3")
    if sqlite_path.exists():
        sqlite_path.unlink()

    conn = sqlite3.connect(sqlite_path)
    try:
        conn.execute(
            """
            create table users (
              run_id text,
              user_index integer,
              email text,
              user_id text,
              ok integer,
              subscription_id text,
              subscription_observed integer
            )
            """
        )
        conn.execute(
            """
            create table steps (
              run_id text,
              user_index integer,
              step text,
              status_code integer,
              ok integer,
              payload_preview text
            )
            """
        )
        for result in results:
            conn.execute(
                "insert into users values (?, ?, ?, ?, ?, ?, ?)",
                (
                    result["run_id"],
                    result["user_index"],
                    result["email"],
                    result.get("user_id"),
                    1 if result.get("ok") else 0,
                    result.get("subscription_id"),
                    1 if result.get("subscription_observed") else 0,
                ),
            )
            for step in result["steps"]:
                conn.execute(
                    "insert into steps values (?, ?, ?, ?, ?, ?)",
                    (
                        result["run_id"],
                        result["user_index"],
                        step["step"],
                        step["status_code"],
                        1 if step["ok"] else 0,
                        step["payload_preview"],
                    ),
                )
        conn.commit()
    finally:
        conn.close()
    return sqlite_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8026)
    parser.add_argument("--startup-timeout", type=int, default=120)
    parser.add_argument("--request-timeout", type=int, default=180)
    parser.add_argument("--users", type=int, default=30)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--app-mode", default="local")
    parser.add_argument("--llm-backend-mode", default=os.getenv("LLM_BACKEND_MODE", "auto"))
    args = parser.parse_args()

    python_exe = resolve_python_executable()
    if not python_exe:
        emit_json({"ok": False, "error": "python executable not found"})
        return 1

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    run_id = str(int(time.time()))
    report_path = OUTPUT_DIR / f"report-{run_id}.json"
    base_url = f"http://{args.host}:{args.port}"
    temp_dir = Path(tempfile.gettempdir())
    stdout_log = temp_dir / f"deep_user_journey_{args.port}.log"
    stderr_log = temp_dir / f"deep_user_journey_{args.port}.err.log"
    stdout_log.write_text("", encoding="utf-8")
    stderr_log.write_text("", encoding="utf-8")

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["APP_MODE"] = args.app_mode
    env["LLM_BACKEND_MODE"] = args.llm_backend_mode

    proc = subprocess.Popen(
        [
            python_exe,
            "-m",
            "uvicorn",
            "gateway.main:app",
            "--host",
            args.host,
            "--port",
            str(args.port),
        ],
        cwd=PROJECT_ROOT,
        env=env,
        stdout=stdout_log.open("w", encoding="utf-8"),
        stderr=stderr_log.open("w", encoding="utf-8"),
        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
    )

    try:
        ready, health_payload = wait_for_health(base_url, args.startup_timeout)
        if not ready:
            emit_json(
                {
                    "ok": False,
                    "stage": "startup",
                    "health": health_payload,
                    "stdout_tail": tail_log(stdout_log),
                    "stderr_tail": tail_log(stderr_log),
                }
            )
            return 1

        results: list[dict] = []
        with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
            futures = [
                executor.submit(run_user_flow, base_url, args.request_timeout, run_id, user_index)
                for user_index in range(1, args.users + 1)
            ]
            for future in as_completed(futures):
                results.append(future.result())

        results.sort(key=lambda item: item["user_index"])
        auth_status_code, auth_status_payload = request_json(
            "GET",
            f"{base_url}/auth/status",
            timeout=args.request_timeout,
            path="/auth/status",
        )

        report = {
            "ok": all(item.get("ok") for item in results),
            "run_id": run_id,
            "user_count": args.users,
            "worker_count": args.workers,
            "base_url": base_url,
            "health": health_payload,
            "auth_storage": {
                "status_code": auth_status_code,
                "status": auth_status_payload,
            },
            "results": results,
        }
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        sqlite_path = write_sqlite(report_path, results)
        report["sqlite_report"] = str(sqlite_path)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        emit_json(report)
        return 0 if report["ok"] else 1
    finally:
        stop_process(proc)


if __name__ == "__main__":
    raise SystemExit(main())
