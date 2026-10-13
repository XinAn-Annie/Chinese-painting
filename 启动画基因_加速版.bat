@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul

rem Measure several PyPI indexes and automatically use the fastest reachable one.
set "PYTHONUTF8=1"
set "PYTHONUNBUFFERED=1"
set "ZHIHUA_AUTO_PIP_INDEX=1"
set "PIP_DEFAULT_TIMEOUT=90"
set "PIP_RETRIES=3"
set "PIP_DISABLE_PIP_VERSION_CHECK=1"
set "MODELSCOPE_ENDPOINT=https://www.modelscope.cn"
set "MODELSCOPE_DOWNLOAD_PARALLELS=4"
set "MODELSCOPE_DOWNLOAD_PARALLEL_WORKERS=4"
set "MODELSCOPE_DOWNLOAD_PARALLEL_THRESHOLD_MB=64"
set "MODELSCOPE_DOWNLOAD_MAX_RETRIES=8"
set "MODELSCOPE_DOWNLOAD_TIMEOUT=180"

where py >nul 2>nul
if errorlevel 1 goto check_python
py -3.12 --version >nul 2>nul
if errorlevel 1 goto check_python
set "PYTHON_LAUNCHER=py"
goto run_accelerated

:check_python
where python >nul 2>nul
if errorlevel 1 goto no_python
python -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 12) else 1)" >nul 2>nul
if errorlevel 1 goto no_python
set "PYTHON_LAUNCHER=python"

:run_accelerated
echo [Accelerated] PyPI source: automatic wheel throughput test
echo [Accelerated] ModelScope parallel streams: %MODELSCOPE_DOWNLOAD_PARALLELS%
if "%PYTHON_LAUNCHER%"=="py" (
    py -3.12 run_local.py
) else (
    python run_local.py
)
set "launch_exit=%errorlevel%"
goto finish

:no_python
echo Python 3.12 (64-bit) was not found. Install it and enable Add Python to PATH.
pause
exit /b 1

:finish
if not "%launch_exit%"=="0" (
    echo.
    echo Startup failed with exit code %launch_exit%.
    pause
)
exit /b %launch_exit%
