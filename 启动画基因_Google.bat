@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 goto check_python
py -3 --version >nul 2>nul
if errorlevel 1 goto check_python
py -3 run_local.py
goto finish

:check_python
where python >nul 2>nul
if errorlevel 1 goto no_python
python --version >nul 2>nul
if errorlevel 1 goto no_python
python run_local.py
goto finish

:no_python
echo Python was not found. Install 64-bit Python 3.10-3.12 and enable Add Python to PATH.
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
