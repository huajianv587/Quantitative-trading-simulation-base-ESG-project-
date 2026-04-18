#!/usr/bin/env bash
set -euo pipefail

# Stage 1 5090 driver:
# bootstrap -> full-suite preflight -> data audit -> ESG/RL paper-run
# -> full model suite -> final artifact check.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

if [ -d "/root/miniconda3/bin" ]; then
  export PATH="/root/miniconda3/bin:${PATH}"
fi

SMOKE="${SMOKE:-0}"
ALLOW_CPU_SMOKE="${ALLOW_CPU_SMOKE:-0}"
RUN_ID="${RUN_ID:-stage1_$(date -u +%Y%m%dT%H%M%SZ)}"
FULL_SUITE_JOBS="${FULL_SUITE_JOBS:-all}"

if [ "${SMOKE}" = "1" ]; then
  export TOTAL_STEPS="${TOTAL_STEPS:-120}"
  export EPISODES="${EPISODES:-3}"
else
  export TOTAL_STEPS="${TOTAL_STEPS:-500000}"
  export EPISODES="${EPISODES:-50}"
fi

echo "[stage1] repo=${ROOT_DIR}"
echo "[stage1] run_id=${RUN_ID} smoke=${SMOKE} total_steps=${TOTAL_STEPS} episodes=${EPISODES}"

if [ "${SKIP_BOOTSTRAP:-0}" != "1" ]; then
  bash scripts/autodl_bootstrap.sh
fi

if [ -d ".venv" ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

cpu_smoke_args=()
if [ "${ALLOW_CPU_SMOKE}" = "1" ]; then
  cpu_smoke_args=(--allow-cpu-smoke)
fi

preflight_args=(
  --jobs "${FULL_SUITE_JOBS}"
  --min-free-gb "${MIN_FREE_GB:-20}"
  --output-path "storage/full-training-runs/${RUN_ID}/preflight/full_model_preflight.json"
)
suite_args=(
  --run-id "${RUN_ID}"
  --jobs "${FULL_SUITE_JOBS}"
  --resume
  --skip-existing
)

if [ "${SMOKE}" = "1" ]; then
  preflight_args+=(--smoke "${cpu_smoke_args[@]}")
  suite_args+=(--smoke --dry-run "${cpu_smoke_args[@]}")
else
  preflight_args+=(--require-cuda)
  suite_args+=(--require-cuda --promote-latest)
fi

echo "[stage1] full-suite preflight"
python training/full_model_preflight.py "${preflight_args[@]}"

echo "[stage1] full-suite data audit"
python training/full_model_data_audit.py \
  --jobs "${FULL_SUITE_JOBS}" \
  --output-dir "storage/full-training-runs/${RUN_ID}/data_audit"

echo "[stage1] ESG/RL paper-run"
RESUME="${RESUME:-1}" ALLOW_CPU_SMOKE="${ALLOW_CPU_SMOKE}" SMOKE="${SMOKE}" \
  bash scripts/autodl_run_paper_experiments.sh

echo "[stage1] full model suite"
python training/train_full_model_suite.py "${suite_args[@]}"

echo "[stage1] final artifact check"
python - "${RUN_ID}" <<'PY'
import json
import sys
from pathlib import Path

run_id = sys.argv[1]
required = [
    Path(f"storage/full-training-runs/{run_id}/full_training_manifest.json"),
    Path(f"storage/full-training-runs/{run_id}/data_audit/full_model_data_audit.json"),
    Path("storage/quant/rl-experiments/paper-run/formula_v2/sample_full_2022_2025/summary"),
    Path("storage/quant/rl-experiments/paper-run/formula_v2_1/sample_full_2022_2025/summary"),
    Path("storage/quant/rl-experiments/paper-run/formula_v2/sample_post_esg_effective/summary"),
    Path("storage/quant/rl-experiments/paper-run/formula_v2_1/sample_post_esg_effective/summary"),
]
missing = [str(path) for path in required if not path.exists()]
payload = {"run_id": run_id, "status": "fail" if missing else "pass", "missing": missing}
Path(f"storage/full-training-runs/{run_id}/final_artifact_check.json").write_text(
    json.dumps(payload, ensure_ascii=False, indent=2),
    encoding="utf-8",
)
print(json.dumps(payload, ensure_ascii=False, indent=2))
if missing:
    raise SystemExit(1)
PY

echo "[stage1] complete run_id=${RUN_ID}"
