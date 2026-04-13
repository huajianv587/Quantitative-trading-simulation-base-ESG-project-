#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-${ROOT_DIR}/docker-compose.5090.yml}"
PYTHON_BIN="${PYTHON_BIN:-python}"
HEALTHCHECK_JSON="${HEALTHCHECK_JSON:-${ROOT_DIR}/storage/quant/autorecover_5090_health.json}"
RETRY_DELAY="${RETRY_DELAY:-12}"

echo "[autorecover_5090] Running healthcheck..."
set +e
"${PYTHON_BIN}" "${ROOT_DIR}/scripts/healthcheck_5090.py" --retries 1 --json-out "${HEALTHCHECK_JSON}"
HEALTH_STATUS=$?
set -e

if [[ ${HEALTH_STATUS} -eq 0 ]]; then
  echo "[autorecover_5090] All components healthy."
  exit 0
fi

SERVICES_TO_RESTART="$("${PYTHON_BIN}" - "${HEALTHCHECK_JSON}" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
data = json.loads(path.read_text(encoding="utf-8"))
components = data.get("components", {})
mapping = {
    "api": "api",
    "remote_llm": "remote-llm",
    "qdrant": "qdrant",
    "quant_scheduler": "quant-scheduler",
}
services = []
for key, service in mapping.items():
    if not bool((components.get(key) or {}).get("ok")):
        services.append(service)
print(" ".join(dict.fromkeys(services)))
PY
)"

if [[ -z "${SERVICES_TO_RESTART}" ]]; then
  echo "[autorecover_5090] No restart candidates found." >&2
  exit 1
fi

echo "[autorecover_5090] Restarting: ${SERVICES_TO_RESTART}"
docker compose -f "${COMPOSE_FILE}" restart ${SERVICES_TO_RESTART}
sleep "${RETRY_DELAY}"

echo "[autorecover_5090] Re-running healthcheck..."
"${PYTHON_BIN}" "${ROOT_DIR}/scripts/healthcheck_5090.py" --retries 6 --retry-delay "${RETRY_DELAY}" --json-out "${HEALTHCHECK_JSON}"
