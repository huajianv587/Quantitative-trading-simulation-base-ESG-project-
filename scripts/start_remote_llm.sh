#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -f ".env" ]; then
  echo "[remote-llm] Missing .env file. Copy .env.example to .env first."
  exit 1
fi

if [ -x ".venv/bin/python" ]; then
  PYTHON_BIN=".venv/bin/python"
else
  PYTHON_BIN="python"
fi

echo "[remote-llm] Starting remote LLM service using .env configuration..."
"$PYTHON_BIN" model-serving/remote_llm_server.py

