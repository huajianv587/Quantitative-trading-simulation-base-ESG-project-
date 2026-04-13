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


def request_json(method: str, url: str, *, timeout: int, body: dict | None = None) -> tuple[int, dict | str]:
    response = requests.request(method, url, json=body, timeout=timeout)
    try:
        return response.status_code, response.json()
    except Exception:
        return response.status_code, response.text


def emit_json(payload: dict) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    print(text)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8088)
    parser.add_argument("--startup-timeout", type=int, default=120)
    parser.add_argument("--request-timeout", type=int, default=180)
    args = parser.parse_args()

    python_exe = resolve_python_executable()
    if not python_exe:
        emit_json({"ok": False, "error": "python executable not found"})
        return 1

    base_url = f"http://{args.host}:{args.port}"
    temp_dir = Path(tempfile.gettempdir())
    stdout_log = temp_dir / f"esg_p1_stack_{args.port}.log"
    stderr_log = temp_dir / f"esg_p1_stack_{args.port}.err.log"
    stdout_log.write_text("", encoding="utf-8")
    stderr_log.write_text("", encoding="utf-8")

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
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
        stdout=stdout_log.open("w", encoding="utf-8"),
        stderr=stderr_log.open("w", encoding="utf-8"),
        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
    )

    try:
        ready, health_payload = wait_for_health(base_url, args.startup_timeout)
        if not ready:
            emit_json({"ok": False, "stage": "startup", "health": health_payload})
            return 1

        status_code, status_payload = request_json("GET", f"{base_url}/api/v1/quant/p1/status", timeout=args.request_timeout)
        report_code, report_payload = request_json(
            "POST",
            f"{base_url}/api/v1/quant/p1/stack/run",
            timeout=args.request_timeout,
            body={
                "universe": ["AAPL", "MSFT", "TSLA", "NEE", "PG"],
                "benchmark": "SPY",
                "capital_base": 500000,
                "research_question": "Run the P1 alpha + risk stack smoke test.",
            },
        )
        ok = (
            status_code == 200
            and report_code == 200
            and isinstance(status_payload, dict)
            and isinstance(report_payload, dict)
            and "models" in status_payload
            and "deployment_readiness" in report_payload
        )
        emit_json(
            {
                "ok": ok,
                "health": health_payload,
                "status_code": status_code,
                "report_code": report_code,
                "suite_status": status_payload,
                "report": report_payload,
            }
        )
        return 0 if ok else 1
    finally:
        stop_process(proc)


if __name__ == "__main__":
    raise SystemExit(main())
