from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYTHON_EXE = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"


def wait_for_health(base_url: str, timeout: int) -> tuple[bool, dict | str]:
    deadline = time.time() + timeout
    last_error: str = "not started"
    while time.time() < deadline:
        try:
            response = requests.get(f"{base_url}/health/ready", timeout=5)
            response.raise_for_status()
            return True, response.json()
        except Exception as exc:  # pragma: no cover - runtime diagnostic helper
            last_error = str(exc)
            time.sleep(2)
    return False, last_error


def stop_process(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return

    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:  # pragma: no cover - defensive cleanup
        proc.kill()
        proc.wait(timeout=5)


def tail_log(path: Path, limit: int = 80) -> str:
    if not path.exists():
        return ""
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    return "\n".join(lines[-limit:])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--startup-timeout", type=int, default=60)
    parser.add_argument("--request-timeout", type=int, default=180)
    parser.add_argument(
        "--question",
        default="Please summarize DBS 2024 ESG priorities in 5 bullet points.",
    )
    parser.add_argument("--session-id", default="local-smoke")
    parser.add_argument("--app-mode", default=os.getenv("APP_MODE", "local"))
    parser.add_argument(
        "--llm-backend-mode",
        default=os.getenv("LLM_BACKEND_MODE", "auto"),
    )
    args = parser.parse_args()

    if not PYTHON_EXE.exists():
        print(json.dumps({"ok": False, "error": f"missing interpreter: {PYTHON_EXE}"}, ensure_ascii=False, indent=2))
        return 1

    base_url = f"http://{args.host}:{args.port}"
    temp_dir = Path(tempfile.gettempdir())
    stdout_log = temp_dir / f"esg_local_api_{args.port}.log"
    stderr_log = temp_dir / f"esg_local_api_{args.port}.err.log"
    stdout_log.write_text("", encoding="utf-8")
    stderr_log.write_text("", encoding="utf-8")

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["APP_MODE"] = args.app_mode
    env["LLM_BACKEND_MODE"] = args.llm_backend_mode

    proc = subprocess.Popen(
        [
            str(PYTHON_EXE),
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
        health_ok, health_payload = wait_for_health(base_url, args.startup_timeout)
        if not health_ok:
            result = {
                "ok": False,
                "stage": "startup",
                "health": health_payload,
                "stdout_tail": tail_log(stdout_log),
                "stderr_tail": tail_log(stderr_log),
            }
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 1

        analyze_response = requests.post(
            f"{base_url}/agent/analyze",
            json={"session_id": args.session_id, "question": args.question},
            timeout=args.request_timeout,
        )

        result = {
            "ok": analyze_response.ok,
            "health": health_payload,
            "analyze_status": analyze_response.status_code,
            "analyze_body": analyze_response.text,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if analyze_response.ok else 1
    finally:
        stop_process(proc)


if __name__ == "__main__":
    raise SystemExit(main())
