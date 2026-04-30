#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${ROOT_DIR}"

VENV_DIR="${VENV_DIR:-.venv}"
SUPERVISOR_CONF="${SUPERVISOR_CONF:-deploy/autodl/supervisord.conf}"

if [[ ! -x "${VENV_DIR}/bin/supervisorctl" ]]; then
  echo "supervisorctl not found in ${VENV_DIR}; nothing to stop."
  exit 0
fi

"${VENV_DIR}/bin/supervisorctl" -c "${SUPERVISOR_CONF}" shutdown || true
rm -f runtime/supervisor/supervisor.sock runtime/supervisor/supervisord.pid
