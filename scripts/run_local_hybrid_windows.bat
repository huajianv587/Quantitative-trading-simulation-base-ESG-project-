@echo off
setlocal

cd /d "%~dp0.."

if not exist ".venv\Scripts\python.exe" (
  echo [run] Missing .venv. Run scripts\bootstrap_local_windows.bat first.
  exit /b 1
)

if not exist ".env" (
  echo [run] Missing .env file. Copy .env.example to .env and fill in your settings first.
  exit /b 1
)

set APP_MODE=hybrid
set LLM_BACKEND_MODE=remote

echo [run] Starting local API in hybrid remote-GPU mode.
echo [run] APP_MODE=%APP_MODE%
echo [run] LLM_BACKEND_MODE=%LLM_BACKEND_MODE%
echo [run] Fallback order: remote ^> DeepSeek ^> OpenAI

".venv\Scripts\python.exe" -m uvicorn gateway.main:app --host 0.0.0.0 --port 8000 --reload
