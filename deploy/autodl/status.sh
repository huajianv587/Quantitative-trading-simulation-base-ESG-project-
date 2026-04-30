#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${ROOT_DIR}"

VENV_DIR="${VENV_DIR:-.venv}"
SUPERVISOR_CONF="${SUPERVISOR_CONF:-deploy/autodl/supervisord.conf}"

if [[ ! -x "${VENV_DIR}/bin/supervisorctl" ]]; then
  echo "supervisorctl not found in ${VENV_DIR}. Run: bash deploy/autodl/start.sh"
  exit 1
fi

"${VENV_DIR}/bin/supervisorctl" -c "${SUPERVISOR_CONF}" status

echo
echo "Recent API log:"
tail -n "${TAIL_LINES:-20}" logs/api.out.log 2>/dev/null || true

echo
echo "Recent scheduler log:"
tail -n "${TAIL_LINES:-20}" logs/scheduler.out.log 2>/dev/null || true
