@echo off
setlocal
cd /d "%~dp0"
title ESG Quant Terminal

echo ============================================
echo   ESG Quant Terminal  --  Launcher
echo ============================================
echo.

:: Step 1: Stop any running servers first so the rebuild never keeps stale UI files alive
echo [1/5] Stopping stale UI/API servers...
call :kill_port 9000
call :kill_port 8000
echo       OK

:: Step 2: Rebuild static bundle from the current repo state
echo [2/5] Rebuilding static bundle...
call npm.cmd run build:static
if errorlevel 1 goto err_build
echo       OK

:: Step 3: Restart UI server on port 9000
echo [3/5] Restarting UI server (port 9000)...
start "UI :9000" "%~dp0_ui_server.cmd"
timeout /t 3 /nobreak >nul

:: Step 4: Restart API server on port 8000
echo [4/5] Restarting API server (port 8000)...
start "API :8000" "%~dp0_api_server.cmd"
timeout /t 4 /nobreak >nul

:: Step 5: Wait for both servers to be ready
echo [5/5] Waiting for UI server to be ready...
call :wait_port 9000 25
if errorlevel 1 goto err_timeout_ui

echo       Waiting for API server to be ready...
call :wait_port 8000 25
if errorlevel 1 goto err_timeout_api

:open_browser
echo.
echo   Landing  --  http://127.0.0.1:9000/
echo   App      --  http://127.0.0.1:9000/app/
echo   API      --  http://127.0.0.1:8000
echo   Docs     --  http://127.0.0.1:8000/docs
echo.
set "LAUNCH_URL=http://127.0.0.1:9000/?v=%RANDOM%%RANDOM%"
start "" "%LAUNCH_URL%"
echo   Browser opened. Press any key to close this window.
pause >nul
exit /b 0

:kill_port
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":%~1" ^| findstr "LISTENING"') do (
    taskkill /PID %%p /F >nul 2>&1
)
timeout /t 1 /nobreak >nul
exit /b 0

:wait_port
set "WAIT_PORT=%~1"
set "WAIT_MAX=%~2"
set /a WAIT_TRY=0
:wait_port_loop
netstat -ano | findstr ":%WAIT_PORT%" | findstr "LISTENING" >nul 2>&1
if %errorlevel%==0 exit /b 0
set /a WAIT_TRY+=1
if %WAIT_TRY% geq %WAIT_MAX% exit /b 1
timeout /t 1 /nobreak >nul
goto wait_port_loop

:err_build
echo.
echo   ERROR: Static bundle rebuild failed.
echo   Check the output above for the failing build step.
echo.
pause >nul
exit /b 1

:err_timeout_ui
echo.
echo   ERROR: UI server did not respond within 25 seconds.
echo   Check the "UI :9000" console window for errors.
echo.
pause >nul
exit /b 1

:err_timeout_api
echo.
echo   ERROR: API server did not respond within 25 seconds.
echo   Check the "API :8000" console window for errors.
echo.
pause >nul
exit /b 1
