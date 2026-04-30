#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${ROOT_DIR}"

VENV_DIR="${VENV_DIR:-.venv}"
SUPERVISOR_CONF="${SUPERVISOR_CONF:-deploy/autodl/supervisord.conf}"

mkdir -p logs runtime/supervisor storage/quant/scheduler storage/quant/market_data storage/quant/model_registry storage/quant/paper_feedback

find_python() {
  if [[ -n "${PYTHON_BIN:-}" ]] && "${PYTHON_BIN}" - <<'PY' >/dev/null 2>&1; then
import sys
raise SystemExit(0 if sys.version_info >= (3, 11) else 1)
PY
    printf '%s\n' "${PYTHON_BIN}"
    return 0
  fi

  local candidate
  for candidate in python3.11 python3 python; do
    if command -v "${candidate}" >/dev/null 2>&1 && "${candidate}" - <<'PY' >/dev/null 2>&1; then
import sys
raise SystemExit(0 if sys.version_info >= (3, 11) else 1)
PY
      command -v "${candidate}"
      return 0
    fi
  done
  return 1
}

bootstrap_venv() {
  if [[ -x "${VENV_DIR}/bin/python" ]]; then
    return 0
  fi

  local py_bin
  if py_bin="$(find_python)"; then
    "${py_bin}" -m venv "${VENV_DIR}"
    return 0
  fi

  if command -v conda >/dev/null 2>&1; then
    conda create -y -p "${ROOT_DIR}/${VENV_DIR}" python=3.11 pip
    return 0
  fi

  echo "Python >= 3.11 was not found, and conda is unavailable." >&2
  exit 1
}

write_env_if_missing() {
  if [[ -f .env ]]; then
    return 0
  fi
  cp deploy/autodl/env.paper.example .env
  chmod 600 .env || true
  echo "Created .env from deploy/autodl/env.paper.example. Fill ALPACA_API_KEY and ALPACA_API_SECRET on the AutoDL host before enabling real paper submissions."
}

print_safe_env_status() {
  "${VENV_DIR}/bin/python" - <<'PY'
from pathlib import Path
import sys

path = Path(".env")
values = {}
if path.exists():
    for line in path.read_text(errors="ignore").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#") or "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        values[key.strip()] = value.strip().strip("\"'")

for key in [
    "ALPACA_API_KEY",
    "ALPACA_API_SECRET",
    "ALPACA_PAPER",
    "ALPACA_ENABLE_LIVE_TRADING",
    "SCHEDULER_AUTO_SUBMIT",
    "PAPER_REWARD_SUBMIT_ENABLED",
    "API_HEALTHCHECK_REQUIRED_COMPONENTS",
]:
    value = values.get(key, "")
    if key in {"ALPACA_API_KEY", "ALPACA_API_SECRET"}:
        value = "<set>" if value else "<missing>"
    elif not value:
        value = "<missing>"
    print(f"{key}={value}")

errors = []
warnings = []
if values.get("ALPACA_ENABLE_LIVE_TRADING", "").lower() == "true":
    errors.append("ALPACA_ENABLE_LIVE_TRADING must stay false in AutoDL paper fallback.")
if values.get("PAPER_REWARD_SUBMIT_ENABLED", "").lower() == "true":
    errors.append("PAPER_REWARD_SUBMIT_ENABLED must stay false unless it is wired through the scheduler idempotency gate.")
if values.get("API_HEALTHCHECK_REQUIRED_COMPONENTS", "") != "api":
    warnings.append("API_HEALTHCHECK_REQUIRED_COMPONENTS should be api while Qdrant is degraded on AutoDL.")
if values.get("SCHEDULER_OWNER", "") != "quant-scheduler":
    warnings.append("SCHEDULER_OWNER should be quant-scheduler for the single paper submit owner.")
if values.get("SCHEDULER_AUTO_SUBMIT", "").lower() != "true":
    warnings.append("SCHEDULER_AUTO_SUBMIT is not true; scheduler will not submit paper orders automatically.")

for item in warnings:
    print(f"WARNING: {item}")
for item in errors:
    print(f"ERROR: {item}", file=sys.stderr)
if errors:
    raise SystemExit(1)
PY
}

bootstrap_venv

if [[ "${SKIP_PIP_INSTALL:-0}" != "1" ]]; then
  "${VENV_DIR}/bin/python" -m pip install --upgrade pip setuptools wheel
  "${VENV_DIR}/bin/python" -m pip install -r requirements.txt supervisor
fi

write_env_if_missing
print_safe_env_status

if "${VENV_DIR}/bin/supervisorctl" -c "${SUPERVISOR_CONF}" status >/dev/null 2>&1; then
  "${VENV_DIR}/bin/supervisorctl" -c "${SUPERVISOR_CONF}" reread
  "${VENV_DIR}/bin/supervisorctl" -c "${SUPERVISOR_CONF}" update
  "${VENV_DIR}/bin/supervisorctl" -c "${SUPERVISOR_CONF}" restart api quant-scheduler
else
  rm -f runtime/supervisor/supervisor.sock runtime/supervisor/supervisord.pid
  "${VENV_DIR}/bin/supervisord" -c "${SUPERVISOR_CONF}"
fi

"${VENV_DIR}/bin/supervisorctl" -c "${SUPERVISOR_CONF}" status
echo "AutoDL paper fallback started. Run: bash deploy/autodl/healthcheck.sh"
