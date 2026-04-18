#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

if [ -d ".venv" ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

PYTHON_BIN="${PYTHON_BIN:-python3}"
if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  PYTHON_BIN="python"
fi

export QWEN_MODEL_NAME="${QWEN_MODEL_NAME:-Qwen/Qwen2.5-7B-Instruct}"
export HF_ENDPOINT="${HF_ENDPOINT:-https://hf-mirror.com}"
export HF_HOME="${HF_HOME:-${ROOT_DIR}/.hf_cache}"
export QWEN_CACHE_REPORT="${QWEN_CACHE_REPORT:-storage/full-training-runs/qwen_base_model_cache_check.json}"

args=(
  --model-name "${QWEN_MODEL_NAME}"
  --output-path "${QWEN_CACHE_REPORT}"
)

if [ -n "${QWEN_REVISION:-}" ]; then
  args+=(--revision "${QWEN_REVISION}")
fi

if [ -n "${QWEN_LOCAL_DIR:-}" ]; then
  args+=(--local-dir "${QWEN_LOCAL_DIR}")
fi

if [ "${QWEN_DRY_RUN:-0}" = "1" ] || [ "${SKIP_QWEN_DOWNLOAD:-0}" = "1" ]; then
  args+=(--dry-run)
elif [ "${QWEN_USE_HF_CLI:-0}" = "1" ] && command -v hf >/dev/null 2>&1; then
  hf_args=(download "${QWEN_MODEL_NAME}" --cache-dir "${HF_HOME}")
  if [ -n "${QWEN_REVISION:-}" ]; then
    hf_args+=(--revision "${QWEN_REVISION}")
  fi
  if [ -n "${QWEN_LOCAL_DIR:-}" ]; then
    hf_args+=(--local-dir "${QWEN_LOCAL_DIR}")
  fi
  echo "[qwen] downloading with hf CLI"
  hf "${hf_args[@]}"
else
  args+=(--download)
fi

echo "[qwen] model=${QWEN_MODEL_NAME}"
echo "[qwen] hf_endpoint=${HF_ENDPOINT}"
echo "[qwen] hf_home=${HF_HOME}"
"${PYTHON_BIN}" training/qwen_base_model_cache.py "${args[@]}"
