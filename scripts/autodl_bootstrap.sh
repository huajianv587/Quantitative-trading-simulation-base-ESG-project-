#!/usr/bin/env bash
set -euo pipefail

# AutoDL 5090 bootstrap for the ESG/RL paper-run line.
# Run from the repository root after SSH login:
#   bash scripts/autodl_bootstrap.sh

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

# AutoDL non-interactive SSH sessions may not source /etc/profile/.bashrc.
# The selected PyTorch image places Python under /root/miniconda3/bin.
if [ -d "/root/miniconda3/bin" ]; then
  export PATH="/root/miniconda3/bin:${PATH}"
fi

echo "[bootstrap] repo=${ROOT_DIR}"
echo "[bootstrap] expected image=PyTorch 2.8.0 + Python 3.12 + Ubuntu 22.04"
echo "[bootstrap] python=$(python3 --version 2>/dev/null || python --version)"

if command -v nvidia-smi >/dev/null 2>&1; then
  nvidia-smi
else
  echo "[bootstrap][warn] nvidia-smi not found; continuing so CPU-only smoke can still run."
fi

PYTHON_BIN="${PYTHON_BIN:-python3}"
if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  PYTHON_BIN="python"
fi

if [ ! -d ".venv" ]; then
  # AutoDL PyTorch images already ship the correct CUDA/PyTorch stack.
  # Reuse system site packages so the venv sees torch 2.8 instead of
  # downloading another multi-GB wheel or accidentally changing CUDA builds.
  "${PYTHON_BIN}" -m venv --system-site-packages .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip wheel setuptools
python - <<'PY'
import sys

version = sys.version_info
print(f"[bootstrap] venv_python={sys.version}")
if version < (3, 11):
    raise SystemExit("[bootstrap][fatal] Python 3.11+ is required.")
if version >= (3, 13):
    raise SystemExit("[bootstrap][fatal] Python 3.13 is not supported for this paper-run.")
PY

python - <<'PY'
try:
    import torch
except Exception as exc:
    raise SystemExit(
        "[bootstrap][fatal] torch is not visible in this environment. "
        "Use the AutoDL PyTorch 2.8.0 image, or set up a CUDA torch wheel first. "
        f"detail={exc}"
    )

print("[bootstrap] torch_version=" + str(torch.__version__))
print("[bootstrap] torch_cuda=" + str(getattr(torch.version, "cuda", None)))
print("[bootstrap] cuda_available=" + str(torch.cuda.is_available()))
if torch.cuda.is_available():
    print("[bootstrap] gpu_name=" + str(torch.cuda.get_device_name(0)))
if not torch.__version__.startswith("2.8"):
    print("[bootstrap][warn] Expected torch 2.8.x from the selected AutoDL image.")
PY

# The venv is created with --system-site-packages, so torch>=2.1.1 in
# requirements.txt is already satisfied by the base image and is not reinstalled.
python -m pip install -r requirements.txt
python -m pip install -r training/requirements.txt
if [ -f "training/cloud_assets/requirements_cloud_extra.txt" ]; then
  python -m pip install -r training/cloud_assets/requirements_cloud_extra.txt
fi

mkdir -p \
  storage/esg_corpus \
  storage/rag/esg_reports_openai_3072 \
  storage/quant/rl-experiments/paper-run \
  storage/quant/remote-sync

python - <<'PY'
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
required = ["OPENAI_API_KEY", "ALPACA_API_KEY", "ALPACA_SECRET_KEY"]
status = {key: bool(os.getenv(key)) for key in required}
print("[bootstrap] secret_presence=" + str(status))
missing = [key for key, ok in status.items() if not ok]
if missing:
    print("[bootstrap][warn] missing secrets: " + ", ".join(missing))
print("[bootstrap] esg_reports_exists=" + str(Path("esg_reports").exists()))
print("[bootstrap] rag_embeddings_exists=" + str(Path("storage/rag/esg_reports_openai_3072/embeddings.jsonl").exists()))
PY

python -m py_compile \
  gateway/quant/esg_house_score.py \
  scripts/esg_corpus_pipeline.py \
  scripts/run_esg_rl_2022_2025_pipeline.py \
  scripts/quant_rl_paper_preflight.py \
  scripts/quant_rl_experiment_suite.py \
  scripts/quant_rl_esg_contribution_report.py

python scripts/esg_corpus_pipeline.py rag-check --corpus-root esg_reports --evidence-chain

echo "[bootstrap] complete"
