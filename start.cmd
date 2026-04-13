@echo off
cd /d "%~dp0"
title ESG Quant Terminal

echo ============================================
echo   ESG Quant Terminal  --  Launcher
echo ============================================
echo.

:: Step 1: Sync frontend to dist/app
echo [1/4] Syncing frontend files...
if not exist "dist\app"      mkdir "dist\app"
if not exist "dist\app\css"  mkdir "dist\app\css"
if not exist "dist\app\js"   mkdir "dist\app\js"
xcopy /E /Y /Q "frontend\css"           "dist\app\css\"  >nul 2>&1
xcopy /E /Y /Q "frontend\js"            "dist\app\js\"   >nul 2>&1
copy  /Y       "frontend\index.html"    "dist\app\"      >nul 2>&1
copy  /Y       "frontend\app-config.js" "dist\app\"      >nul 2>&1
echo       OK

:: Step 2: Start UI server on port 9000
echo [2/4] UI server (port 9000)...
netstat -ano | findstr ":9000" | findstr "LISTENING" >nul 2>&1
if %errorlevel%==0 (
    echo       Already running.
) else (
    start "UI :9000" "%~dp0_ui_server.cmd"
    timeout /t 3 /nobreak >nul
)

:: Step 3: Start API server on port 8000
echo [3/4] API server (port 8000)...
netstat -ano | findstr ":8000" | findstr "LISTENING" >nul 2>&1
if %errorlevel%==0 (
    echo       Already running.
) else (
    start "API :8000" "%~dp0_api_server.cmd"
    timeout /t 4 /nobreak >nul
)

:: Step 4: Wait for UI then open landing page
echo [4/4] Waiting for UI server to be ready...
set /a _try=0
:wait_ui
netstat -ano | findstr ":9000" | findstr "LISTENING" >nul 2>&1
if %errorlevel%==0 goto open_browser
set /a _try+=1
if %_try% gtr 25 goto err_timeout
timeout /t 1 /nobreak >nul
goto wait_ui

:open_browser
echo.
echo   Landing  --  http://127.0.0.1:9000/
echo   App      --  http://127.0.0.1:9000/app/
echo   API      --  http://127.0.0.1:8000
echo   Docs     --  http://127.0.0.1:8000/docs
echo.
start "" "http://127.0.0.1:9000/"
echo   Browser opened. Press any key to close this window.
pause >nul
exit /b 0

:err_timeout
echo.
echo   ERROR: UI server did not respond within 25 seconds.
echo   Check the "UI :9000" console window for errors.
echo.
pause >nul
exit /b 1
