@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
title ESG Quant Terminal

set "LAUNCH_LOG=%~dp0start-launch.log"
set "API_OUT_LOG=%~dp0runtime-api.out.log"
set "API_ERR_LOG=%~dp0runtime-api.err.log"
set "PS_BIN=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
set "DEFAULT_PORT=8012"
set "PORT_CANDIDATES=8012"
set "PORT_RANGE_START=8012"
set "PORT_RANGE_END=8012"
set "PORT_SCAN_SUMMARY=8012"
set "SELECTED_PORT="
set "LAUNCH_API=1"
set "API_URL="
set "APP_URL="
set "DOCS_URL="
set "API_HEALTH_URL="
set "API_LIVE_URL="
set "UI_HEALTH_URL="

> "%LAUNCH_LOG%" echo [%date% %time%] Launcher started in %CD%

echo ============================================
echo   ESG Quant Terminal -- Launcher
echo ============================================
echo.

echo [0/4] Checking runtime...
call :require_python
if errorlevel 1 goto err_python
call :require_powershell
if errorlevel 1 goto err_powershell
echo       OK

echo [1/4] Stopping stale Quant Terminal processes...
call :stop_runtime
echo       OK

echo [2/4] Preparing static bundle...
call :prepare_static_bundle
if errorlevel 2 goto err_static_missing
if errorlevel 1 goto err_build
call :verify_app_config
if errorlevel 1 goto err_config
echo       OK

echo [3/4] Resolving backend port...
set "SELECTED_PORT="
set "LAUNCH_API=1"
set "LAUNCH_MODE="
set "PORT_PROBE_FILE=%TEMP%\esg-quant-port-%RANDOM%%RANDOM%.tmp"
if exist "%PORT_PROBE_FILE%" del /f /q "%PORT_PROBE_FILE%" >nul 2>&1
"%PS_BIN%" -NoProfile -ExecutionPolicy Bypass -Command "$priorityRaw = $env:PORT_CANDIDATES; $rangeStart = [int]$env:PORT_RANGE_START; $rangeEnd = [int]$env:PORT_RANGE_END; $ports = New-Object 'System.Collections.Generic.List[int]'; foreach ($token in $priorityRaw.Split(' ')) { if ($token) { $port = [int]$token; if (-not $ports.Contains($port)) { [void]$ports.Add($port) } } }; foreach ($port in $rangeStart..$rangeEnd) { if (-not $ports.Contains($port)) { [void]$ports.Add($port) } }; function Test-PortFree([int]$port) { $listener = $null; try { $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $port); $listener.Start(); return $true } catch { return $false } finally { if ($listener -ne $null) { $listener.Stop() } } }; function Test-QuantHealth([int]$port) { try { $response = Invoke-RestMethod -UseBasicParsing -TimeoutSec 2 ('http://127.0.0.1:{0}/livez' -f $port); return ($response.app_id -eq 'quant-terminal' -and $response.service_name -eq 'Quant Terminal') } catch { return $false } }; foreach ($port in $ports) { if (Test-QuantHealth $port) { Write-Output ('reuse|' + $port); exit 0 }; if (Test-PortFree $port) { Write-Output ('launch|' + $port); exit 0 } }; exit 1" > "%PORT_PROBE_FILE%"
if not errorlevel 1 (
  for /f "usebackq tokens=1,2 delims=|" %%A in ("%PORT_PROBE_FILE%") do (
    set "LAUNCH_MODE=%%A"
    set "SELECTED_PORT=%%B"
  )
)
if exist "%PORT_PROBE_FILE%" del /f /q "%PORT_PROBE_FILE%" >nul 2>&1
if not defined SELECTED_PORT goto err_ports
if /i "%LAUNCH_MODE%"=="reuse" (
  set "LAUNCH_API=0"
) else (
  set "LAUNCH_API=1"
)
set "API_URL=http://127.0.0.1:%SELECTED_PORT%"
set "APP_URL=%API_URL%/"
set "DOCS_URL=%API_URL%/docs"
set "API_HEALTH_URL=%API_URL%/health"
set "API_LIVE_URL=%API_URL%/livez"
set "UI_HEALTH_URL=%API_URL%/app/index.html"
if /i "%LAUNCH_API%"=="1" (
  echo       Using free port %SELECTED_PORT%
  echo [%date% %time%] Launching API server on %SELECTED_PORT% >> "%LAUNCH_LOG%"
  call :launch_api_server "%SELECTED_PORT%"
  if errorlevel 1 goto err_api_launch
) else (
  echo       Reusing existing Quant Terminal service on %SELECTED_PORT%
  echo [%date% %time%] Reusing existing Quant Terminal service on %SELECTED_PORT% >> "%LAUNCH_LOG%"
)
echo       OK

