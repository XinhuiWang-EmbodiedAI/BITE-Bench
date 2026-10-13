@echo off
setlocal
cd /d "%~dp0"
if exist "runtime-python\python.exe" (
  "runtime-python\python.exe" run.py serve
) else (
  where py >nul 2>nul
  if errorlevel 1 (
    python run.py serve
  ) else (
    py -3 run.py serve
  )
)
if errorlevel 1 (
  echo BITE Collect failed. A working Python 3.12 or newer is required.
  pause
)
