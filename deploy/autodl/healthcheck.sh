#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${ROOT_DIR}"

VENV_DIR="${VENV_DIR:-.venv}"
SUPERVISOR_CONF="${SUPERVISOR_CONF:-deploy/autodl/supervisord.conf}"
API_URL="${API_URL:-http://127.0.0.1:8012}"
HEARTBEAT_PATH="${SCHEDULER_HEARTBEAT_PATH:-storage/quant/scheduler/heartbeat.json}"
HEARTBEAT_MAX_AGE_SECONDS="${HEARTBEAT_MAX_AGE_SECONDS:-300}"

if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
  echo "Missing ${VENV_DIR}/bin/python. Run: bash deploy/autodl/start.sh" >&2
  exit 1
fi

if [[ -x "${VENV_DIR}/bin/supervisorctl" ]]; then
  "${VENV_DIR}/bin/supervisorctl" -c "${SUPERVISOR_CONF}" status
fi

"${VENV_DIR}/bin/python" - "${API_URL}" "${HEARTBEAT_PATH}" "${HEARTBEAT_MAX_AGE_SECONDS}" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

api_url, heartbeat_path, max_age_raw = sys.argv[1:4]
max_age = int(max_age_raw)


def fetch(path: str, *, method: str = "GET") -> tuple[int, str]:
    request = Request(api_url.rstrip("/") + path, method=method)
    with urlopen(request, timeout=10) as response:
        return int(response.status), response.read().decode("utf-8", errors="replace")


failed = False

try:
    status, body = fetch("/livez")
    print(f"livez_status={status}")
    if status >= 400:
        failed = True
except URLError as exc:
    print(f"livez_error={exc}")
    failed = True

try:
    status, body = fetch("/api/v1/ops/online-status")
    print(f"online_status_status={status}")
    if status < 400:
        payload = json.loads(body)
        scheduler = payload.get("scheduler", {}) if isinstance(payload, dict) else {}
        heartbeat = scheduler.get("heartbeat", {}) if isinstance(scheduler, dict) else {}
        print(f"scheduler_heartbeat_status={heartbeat.get('status', '<missing>')}")
        print(f"scheduler_owner={payload.get('config', {}).get('scheduler_owner', '<missing>') if isinstance(payload, dict) else '<missing>'}")
except Exception as exc:
    print(f"online_status_error={exc}")
    failed = True

path = Path(heartbeat_path)
if path.exists():
    try:
        payload = json.loads(path.read_text(errors="ignore"))
        raw = str(payload.get("updated_at") or "")
        updated_at = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - updated_at.astimezone(timezone.utc)).total_seconds()
        print(f"heartbeat_age_seconds={int(age)}")
        if age > max_age:
            failed = True
    except Exception as exc:
        print(f"heartbeat_parse_error={exc}")
        failed = True
else:
    print(f"heartbeat_missing={heartbeat_path}")
    failed = True

raise SystemExit(1 if failed else 0)
PY

if [[ "${RECOVER:-0}" == "1" ]]; then
  "${VENV_DIR}/bin/python" - "${API_URL}" <<'PY'
import sys
from urllib.request import Request, urlopen

api_url = sys.argv[1].rstrip("/")
request = Request(api_url + "/api/v1/ops/scheduler/recover", method="POST")
with urlopen(request, timeout=30) as response:
    print(f"recover_status={response.status}")
    print(response.read().decode("utf-8", errors="replace")[:2000])
PY
fi
