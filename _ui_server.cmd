@echo off
title UI Server - port 9000
cd /d "%~dp0dist"
echo.
echo  UI Server starting on http://127.0.0.1:9000
echo  Serving directory: %CD%
echo  Press Ctrl+C to stop.
echo.
python -m http.server 9000
pause
