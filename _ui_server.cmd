@echo off
setlocal EnableExtensions
set "UI_PORT=1002"
set "UI_URL=http://127.0.0.1:%UI_PORT%/app/"
title UI Entry - port %UI_PORT%
cd /d "%~dp0"
echo.
echo  Quant Terminal UI now uses the integrated gateway entry.
echo  Open this URL after the gateway starts:
echo  %UI_URL%
echo.
start "" "%UI_URL%"
if errorlevel 1 (
  echo  Browser auto-open failed. Open the URL above manually.
)
pause
