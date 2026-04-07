@echo off
setlocal

cd /d "%~dp0.."

docker version >nul 2>&1
if errorlevel 1 (
  echo [qdrant] Docker Desktop is not ready. Start Docker Desktop first.
  exit /b 1
)

docker ps -a --format "{{.Names}}" | findstr /R /C:"^qdrant$" >nul
if not errorlevel 1 (
  echo [qdrant] Found standalone container named qdrant. Stopping it to free port 6333...
  docker stop qdrant >nul 2>&1
)

echo [qdrant] Starting compose-managed local Qdrant...
docker compose up -d qdrant
if errorlevel 1 exit /b %errorlevel%

echo.
echo [qdrant] Current status:
docker compose ps qdrant
echo.
echo [qdrant] Health probe:
curl http://127.0.0.1:6333/collections
