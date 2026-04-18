#!/usr/bin/env bash
set -euo pipefail

# Formal AutoDL driver. It assumes scripts/autodl_bootstrap.sh already ran.
# Optional env:
#   RUN_EMBED=1       call OpenAI embeddings before scoring
#   QUICK_STEPS=120   quick/full trainer steps for current quant_rl trainers
#   EPISODES=30
#   SAMPLES="full_2022_2025 post_esg_effective"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

if [ -d "/root/miniconda3/bin" ]; then
  export PATH="/root/miniconda3/bin:${PATH}"
fi

if [ -d ".venv" ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

python - <<'PY'
import sys

print(f"[paper-run] python={sys.version.split()[0]}")
try:
    import torch
except Exception as exc:
    raise SystemExit(f"[paper-run][fatal] torch unavailable: {exc}")
print(f"[paper-run] torch={torch.__version__} cuda={getattr(torch.version, 'cuda', None)} gpu={torch.cuda.is_available()}")
if not torch.cuda.is_available():
    print("[paper-run][warn] CUDA is not visible; formal training will be slow and should only be used for smoke checks.")
PY

SAMPLES="${SAMPLES:-full_2022_2025 post_esg_effective}"
QUICK_STEPS="${QUICK_STEPS:-120}"
EPISODES="${EPISODES:-30}"
GROUPS_BASELINE="B1_buyhold,B2_macd,B3_sac_noesg"
GROUPS_ESG="B4_sac_esg,OURS_full,6a_no_esg_obs,6b_no_esg_reward,6c_no_regime"

embed_flag=()
if [ "${RUN_EMBED:-0}" = "1" ]; then
  embed_flag=(--embed)
fi

for sample in ${SAMPLES}; do
  echo "[paper-run] building frozen inputs and datasets for ${sample}"
  python scripts/run_esg_rl_2022_2025_pipeline.py \
    --run-namespace paper-run \
    --sample "${sample}" \
    --corpus-root esg_reports \
    --build-datasets \
    "${embed_flag[@]}"

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
    echo "[paper-run] baseline groups formula=${formula} no-ESG dataset=${no_esg_dataset}"
    python scripts/quant_rl_experiment_suite.py \
      --run-namespace paper-run \
      --sample "${sample}" \
      --formula-mode "${formula}" \
      --dataset-path "${no_esg_dataset}" \
      --groups "${GROUPS_BASELINE}" \
      --episodes "${EPISODES}" \
      --total-steps "${QUICK_STEPS}" \
      --output-summary "storage/quant/rl-experiments/paper-run/formula_${formula}/summary/experiment_suite_${sample}_baseline_${formula}.json"

    echo "[paper-run] ESG groups formula=${formula} dataset=${house_esg_dataset}"
    python scripts/quant_rl_experiment_suite.py \
      --run-namespace paper-run \
      --sample "${sample}" \
      --formula-mode "${formula}" \
      --dataset-path "${house_esg_dataset}" \
      --groups "${GROUPS_ESG}" \
      --episodes "${EPISODES}" \
      --total-steps "${QUICK_STEPS}" \
      --output-summary "storage/quant/rl-experiments/paper-run/formula_${formula}/summary/experiment_suite_${sample}_${formula}.json"

    python scripts/quant_rl_esg_contribution_report.py \
      --run-namespace paper-run \
      --sample "${sample}" \
      --formula-mode "${formula}" \
      --output-dir "storage/quant/rl-experiments/paper-run/formula_${formula}/summary/${sample}"
  done
done

echo "[paper-run] complete"
