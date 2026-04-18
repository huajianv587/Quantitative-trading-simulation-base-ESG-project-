#!/usr/bin/env bash
set -euo pipefail

# Formal AutoDL driver. It assumes scripts/autodl_bootstrap.sh already ran.
# Optional env:
#   RUN_EMBED=1              call OpenAI embeddings before scoring
#   SMOKE=1                  use small training defaults for a cloud smoke pass
#   TOTAL_STEPS=500000       formal trainer steps; SMOKE default is 120
#   EPISODES=50              formal episodes; SMOKE default is 3
#   SAMPLES="full_2022_2025 post_esg_effective"
#   SEEDS="42,123,456"       formal seeds for every group, including baselines
#   RESUME=1                 skip completed group/seed runs
#   ALLOW_CPU_SMOKE=1        explicitly allow CPU-only smoke checks

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

if [ -d "/root/miniconda3/bin" ]; then
  export PATH="/root/miniconda3/bin:${PATH}"
fi

if [ -d ".venv" ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

SMOKE="${SMOKE:-0}"
if [ -n "${QUICK_STEPS:-}" ] && [ -z "${TOTAL_STEPS:-}" ]; then
  echo "[paper-run][warn] QUICK_STEPS is deprecated; using it as TOTAL_STEPS for this run."
  TOTAL_STEPS="${QUICK_STEPS}"
fi
if [ "${SMOKE}" = "1" ]; then
  TOTAL_STEPS="${TOTAL_STEPS:-120}"
  EPISODES="${EPISODES:-3}"
else
  TOTAL_STEPS="${TOTAL_STEPS:-500000}"
  EPISODES="${EPISODES:-50}"
fi

python - <<'PY'
import os
import sys

print(f"[paper-run] python={sys.version.split()[0]}")
try:
    import torch
except Exception as exc:
    raise SystemExit(f"[paper-run][fatal] torch unavailable: {exc}")
cuda = bool(torch.cuda.is_available())
print(f"[paper-run] torch={torch.__version__} cuda={getattr(torch.version, 'cuda', None)} gpu={cuda}")
if cuda:
    print(f"[paper-run] gpu_name={torch.cuda.get_device_name(0)}")
elif os.getenv("ALLOW_CPU_SMOKE") == "1":
    print("[paper-run][warn] CUDA is not visible; ALLOW_CPU_SMOKE=1 permits a CPU smoke pass only.")
else:
    raise SystemExit("[paper-run][fatal] CUDA is not visible. Set ALLOW_CPU_SMOKE=1 only for CPU smoke checks.")
PY

SAMPLES="${SAMPLES:-full_2022_2025 post_esg_effective}"
GROUPS_BASELINE="B1_buyhold B2_macd B3_sac_noesg"
GROUPS_ESG="B4_sac_esg OURS_full 6a_no_esg_obs 6b_no_esg_reward 6c_no_regime"
ALL_GROUPS="${GROUPS_BASELINE} ${GROUPS_ESG}"
SEEDS="${SEEDS:-42,123,456}"
RESUME="${RESUME:-1}"
EXPECTED_MANIFEST_PATH="${EXPECTED_MANIFEST_PATH:-storage/quant/rl-experiments/paper-run/protocol/expected_run_manifest.json}"

python scripts/quant_rl_expected_run_manifest.py build \
  --namespace-root "storage/quant/rl-experiments/paper-run" \
  --output-path "${EXPECTED_MANIFEST_PATH}" \
  --samples "${SAMPLES}" \
  --formulas "v2 v2_1" \
  --groups "${ALL_GROUPS}" \
  --seeds "${SEEDS}"

embed_flag=()
if [ "${RUN_EMBED:-0}" = "1" ]; then
  embed_flag=(--embed)
fi

resume_flag=()
if [ "${RESUME}" = "1" ]; then
  resume_flag=(--resume)
fi

cpu_flag=()
if [ "${ALLOW_CPU_SMOKE:-0}" = "1" ]; then
  cpu_flag=(--allow-cpu-smoke)
fi

for sample in ${SAMPLES}; do
  echo "[paper-run] building frozen inputs and datasets for ${sample}"
  python scripts/run_esg_rl_2022_2025_pipeline.py \
    --run-namespace paper-run \
    --sample "${sample}" \
    --corpus-root esg_reports \
    --build-datasets \
    "${embed_flag[@]}"

  echo "[paper-run] final preflight sample=${sample}"
  python scripts/quant_rl_paper_preflight.py \
    --namespace paper-run \
    --sample "${sample}" \
    --require-cuda \
    "${cpu_flag[@]}" \
    --output-path "storage/quant/rl-experiments/paper-run/protocol/preflight_${sample}.json"

  protocol_file="storage/quant/rl-experiments/paper-run/protocol/frozen_inputs_${sample}.json"
  read -r no_esg_dataset house_esg_dataset < <(python - "${sample}" <<'PY'
import json
import sys
from pathlib import Path

sample = sys.argv[1]
payload = json.loads(Path(f"storage/quant/rl-experiments/paper-run/summary/esg_rl_2022_2025_pipeline_{sample}.json").read_text(encoding="utf-8"))
datasets = payload["datasets"]
print(datasets["no_esg"]["merged_dataset_path"], datasets["house_esg"]["merged_dataset_path"])
PY
)

  for formula in v2 v2_1; do
    sample_root="storage/quant/rl-experiments/paper-run/formula_${formula}/sample_${sample}"
    mkdir -p "${sample_root}/summary" "${sample_root}/logs"

    for group in ${GROUPS_BASELINE}; do
      log_path="${sample_root}/logs/${group}.log"
      echo "[paper-run] group=${group} formula=${formula} sample=${sample} dataset=${no_esg_dataset}"
      python scripts/quant_rl_experiment_suite.py \
        --run-namespace paper-run \
        --sample "${sample}" \
        --formula-mode "${formula}" \
        --dataset-path "${no_esg_dataset}" \
        --groups "${group}" \
        --episodes "${EPISODES}" \
        --total-steps "${TOTAL_STEPS}" \
        --protocol-file "${protocol_file}" \
        --seeds "${SEEDS}" \
        --sample-output-root "${sample_root}" \
        "${resume_flag[@]}" \
        --output-summary "${sample_root}/summary/experiment_suite_${sample}_${group}_${formula}.json" \
        2>&1 | tee "${log_path}"
    done

    for group in ${GROUPS_ESG}; do
      log_path="${sample_root}/logs/${group}.log"
      echo "[paper-run] group=${group} formula=${formula} sample=${sample} dataset=${house_esg_dataset}"
      python scripts/quant_rl_experiment_suite.py \
        --run-namespace paper-run \
        --sample "${sample}" \
        --formula-mode "${formula}" \
        --dataset-path "${house_esg_dataset}" \
        --groups "${group}" \
        --episodes "${EPISODES}" \
        --total-steps "${TOTAL_STEPS}" \
        --protocol-file "${protocol_file}" \
        --seeds "${SEEDS}" \
        --sample-output-root "${sample_root}" \
        "${resume_flag[@]}" \
        --output-summary "${sample_root}/summary/experiment_suite_${sample}_${group}_${formula}.json" \
        2>&1 | tee "${log_path}"
    done

    python scripts/quant_rl_esg_contribution_report.py \
      --run-namespace paper-run \
      --sample "${sample}" \
      --formula-mode "${formula}" \
      --output-dir "${sample_root}/summary"
  done
done

python scripts/quant_rl_expected_run_manifest.py verify \
  --manifest-path "${EXPECTED_MANIFEST_PATH}" \
  --report-path "storage/quant/rl-experiments/paper-run/summary/expected_run_verification.json"

echo "[paper-run] complete total_steps=${TOTAL_STEPS} episodes=${EPISODES} smoke=${SMOKE}"
