from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")


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
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    print(text)


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


def request_json(method: str, url: str, *, timeout: int, body: dict | None = None) -> tuple[int, dict | str]:
    headers = {}
    api_key = api_key_for_path(urlparse(url).path)
    if api_key:
        headers["x-api-key"] = api_key
        headers["Authorization"] = f"Bearer {api_key}"
    response = requests.request(method, url, json=body, timeout=timeout, headers=headers)
    try:
        payload = response.json()
    except Exception:
        payload = response.text
    return response.status_code, payload


def mark(results: list[dict], name: str, status_code: int, payload, ok: bool | None = None) -> None:
    results.append(
        {
            "name": name,
            "status_code": status_code,
            "ok": bool(status_code == 200 if ok is None else ok),
            "payload_preview": payload if isinstance(payload, (dict, list)) else str(payload)[:600],
        }
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8016)
    parser.add_argument("--startup-timeout", type=int, default=120)
    parser.add_argument("--request-timeout", type=int, default=180)
    parser.add_argument("--app-mode", default=os.getenv("APP_MODE", "local"))
    parser.add_argument("--llm-backend-mode", default=os.getenv("LLM_BACKEND_MODE", "auto"))
    args = parser.parse_args()

    python_exe = resolve_python_executable()
    if not python_exe:
        emit_json({"ok": False, "error": "python executable not found"})
        return 1

    base_url = f"http://{args.host}:{args.port}"
    temp_dir = Path(tempfile.gettempdir())
    stdout_log = temp_dir / f"esg_full_system_{args.port}.log"
    stderr_log = temp_dir / f"esg_full_system_{args.port}.err.log"
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
        unique = str(int(time.time()))

        status, payload = request_json("GET", f"{base_url}/health", timeout=args.request_timeout)
        mark(results, "health", status, payload)

        status, payload = request_json("GET", f"{base_url}/dashboard/overview", timeout=args.request_timeout)
        mark(results, "dashboard_overview", status, payload)

        status, payload = request_json("POST", f"{base_url}/session?session_id=smoke-{unique}", timeout=args.request_timeout)
        mark(results, "session_create", status, payload)

        status, payload = request_json(
            "POST",
            f"{base_url}/query",
            timeout=args.request_timeout,
            body={"session_id": f"smoke-{unique}", "question": "What is Apple's renewable energy goal?"},
        )
        mark(results, "rag_query", status, payload)

        status, payload = request_json("GET", f"{base_url}/history/smoke-{unique}", timeout=args.request_timeout)
        mark(results, "session_history", status, payload)

        status, payload = request_json(
            "POST",
            f"{base_url}/agent/analyze",
            timeout=args.request_timeout,
            body={"session_id": f"smoke-{unique}", "question": "Analyze Tesla ESG performance briefly."},
        )
        mark(results, "agent_analyze", status, payload)

        status, payload = request_json(
            "POST",
            f"{base_url}/agent/esg-score",
            timeout=args.request_timeout,
            body={"company": "Tesla", "ticker": "TSLA", "include_visualization": True, "peers": ["Ford", "GM"]},
        )
        mark(results, "agent_esg_score", status, payload)

        status, payload = request_json("GET", f"{base_url}/api/v1/quant/platform/overview", timeout=args.request_timeout)
        mark(results, "quant_overview", status, payload)

        status, payload = request_json("GET", f"{base_url}/api/v1/quant/universe/default", timeout=args.request_timeout)
        mark(results, "quant_universe", status, payload)

        status, payload = request_json(
            "POST",
            f"{base_url}/api/v1/quant/research/run",
            timeout=args.request_timeout,
            body={
                "universe": ["AAPL", "MSFT", "TSLA"],
                "benchmark": "SPY",
                "research_question": "Generate a paper trading shortlist.",
                "capital_base": 500000,
                "horizon_days": 10,
            },
        )
        mark(results, "quant_research", status, payload)

        status, payload = request_json(
            "POST",
            f"{base_url}/api/v1/quant/portfolio/optimize",
            timeout=args.request_timeout,
            body={
                "universe": ["AAPL", "MSFT", "TSLA"],
                "benchmark": "SPY",
                "capital_base": 500000,
                "research_question": "Paper execution test.",
            },
        )
        mark(results, "quant_portfolio", status, payload)

        status, payload = request_json("GET", f"{base_url}/api/v1/quant/p1/status", timeout=args.request_timeout)
        mark(results, "quant_p1_status", status, payload)

        status, payload = request_json(
            "POST",
            f"{base_url}/api/v1/quant/p1/stack/run",
            timeout=args.request_timeout,
            body={
                "universe": ["AAPL", "MSFT", "TSLA"],
                "benchmark": "SPY",
                "capital_base": 500000,
                "research_question": "Run the P1 alpha + risk stack.",
            },
        )
        mark(results, "quant_p1_stack", status, payload)

        status, payload = request_json("GET", f"{base_url}/api/v1/quant/p2/status", timeout=args.request_timeout)
        mark(results, "quant_p2_status", status, payload)

        status, payload = request_json(
            "POST",
            f"{base_url}/api/v1/quant/p2/decision/run",
            timeout=args.request_timeout,
            body={
                "universe": ["AAPL", "MSFT", "TSLA", "NEE", "PG"],
                "benchmark": "SPY",
                "capital_base": 500000,
                "research_question": "Run the P2 graph + strategy selector stack.",
            },
        )
        mark(results, "quant_p2_decision", status, payload)

        status, payload = request_json(
            "POST",
            f"{base_url}/api/v1/quant/backtests/run",
            timeout=args.request_timeout,
            body={
                "strategy_name": "ESG Multi-Factor Long-Only",
                "universe": ["AAPL", "MSFT", "TSLA"],
                "benchmark": "SPY",
                "capital_base": 500000,
                "lookback_days": 90,
            },
        )
        mark(results, "quant_backtest_run", status, payload)
        backtest_id = payload.get("backtest_id") if isinstance(payload, dict) else None

        status, payload = request_json("GET", f"{base_url}/api/v1/quant/backtests", timeout=args.request_timeout)
        mark(results, "quant_backtest_list", status, payload)

        if backtest_id:
          status, payload = request_json("GET", f"{base_url}/api/v1/quant/backtests/{backtest_id}", timeout=args.request_timeout)
          mark(results, "quant_backtest_get", status, payload)

        status, payload = request_json(
            "POST",
            f"{base_url}/api/v1/quant/execution/paper",
            timeout=args.request_timeout,
            body={
                "universe": ["AAPL", "MSFT", "TSLA"],
                "benchmark": "SPY",
                "capital_base": 500000,
                "mode": "paper",
                "submit_orders": False,
                "max_orders": 1,
                "per_order_notional": 1.0,
                "order_type": "market",
                "time_in_force": "day",
            },
        )
        mark(results, "quant_execution_plan", status, payload)
        execution_id = payload.get("execution_id") if isinstance(payload, dict) else None

        status, payload = request_json("GET", f"{base_url}/api/v1/quant/execution/account", timeout=args.request_timeout)
        mark(results, "quant_execution_account", status, payload)

        status, payload = request_json("GET", f"{base_url}/api/v1/quant/execution/brokers", timeout=args.request_timeout)
        mark(results, "quant_execution_brokers", status, payload)

        status, payload = request_json("GET", f"{base_url}/api/v1/quant/execution/orders?status=all&limit=10", timeout=args.request_timeout)
        mark(results, "quant_execution_orders", status, payload)

        status, payload = request_json("GET", f"{base_url}/api/v1/quant/execution/positions", timeout=args.request_timeout)
        mark(results, "quant_execution_positions", status, payload)

        status, payload = request_json(
            "POST",
            f"{base_url}/api/v1/quant/validation/run",
            timeout=args.request_timeout,
            body={
                "strategy_name": "ESG Multi-Factor Long-Only",
                "universe": ["AAPL", "MSFT", "TSLA"],
                "benchmark": "SPY",
                "capital_base": 500000,
                "in_sample_days": 180,
                "out_of_sample_days": 45,
                "walk_forward_windows": 2,
            },
        )
        mark(results, "quant_validation", status, payload)

        if execution_id:
            status, payload = request_json("GET", f"{base_url}/api/v1/quant/execution/journal/{execution_id}", timeout=args.request_timeout)
            mark(results, "quant_execution_journal", status, payload)

        status, payload = request_json("GET", f"{base_url}/ops/runtime", timeout=args.request_timeout)
        mark(results, "ops_runtime", status, payload)

        status, payload = request_json("GET", f"{base_url}/ops/metrics", timeout=args.request_timeout)
        mark(results, "ops_metrics", status, payload)

        status, payload = request_json("GET", f"{base_url}/ops/healthcheck", timeout=args.request_timeout)
        mark(results, "ops_healthcheck", status, payload)

        status, payload = request_json("GET", f"{base_url}/ops/alerts", timeout=args.request_timeout)
        mark(results, "ops_alerts", status, payload)

        status, payload = request_json("GET", f"{base_url}/ops/models", timeout=args.request_timeout)
        mark(results, "ops_models", status, payload)

        status, payload = request_json("GET", f"{base_url}/ops/audit/search?limit=5", timeout=args.request_timeout)
        mark(results, "ops_audit_search", status, payload)

        status, payload = request_json("GET", f"{base_url}/api/v1/quant/experiments", timeout=args.request_timeout)
        mark(results, "quant_experiments", status, payload)

        status, payload = request_json(
            "POST",
            f"{base_url}/admin/reports/generate",
            timeout=args.request_timeout,
            body={"report_type": "weekly", "companies": ["Tesla", "Apple"], "async": False},
        )
        mark(results, "report_generate_sync", status, payload)
        report_id = payload.get("report_id") if isinstance(payload, dict) else None

        if report_id:
            status, payload = request_json("GET", f"{base_url}/admin/reports/{report_id}", timeout=args.request_timeout)
            mark(results, "report_get", status, payload)

            status, payload = request_json("GET", f"{base_url}/admin/reports/export/{report_id}?format=json", timeout=args.request_timeout)
            mark(results, "report_export", status, payload)

        status, payload = request_json("GET", f"{base_url}/admin/reports/latest?report_type=weekly", timeout=args.request_timeout)
        mark(results, "report_latest", status, payload, ok=status in {200, 204})

        status, payload = request_json("GET", f"{base_url}/admin/reports/statistics?period=2026-04-01:2026-04-10&group_by=report_type", timeout=args.request_timeout)
        mark(results, "report_statistics", status, payload)

        status, payload = request_json(
            "POST",
            f"{base_url}/admin/data-sources/sync",
            timeout=args.request_timeout,
            body={"companies": ["Tesla"], "force_refresh": False},
        )
        mark(results, "data_sync_start", status, payload)
        sync_job_id = payload.get("job_id") if isinstance(payload, dict) else None
        time.sleep(3)
        if sync_job_id:
            status, payload = request_json("GET", f"{base_url}/admin/data-sources/sync/{sync_job_id}", timeout=args.request_timeout)
            mark(results, "data_sync_status", status, payload)

        rule_name = f"smoke_rule_{unique}"
        status, payload = request_json(
            "POST",
            f"{base_url}/admin/push-rules",
            timeout=args.request_timeout,
            body={
                "rule_name": rule_name,
                "condition": "overall_score < 50",
                "target_users": "holders",
                "push_channels": ["in_app"],
                "priority": 5,
                "template_id": "template_low_esg_warning",
            },
        )
        mark(results, "push_rule_create", status, payload)
        rule_id = payload.get("rule_id") if isinstance(payload, dict) else None

        status, payload = request_json("GET", f"{base_url}/admin/push-rules", timeout=args.request_timeout)
        mark(results, "push_rule_list", status, payload)

        if rule_id:
            status, payload = request_json(
                "PUT",
                f"{base_url}/admin/push-rules/{rule_id}",
                timeout=args.request_timeout,
                body={"priority": 7, "enabled": True},
            )
            mark(results, "push_rule_update", status, payload)

            status, payload = request_json(
                "POST",
                f"{base_url}/admin/push-rules/{rule_id}/test",
                timeout=args.request_timeout,
                body={"test_user_id": "user_123", "mock_report": {"overall_score": 35}},
            )
            mark(results, "push_rule_test", status, payload)

        status, payload = request_json(
            "POST",
            f"{base_url}/user/reports/subscribe",
            timeout=args.request_timeout,
            body={
                "report_types": ["weekly"],
                "companies": ["Tesla", "Apple"],
                "alert_threshold": {"overall_score": 40},
                "push_channels": ["in_app"],
                "frequency": "daily",
            },
        )
        mark(results, "subscription_create", status, payload)
        subscription_id = payload.get("subscription_id") if isinstance(payload, dict) else None

        status, payload = request_json("GET", f"{base_url}/user/reports/subscriptions", timeout=args.request_timeout)
        mark(results, "subscription_list", status, payload)

        if subscription_id:
            status, payload = request_json(
                "PUT",
                f"{base_url}/user/reports/subscriptions/{subscription_id}",
                timeout=args.request_timeout,
                body={"frequency": "weekly"},
            )
            mark(results, "subscription_update", status, payload)

        status, payload = request_json("POST", f"{base_url}/scheduler/scan", timeout=args.request_timeout, body={})
        mark(results, "scheduler_scan", status, payload)
        time.sleep(3)

        status, payload = request_json("GET", f"{base_url}/scheduler/scan/status", timeout=args.request_timeout)
        mark(results, "scheduler_scan_status", status, payload)

        status, payload = request_json("GET", f"{base_url}/scheduler/statistics?days=7", timeout=args.request_timeout)
        mark(results, "scheduler_statistics", status, payload)

        if rule_id:
            status, payload = request_json("DELETE", f"{base_url}/admin/push-rules/{rule_id}", timeout=args.request_timeout)
            mark(results, "push_rule_delete", status, payload)

        if subscription_id:
            status, payload = request_json("DELETE", f"{base_url}/user/reports/subscriptions/{subscription_id}", timeout=args.request_timeout)
            mark(results, "subscription_delete", status, payload)

        failed = [item for item in results if not item["ok"]]
        emit_json(
            {
                "ok": not failed,
                "total_checks": len(results),
                "failed_checks": len(failed),
                "results": results,
            }
        )
        return 0 if not failed else 1
    finally:
        stop_process(proc)


if __name__ == "__main__":
    raise SystemExit(main())
