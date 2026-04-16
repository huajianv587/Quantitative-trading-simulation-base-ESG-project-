@echo off
setlocal
cd /d "%~dp0"
title 恢复到基础版

echo ============================================
echo   Restore Workspace To Tag: 基础版
echo ============================================
echo.
echo This will:
echo   1. fetch the latest tags from origin
echo   2. force local branch main to tag "基础版"
echo   3. discard tracked local changes
echo   4. remove untracked files and folders
echo.
echo Ignored files like .env, node_modules, dist, data, storage stay untouched.
echo.
set /p CONFIRM=Type YES to continue: 
if /I not "%CONFIRM%"=="YES" (
  echo Cancelled.
  pause
  exit /b 1
)

echo.
echo [1/4] Fetching tags from origin...
git fetch origin --tags
if errorlevel 1 goto err_fetch

echo [2/4] Checking tag "基础版"...
git rev-parse --verify "refs/tags/基础版" >nul 2>&1
if errorlevel 1 goto err_tag

echo [3/4] Switching to main...
git checkout -f main
if errorlevel 1 goto err_checkout

echo [4/4] Resetting local files to tag "基础版"...
git reset --hard "基础版"
if errorlevel 1 goto err_reset
git clean -fd
if errorlevel 1 goto err_clean

echo.
echo Workspace restored to tag "基础版".
pause
exit /b 0

:err_fetch
echo.
echo ERROR: Failed to fetch tags from origin.
pause
exit /b 1

:err_tag
echo.
echo ERROR: Tag "基础版" was not found.
pause
exit /b 1

:err_checkout
echo.
echo ERROR: Failed to switch to branch main.
pause
exit /b 1

:err_reset
echo.
echo ERROR: Failed to reset to tag "基础版".
pause
exit /b 1

:err_clean
echo.
echo ERROR: Failed to clean untracked files.
pause
exit /b 1
