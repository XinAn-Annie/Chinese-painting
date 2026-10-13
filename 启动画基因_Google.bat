@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 goto check_python
py -3.12 --version >nul 2>nul
if errorlevel 1 goto check_python
py -3.12 run_local.py
goto finish

:check_python
where python >nul 2>nul
if errorlevel 1 goto no_python
python -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 12) else 1)" >nul 2>nul
if errorlevel 1 goto no_python
python run_local.py
goto finish

:no_python
echo Python 3.12 (64-bit) was not found. Install it and enable Add Python to PATH.
pause
exit /b 1

:finish
set "launch_exit=%errorlevel%"
if not "%launch_exit%"=="0" (
    echo.
    echo Startup failed with exit code %launch_exit%.
    pause
)
exit /b %launch_exit%
