@echo off
setlocal EnableExtensions
cd /d "%~dp0"
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\bootstrap_python.ps1" -Mode Normal
set "launch_exit=%ERRORLEVEL%"
if not "%launch_exit%"=="0" (
 echo.
 echo Startup failed with exit code %launch_exit%.
 pause
)
exit /b %launch_exit%
