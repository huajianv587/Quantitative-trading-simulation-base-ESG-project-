@echo off
setlocal EnableDelayedExpansion

cd /d "%~dp0.."

if not exist ".env" (
  echo [tunnel] Missing .env file. Copy .env.example to .env first.
  exit /b 1
)

for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
  if /i "%%A"=="REMOTE_GPU_SSH_HOST" set REMOTE_GPU_SSH_HOST=%%B
  if /i "%%A"=="REMOTE_GPU_SSH_PORT" set REMOTE_GPU_SSH_PORT=%%B
  if /i "%%A"=="REMOTE_GPU_SSH_USER" set REMOTE_GPU_SSH_USER=%%B
  if /i "%%A"=="REMOTE_GPU_FORWARD_LOCAL_PORT" set REMOTE_GPU_FORWARD_LOCAL_PORT=%%B
  if /i "%%A"=="REMOTE_GPU_FORWARD_REMOTE_PORT" set REMOTE_GPU_FORWARD_REMOTE_PORT=%%B
)

if "!REMOTE_GPU_SSH_HOST!"=="" (
  echo [tunnel] REMOTE_GPU_SSH_HOST is empty in .env
  exit /b 1
)

if "!REMOTE_GPU_SSH_PORT!"=="" set REMOTE_GPU_SSH_PORT=22
if "!REMOTE_GPU_SSH_USER!"=="" set REMOTE_GPU_SSH_USER=root
if "!REMOTE_GPU_FORWARD_LOCAL_PORT!"=="" set REMOTE_GPU_FORWARD_LOCAL_PORT=8010
if "!REMOTE_GPU_FORWARD_REMOTE_PORT!"=="" set REMOTE_GPU_FORWARD_REMOTE_PORT=8010

echo [tunnel] Opening SSH tunnel:
echo [tunnel]   local !REMOTE_GPU_FORWARD_LOCAL_PORT! ^> !REMOTE_GPU_SSH_HOST!:!REMOTE_GPU_FORWARD_REMOTE_PORT!

C:\Windows\System32\OpenSSH\ssh.exe -N -L !REMOTE_GPU_FORWARD_LOCAL_PORT!:127.0.0.1:!REMOTE_GPU_FORWARD_REMOTE_PORT! -p !REMOTE_GPU_SSH_PORT! !REMOTE_GPU_SSH_USER!@!REMOTE_GPU_SSH_HOST!
