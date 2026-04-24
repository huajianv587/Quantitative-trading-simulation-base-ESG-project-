@echo off
set "API_PORT=1002"
title API Server - port %API_PORT%
cd /d "%~dp0"
echo.
echo  API Server starting on http://127.0.0.1:%API_PORT%
echo  Press Ctrl+C to stop.
echo.
if /i "%ESG_DEV_RELOAD%"=="1" (
  echo  Dev reload mode enabled.
  python -m uvicorn gateway.main:app --host 127.0.0.1 --port %API_PORT% --reload
) else (
  echo  Production-style single process mode enabled.
  python -m uvicorn gateway.main:app --host 127.0.0.1 --port %API_PORT%
)
pause
