@echo off
setlocal

cd /d "%~dp0.."

call :resolve_python || exit /b 1

if not exist ".env" (
  echo [run] Missing .env file. Copy .env.example to .env and fill in your settings first.
  exit /b 1
)

set APP_MODE=local
set LLM_BACKEND_MODE=auto

echo [run] Starting local API in local-first mode.
echo [run] APP_MODE=%APP_MODE%
echo [run] LLM_BACKEND_MODE=%LLM_BACKEND_MODE%
echo [run] Fallback order: local ^> DeepSeek ^> OpenAI
echo [run] To re-enable a remote GPU host later, use scripts\run_local_hybrid_windows.bat

"%PYTHON_BIN%" -m uvicorn gateway.main:app --host 0.0.0.0 --port 8012 --reload
exit /b %errorlevel%

:resolve_python
if exist ".venv\Scripts\python.exe" (
  set "PYTHON_BIN=%CD%\.venv\Scripts\python.exe"
  goto :eof
)

where python >nul 2>&1
if not errorlevel 1 (
  set "PYTHON_BIN=python"
  echo [run] .venv not found, using Python from PATH.
  goto :eof
)

echo [run] Python interpreter not found. Run scripts\bootstrap_local_windows.bat or install Python first.
exit /b 1
