@echo off
title API Server - port 8000
cd /d "%~dp0"
echo.
echo  API Server starting on http://127.0.0.1:8000
echo  Press Ctrl+C to stop.
echo.
if /i "%ESG_DEV_RELOAD%"=="1" (
  echo  Dev reload mode enabled.
  python -m uvicorn gateway.main:app --host 127.0.0.1 --port 8000 --reload
) else (
  echo  Production-style single process mode enabled.
  python -m uvicorn gateway.main:app --host 127.0.0.1 --port 8000
)
pause
