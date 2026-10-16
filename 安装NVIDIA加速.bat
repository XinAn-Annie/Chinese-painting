@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\bootstrap_python.ps1" -Mode Nvidia
set "launch_exit=%errorlevel%"
if not "%launch_exit%"=="0" (
 echo.
 echo NVIDIA 加速安装或启动失败，退出代码：%launch_exit%。
 pause
)
exit /b %launch_exit%
