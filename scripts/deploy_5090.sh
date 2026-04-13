#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-${ROOT_DIR}/docker-compose.5090.yml}"
PYTHON_BIN="${PYTHON_BIN:-python}"
HEALTHCHECK_JSON="${HEALTHCHECK_JSON:-${ROOT_DIR}/storage/quant/deploy_5090_health.json}"
HEALTHCHECK_RETRIES="${HEALTHCHECK_RETRIES:-20}"
HEALTHCHECK_DELAY="${HEALTHCHECK_DELAY:-10}"

if [[ ! -f "${ROOT_DIR}/.env" ]]; then
  echo "Missing .env in ${ROOT_DIR}" >&2
  exit 1
fi

if [[ ! -f "${COMPOSE_FILE}" ]]; then
  echo "Compose file not found: ${COMPOSE_FILE}" >&2
  exit 1
fi

command -v docker >/dev/null 2>&1 || { echo "docker is required" >&2; exit 1; }

echo "[deploy_5090] Building and starting services..."
docker compose -f "${COMPOSE_FILE}" up -d --build

echo "[deploy_5090] Waiting for healthcheck..."
"${PYTHON_BIN}" "${ROOT_DIR}/scripts/healthcheck_5090.py" \
  --retries "${HEALTHCHECK_RETRIES}" \
  --retry-delay "${HEALTHCHECK_DELAY}" \
  --json-out "${HEALTHCHECK_JSON}"

echo "[deploy_5090] Deployment healthy."
