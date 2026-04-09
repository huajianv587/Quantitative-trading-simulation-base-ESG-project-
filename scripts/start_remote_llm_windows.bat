@echo off
setlocal

cd /d "%~dp0.."

call :resolve_python || exit /b 1

if not exist ".env" (
  echo [remote-llm] Missing .env file. Copy .env.example to .env first.
  exit /b 1
)

echo [remote-llm] Starting remote LLM service using .env configuration...
"%PYTHON_BIN%" model-serving\remote_llm_server.py
exit /b %errorlevel%

:resolve_python
if exist ".venv\Scripts\python.exe" (
  set "PYTHON_BIN=%CD%\.venv\Scripts\python.exe"
  goto :eof
)

where python >nul 2>&1
if not errorlevel 1 (
  set "PYTHON_BIN=python"
  echo [remote-llm] .venv not found, using Python from PATH.
  goto :eof
)

echo [remote-llm] Python interpreter not found. Run scripts\bootstrap_local_windows.bat or install Python first.
exit /b 1
