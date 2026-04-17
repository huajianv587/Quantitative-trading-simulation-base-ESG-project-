@echo off
setlocal
cd /d "%~dp0"
title ESG Quant Terminal
set "LAUNCH_LOG=%~dp0start-launch.log"
> "%LAUNCH_LOG%" echo [%date% %time%] Launcher started in %CD%

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
set "ESG_API_BASE_URL=http://127.0.0.1:8000"
call npm.cmd run build:static
if errorlevel 1 goto err_build
echo       OK

:: Step 3: Restart UI server on port 9000
echo [3/5] Restarting UI server (port 9000)...
echo [%date% %time%] Launching UI server window >> "%LAUNCH_LOG%"
start "UI :9000" "%ComSpec%" /k ""%~dp0_ui_server.cmd""
timeout /t 3 /nobreak >nul

:: Step 4: Restart API server on port 8000
echo [4/5] Restarting API server (port 8000)...
echo [%date% %time%] Launching API server window >> "%LAUNCH_LOG%"
start "API :8000" "%ComSpec%" /k ""%~dp0_api_server.cmd""
timeout /t 4 /nobreak >nul

:: Step 5: Wait for both servers to be ready
echo [5/5] Verifying static bundle config...
call :verify_app_config
if errorlevel 1 goto err_config
echo       OK

echo       Waiting for API health endpoint...
call :wait_http_200 http://127.0.0.1:8000/health 25
if errorlevel 1 goto err_timeout_api
echo       OK

echo       Waiting for UI shell...
call :wait_http_200 http://127.0.0.1:9000/app/ 25
if errorlevel 1 goto err_timeout_ui
echo       OK

:open_browser
echo.
echo   Landing  --  http://127.0.0.1:9000/
echo   App      --  http://127.0.0.1:9000/app/
echo   API      --  http://127.0.0.1:8000
echo   Docs     --  http://127.0.0.1:8000/docs
echo.
set "LAUNCH_URL=http://127.0.0.1:9000/?v=%RANDOM%%RANDOM%"
call :open_url "%LAUNCH_URL%"
if errorlevel 1 (
  echo   WARNING: Browser auto-open failed.
  echo   Please open this URL manually:
  echo   %LAUNCH_URL%
  echo [%date% %time%] Browser auto-open failed for %LAUNCH_URL% >> "%LAUNCH_LOG%"
) else (
  echo   Browser opened.
  echo [%date% %time%] Browser auto-open succeeded for %LAUNCH_URL% >> "%LAUNCH_LOG%"
)
echo   Launch log: %LAUNCH_LOG%
echo   Press any key to close this window.
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

:verify_app_config
powershell -NoProfile -ExecutionPolicy Bypass -Command "$p = Join-Path (Get-Location) 'dist\\app\\app-config.js'; if (!(Test-Path $p)) { Write-Host 'dist/app/app-config.js missing'; exit 1 }; $c = Get-Content -Raw $p; if ($c -notmatch 'http://127\\.0\\.0\\.1:8000') { Write-Host ('Unexpected app-config.js: ' + $c.Trim()); exit 1 }"
exit /b %errorlevel%

:wait_http_200
set "WAIT_URL=%~1"
set "WAIT_MAX=%~2"
set /a WAIT_TRY=0
:wait_http_200_loop
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $r = Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 '%WAIT_URL%'; if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 300) { exit 0 } ; exit 1 } catch { exit 1 }"
if %errorlevel%==0 exit /b 0
set /a WAIT_TRY+=1
if %WAIT_TRY% geq %WAIT_MAX% exit /b 1
timeout /t 1 /nobreak >nul
goto wait_http_200_loop

:open_url
set "TARGET_URL=%~1"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "try { Start-Process '%TARGET_URL%' -ErrorAction Stop; exit 0 } catch { try { Start-Process explorer.exe '%TARGET_URL%' -ErrorAction Stop; exit 0 } catch { exit 1 } }"
exit /b %errorlevel%

:err_build
echo.
echo   ERROR: Static bundle rebuild failed.
echo   Check the output above for the failing build step.
echo [%date% %time%] ERROR build step failed >> "%LAUNCH_LOG%"
echo.
pause >nul
exit /b 1

:err_config
echo.
echo   ERROR: dist/app/app-config.js does not point to http://127.0.0.1:8000
echo   Rebuild was aborted before opening the browser.
echo [%date% %time%] ERROR invalid dist/app/app-config.js >> "%LAUNCH_LOG%"
echo.
pause >nul
exit /b 1

:err_timeout_ui
echo.
echo   ERROR: UI shell http://127.0.0.1:9000/app/ did not respond within 25 seconds.
echo   Check the "UI :9000" console window for errors.
echo [%date% %time%] ERROR UI shell readiness timeout >> "%LAUNCH_LOG%"
echo.
pause >nul
exit /b 1

:err_timeout_api
echo.
echo   ERROR: API health http://127.0.0.1:8000/health did not respond within 25 seconds.
echo   Check the "API :8000" console window for errors.
echo [%date% %time%] ERROR API health readiness timeout >> "%LAUNCH_LOG%"
echo.
pause >nul
exit /b 1