echo [4/4] Verifying readiness...
"%PS_BIN%" -NoProfile -ExecutionPolicy Bypass -Command "for ($i = 0; $i -lt 40; $i++) { try { $response = Invoke-RestMethod -UseBasicParsing -TimeoutSec 3 '%API_LIVE_URL%'; if ($response.app_id -eq 'quant-terminal' -and $response.service_name -eq 'Quant Terminal') { exit 0 } } catch {}; Start-Sleep -Seconds 1 }; exit 1"
if errorlevel 1 goto err_timeout_api
echo       API fingerprint OK
"%PS_BIN%" -NoProfile -ExecutionPolicy Bypass -Command "for ($i = 0; $i -lt 40; $i++) { try { $r = Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 '%UI_HEALTH_URL%'; if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 300) { exit 0 } } catch {}; Start-Sleep -Seconds 1 }; exit 1"
if errorlevel 1 goto err_timeout_ui
echo       UI shell OK

echo.
echo   Landing  -- %APP_URL%
echo   Console  -- %API_URL%/app/#/dashboard
echo   API      -- %API_URL%
echo   Docs     -- %DOCS_URL%
echo.

if /i "%ESG_START_SKIP_BROWSER%"=="1" (
  echo   Browser auto-open skipped because ESG_START_SKIP_BROWSER=1.
  echo [%date% %time%] Browser auto-open skipped for %APP_URL% >> "%LAUNCH_LOG%"
) else (
  call :open_url "%APP_URL%"
  if errorlevel 1 (
    echo   WARNING: Browser auto-open failed.
    echo   Please open this URL manually:
    echo   %APP_URL%
    echo [%date% %time%] Browser auto-open failed for %APP_URL% >> "%LAUNCH_LOG%"
  ) else (
    echo   Browser opened.
    echo [%date% %time%] Browser auto-open succeeded for %APP_URL% >> "%LAUNCH_LOG%"
  )
)

echo   Launch log: %LAUNCH_LOG%

if /i "%ESG_START_NO_PAUSE%"=="1" exit /b 0

echo   Press any key to close this window.
pause >nul
exit /b 0

:require_python
python --version >nul 2>&1
if errorlevel 1 exit /b 1
exit /b 0

:require_powershell
if not exist "%PS_BIN%" exit /b 1
exit /b 0

:prepare_static_bundle
if /i "%ESG_SKIP_STATIC_BUILD%"=="1" (
  echo       Using existing dist bundle because ESG_SKIP_STATIC_BUILD=1.
  goto prepare_existing_dist
)

where npm.cmd >nul 2>&1
if errorlevel 1 (
  echo       npm.cmd not found, trying existing dist bundle.
  goto prepare_existing_dist
)

set "ESG_API_BASE_URL="
call npm.cmd run build:static
if errorlevel 1 exit /b 1
exit /b 0

:prepare_existing_dist
if not exist "dist\app\index.html" exit /b 2
exit /b 0

:verify_app_config
if not exist "dist\app\app-config.js" exit /b 1
findstr /c:"window.__ESG_API_BASE_URL__" "dist\app\app-config.js" >nul 2>&1
exit /b %errorlevel%

:stop_runtime
"%PS_BIN%" -NoProfile -ExecutionPolicy Bypass -Command "$self = $PID; $patterns = @('*uvicorn gateway.main:app*', '*python -m uvicorn gateway.main:app*', '*python -m http.server 9000*', '*_ui_server.cmd*', '*_api_server.cmd*'); Get-CimInstance Win32_Process | Where-Object { $_.ProcessId -ne $self -and ($cmd = $_.CommandLine) -and (($patterns | Where-Object { $cmd -like $_ }) | Measure-Object).Count -gt 0 } | ForEach-Object { try { Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop } catch {} }"
"%PS_BIN%" -NoProfile -ExecutionPolicy Bypass -Command "Start-Sleep -Seconds 1"
exit /b 0

