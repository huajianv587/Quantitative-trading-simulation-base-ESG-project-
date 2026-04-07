@echo off
setlocal

cd /d "%~dp0.."

if exist ".venv\Scripts\python.exe" goto install

echo [bootstrap] No local .venv found. Creating one...
py -3.11 -m venv .venv 2>nul && goto install
py -3.12 -m venv .venv 2>nul && goto install
py -3.13 -m venv .venv 2>nul && goto install

echo [bootstrap] Failed to create .venv. Install Python 3.11/3.12/3.13 with the py launcher enabled.
exit /b 1

:install
echo [bootstrap] Using interpreter:
".venv\Scripts\python.exe" --version
if errorlevel 1 exit /b %errorlevel%

".venv\Scripts\python.exe" -m pip install --upgrade pip setuptools wheel
if errorlevel 1 exit /b %errorlevel%

".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 exit /b %errorlevel%

echo.
echo [bootstrap] Local environment ready.
echo [bootstrap] Recommended next step: scripts\run_local_first_windows.bat
echo [bootstrap] Optional remote GPU path: scripts\run_local_hybrid_windows.bat
