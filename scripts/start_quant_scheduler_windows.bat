@echo off
setlocal
cd /d %~dp0..

if exist .venv\Scripts\python.exe (
  set PYTHON_EXE=.venv\Scripts\python.exe
) else (
  set PYTHON_EXE=python
)

%PYTHON_EXE% scripts\quant_signal_scheduler.py --poll-seconds 20