:launch_api_server
if exist "%API_OUT_LOG%" del /f /q "%API_OUT_LOG%" >nul 2>&1
if exist "%API_ERR_LOG%" del /f /q "%API_ERR_LOG%" >nul 2>&1
if /i "%ESG_DEV_RELOAD%"=="1" (
  "%PS_BIN%" -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath 'python' -ArgumentList '-m','uvicorn','gateway.main:app','--host','127.0.0.1','--port','%~1','--reload' -WorkingDirectory (Resolve-Path '.') -RedirectStandardOutput '%API_OUT_LOG%' -RedirectStandardError '%API_ERR_LOG%' -WindowStyle Hidden | Out-Null"
) else (
  "%PS_BIN%" -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath 'python' -ArgumentList '-m','uvicorn','gateway.main:app','--host','127.0.0.1','--port','%~1' -WorkingDirectory (Resolve-Path '.') -RedirectStandardOutput '%API_OUT_LOG%' -RedirectStandardError '%API_ERR_LOG%' -WindowStyle Hidden | Out-Null"
)
exit /b %errorlevel%

:open_url
set "TARGET_URL=%~1"
"%PS_BIN%" -NoProfile -ExecutionPolicy Bypass -Command "try { Start-Process '%TARGET_URL%' -ErrorAction Stop; exit 0 } catch { try { Start-Process explorer.exe '%TARGET_URL%' -ErrorAction Stop; exit 0 } catch { exit 1 } }"
exit /b %errorlevel%

:pause_if_needed
if /i "%ESG_START_NO_PAUSE%"=="1" exit /b 0
pause >nul
exit /b 0

:err_python
echo.
echo   ERROR: Python was not found in PATH.
echo   Install Python or add it to PATH, then double-click start.cmd again.
echo [%date% %time%] ERROR python missing >> "%LAUNCH_LOG%"
echo.
call :pause_if_needed
exit /b 1

:err_powershell
echo.
echo   ERROR: Windows PowerShell was not found at:
echo   %PS_BIN%
echo   Check your Windows installation, then double-click start.cmd again.
echo [%date% %time%] ERROR powershell missing >> "%LAUNCH_LOG%"
echo.
call :pause_if_needed
exit /b 1

:err_build
echo.
echo   ERROR: Static bundle build failed.
echo   Check the output above for the failing npm step.
echo [%date% %time%] ERROR build step failed >> "%LAUNCH_LOG%"
echo.
call :pause_if_needed
exit /b 1

:err_static_missing
echo.
echo   ERROR: dist\app\index.html is missing and no fresh build was produced.
echo   Run npm install first, then double-click start.cmd again.
echo [%date% %time%] ERROR dist bundle missing >> "%LAUNCH_LOG%"
echo.
call :pause_if_needed
exit /b 1

:err_config
echo.
echo   ERROR: dist\app\app-config.js was not generated correctly.
echo   Rebuild was aborted before opening the browser.
echo [%date% %time%] ERROR invalid dist\app\app-config.js >> "%LAUNCH_LOG%"
echo.
call :pause_if_needed
exit /b 1

:err_timeout_ui
echo.
echo   ERROR: UI shell %UI_HEALTH_URL% did not respond within 40 seconds.
echo   Check this log for details:
echo   %API_ERR_LOG%
echo [%date% %time%] ERROR UI shell readiness timeout >> "%LAUNCH_LOG%"
echo.
call :pause_if_needed
exit /b 1

:err_timeout_api
echo.
echo   ERROR: API liveness %API_LIVE_URL% did not expose the Quant Terminal fingerprint within 40 seconds.
echo   Check these logs for details:
echo   %API_OUT_LOG%
echo   %API_ERR_LOG%
echo [%date% %time%] ERROR API health readiness timeout >> "%LAUNCH_LOG%"
echo.
call :pause_if_needed
exit /b 1

:err_api_launch
echo.
echo   ERROR: API server process could not be launched.
echo   Check these logs for details:
echo   %API_OUT_LOG%
echo   %API_ERR_LOG%
echo [%date% %time%] ERROR API launch failed >> "%LAUNCH_LOG%"
echo.
call :pause_if_needed
exit /b 1

:err_ports
echo.
echo   ERROR: No usable Quant Terminal port was found in %PORT_SCAN_SUMMARY%.
echo   Another service may already be occupying every scanned port.
echo [%date% %time%] ERROR no available port in %PORT_SCAN_SUMMARY% >> "%LAUNCH_LOG%"
echo.
call :pause_if_needed
exit /b 1
