@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul

rem Use a mainland PyPI mirror and increase retry/parallel download settings.
rem If the accelerated run fails, retry once with the official PyPI index.
set "PYTHONUTF8=1"
set "PYTHONUNBUFFERED=1"
set "PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/"
set "PIP_DEFAULT_TIMEOUT=180"
set "PIP_RETRIES=8"
set "PIP_DISABLE_PIP_VERSION_CHECK=1"
set "MODELSCOPE_ENDPOINT=https://www.modelscope.cn"
set "MODELSCOPE_DOWNLOAD_PARALLELS=4"
set "MODELSCOPE_DOWNLOAD_PARALLEL_WORKERS=4"
set "MODELSCOPE_DOWNLOAD_PARALLEL_THRESHOLD_MB=64"
set "MODELSCOPE_DOWNLOAD_MAX_RETRIES=8"
set "MODELSCOPE_DOWNLOAD_TIMEOUT=180"

where py >nul 2>nul
if errorlevel 1 goto check_python
py -3 --version >nul 2>nul
if errorlevel 1 goto check_python
set "PYTHON_LAUNCHER=py"
goto run_accelerated

:check_python
where python >nul 2>nul
if errorlevel 1 goto no_python
python --version >nul 2>nul
if errorlevel 1 goto no_python
set "PYTHON_LAUNCHER=python"

:run_accelerated
echo [Accelerated] PyPI mirror: %PIP_INDEX_URL%
echo [Accelerated] ModelScope parallel streams: %MODELSCOPE_DOWNLOAD_PARALLELS%
if "%PYTHON_LAUNCHER%"=="py" (
    py -3 run_local.py
) else (
    python run_local.py
)
set "launch_exit=%errorlevel%"
if "%launch_exit%"=="0" goto finish

echo.
echo [Fallback] Accelerated startup failed. Retrying once with official PyPI...
set "PIP_INDEX_URL=https://pypi.org/simple"
if "%PYTHON_LAUNCHER%"=="py" (
    py -3 run_local.py
) else (
    python run_local.py
)
set "launch_exit=%errorlevel%"
goto finish

:no_python
echo Python was not found. Install 64-bit Python 3.10-3.12 and enable Add Python to PATH.
pause
exit /b 1

:finish
if not "%launch_exit%"=="0" (
    echo.
    echo Startup failed with exit code %launch_exit%.
    pause
)
exit /b %launch_exit%

