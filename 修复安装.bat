@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\bootstrap_python.ps1" -Mode Repair
set "launch_exit=%errorlevel%"
if not "%launch_exit%"=="0" (
 echo.
 echo 修复失败，退出代码：%launch_exit%。
 pause
)
exit /b %launch_exit%
