#!/usr/bin/env python3
"""
Staging preflight and smoke checks for ESG Agentic RAG Copilot.

Usage examples:
  python scripts/staging_check.py preflight
  python scripts/staging_check.py up --require-module rag --require-module esg_scorer
  python scripts/staging_check.py compose
  python scripts/staging_check.py smoke --base-url http://localhost:8000
  python scripts/staging_check.py all --require-module rag --require-module esg_scorer
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_FILE = PROJECT_ROOT / ".env"
DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_ENDPOINTS = ("/health", "/dashboard/overview")
REQUIRED_ENV_VARS = (
    "OPENAI_API_KEY",
    "SUPABASE_URL",
)
OPTIONAL_ENV_GROUPS = (
    ("SUPABASE_API_KEY", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_KEY"),
    ("ANTHROPIC_API_KEY", "DEEPSEEK_API_KEY"),
)
EXPECTED_PATHS = (
    PROJECT_ROOT / "docker-compose.yml",
    PROJECT_ROOT / "gateway" / "Dockerfile",
    PROJECT_ROOT / "deploy" / "nginx.conf",
    PROJECT_ROOT / "frontend" / "index.html",
)
EXPECTED_DIRS = (
    PROJECT_ROOT / "data",
    PROJECT_ROOT / "gateway",
    PROJECT_ROOT / "frontend",
    PROJECT_ROOT / "configs",
)
DEFAULT_PORTS = (80, 8000, 6333)


def ok(message: str) -> None:
    print(f"[OK] {message}")


def warn(message: str) -> None:
    print(f"[WARN] {message}")


def fail(message: str) -> None:
    print(f"[FAIL] {message}")


def mask_value(value: str) -> str:
    if not value:
        return "<empty>"
    if len(value) <= 6:
        return "*" * len(value)
    return f"{value[:3]}***{value[-3:]}"


def load_env_file(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not path.exists():
        return env

    for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip().strip("\"'")
    return env


def run_command(command: list[str], timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )


def check_port(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def preflight(env_file: Path) -> bool:
    success = True
    env_values = load_env_file(env_file)

    print("== Preflight ==")
    if env_file.exists():
        ok(f"env file present: {env_file.name}")
    else:
        fail(f"env file missing: {env_file}")
        return False

    for path in EXPECTED_PATHS:
        if path.exists():
            ok(f"file present: {path.relative_to(PROJECT_ROOT)}")
        else:
            fail(f"missing file: {path.relative_to(PROJECT_ROOT)}")
            success = False

    for path in EXPECTED_DIRS:
        if path.exists():
            ok(f"directory present: {path.relative_to(PROJECT_ROOT)}")
        else:
            fail(f"missing directory: {path.relative_to(PROJECT_ROOT)}")
            success = False

    for key in REQUIRED_ENV_VARS:
        value = env_values.get(key) or os.getenv(key, "")
        if value:
            ok(f"env present: {key}={mask_value(value)}")
        else:
            fail(f"required env missing: {key}")
            success = False

    for group in OPTIONAL_ENV_GROUPS:
        resolved = None
        for key in group:
            value = env_values.get(key) or os.getenv(key, "")
            if value:
                resolved = (key, value)
                break
        if resolved:
            ok(f"env group satisfied: {resolved[0]}={mask_value(resolved[1])}")
        else:
            fail(f"missing env group: one of {', '.join(group)}")
            success = False

    supabase_url = env_values.get("SUPABASE_URL") or os.getenv("SUPABASE_URL", "")
    if supabase_url.startswith("https://") and ".supabase.co" in supabase_url:
        ok("SUPABASE_URL format looks valid")
    else:
        fail("SUPABASE_URL format is invalid")
        success = False

    cors_raw = env_values.get("CORS_ORIGINS") or os.getenv("CORS_ORIGINS", "")
    if cors_raw:
        try:
            parsed = json.loads(cors_raw)
            if isinstance(parsed, list):
                ok("CORS_ORIGINS is valid JSON array")
            else:
                warn("CORS_ORIGINS is set but not a JSON array")
        except json.JSONDecodeError:
            warn("CORS_ORIGINS is not JSON; app will fall back to CSV parsing")
    else:
        warn("CORS_ORIGINS not set; app will default to '*'")

    docker_result = run_command(["docker", "--version"], timeout=15)
    if docker_result.returncode == 0:
        ok(docker_result.stdout.strip())
    else:
        fail(docker_result.stderr.strip() or "docker unavailable")
        success = False

    compose_result = run_command(["docker", "compose", "version"], timeout=15)
    if compose_result.returncode == 0:
        ok(compose_result.stdout.strip())
    else:
        fail(compose_result.stderr.strip() or "docker compose unavailable")
        success = False

    config_result = run_command(["docker", "compose", "config"], timeout=30)
    if config_result.returncode == 0:
        ok("docker compose config parsed successfully")
    else:
        fail("docker compose config failed")
        print(config_result.stderr or config_result.stdout)
        success = False

    for port in DEFAULT_PORTS:
        if check_port(port):
            warn(f"port already in use: {port}")
        else:
            ok(f"port available: {port}")

    return success


def compose_health() -> bool:
    print("== Compose ==")
    result = run_command(["docker", "compose", "ps", "--format", "json"], timeout=30)
    if result.returncode != 0:
        fail("failed to query docker compose status")
        print(result.stderr or result.stdout)
        return False

    raw = result.stdout.strip()
    if not raw:
        fail("docker compose ps returned no services")
        return False

    services = []
    try:
        parsed = json.loads(raw)
        services = [parsed] if isinstance(parsed, dict) else parsed
    except json.JSONDecodeError:
        # docker compose ps --format json may emit newline-delimited JSON objects.
        services = [json.loads(line) for line in raw.splitlines() if line.strip()]

    success = True
    for service in services:
        name = service.get("Service") or service.get("Name") or "<unknown>"
        state = service.get("State") or "<unknown>"
        health = service.get("Health") or "n/a"
        if state == "running" and health in {"healthy", "n/a", ""}:
            ok(f"{name}: state={state}, health={health}")
        else:
            fail(f"{name}: state={state}, health={health}")
            success = False

    return success


def compose_up(base_url: str, build: bool, require_modules: list[str], retries: int, delay: float) -> bool:
    print("== Compose Up ==")
    command = ["docker", "compose", "up", "-d"]
    if build:
        command.append("--build")

    result = run_command(command, timeout=1800)
    if result.returncode != 0:
        fail("docker compose up failed")
        print(result.stderr or result.stdout)
        return False

    ok("docker compose up completed")
    health_ok = compose_health()
    smoke_ok = smoke(base_url, require_modules, retries, delay)
    return health_ok and smoke_ok


def http_json(url: str, timeout: int = 20) -> tuple[int, str]:
    request = Request(url, headers={"User-Agent": "staging-check/1.0"})
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.getcode(), response.read().decode("utf-8", errors="ignore")
    except HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="ignore")
    except URLError as exc:
        raise RuntimeError(str(exc)) from exc


def smoke(base_url: str, require_modules: list[str], retries: int, delay: float) -> bool:
    print("== Smoke ==")
    success = True

    for endpoint in DEFAULT_ENDPOINTS:
        last_error = None
        for attempt in range(1, retries + 1):
            try:
                status, _ = http_json(f"{base_url}{endpoint}")
                if status == 200:
                    ok(f"{endpoint} -> 200")
                    break
                last_error = f"unexpected status {status}"
            except Exception as exc:  # pragma: no cover - defensive
                last_error = str(exc)
            time.sleep(delay)
        else:
            fail(f"{endpoint} failed after {retries} attempts: {last_error}")
            success = False

    try:
        status, body = http_json(f"{base_url}/health")
        if status != 200:
            fail("/health did not return 200 for module check")
            return False
        payload = json.loads(body)
        modules = payload.get("modules", {})
        for module_name in require_modules:
            if modules.get(module_name):
                ok(f"required module ready: {module_name}")
            else:
                fail(f"required module not ready: {module_name}")
                success = False
    except Exception as exc:
        fail(f"unable to parse /health payload: {exc}")
        return False

    return success


def main() -> int:
    parser = argparse.ArgumentParser(description="Run staging checks for ESG Agentic RAG Copilot")
    parser.add_argument("mode", choices=["preflight", "up", "compose", "smoke", "all"])
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--require-module", action="append", default=[])
    parser.add_argument("--retries", type=int, default=10)
    parser.add_argument("--delay", type=float, default=3.0)
    parser.add_argument("--skip-build", action="store_true")
    args = parser.parse_args()

    overall = True
    if args.mode in {"preflight", "all"}:
        overall = preflight(args.env_file) and overall
    if args.mode == "up":
        overall = preflight(args.env_file) and overall
        overall = compose_up(args.base_url, not args.skip_build, args.require_module, args.retries, args.delay) and overall
    if args.mode in {"compose", "all"}:
        overall = compose_health() and overall
    if args.mode in {"smoke", "all"}:
        overall = smoke(args.base_url, args.require_module, args.retries, args.delay) and overall

    return 0 if overall else 1


if __name__ == "__main__":
    sys.exit(main())
