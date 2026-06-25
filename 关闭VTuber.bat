@echo off
chcp 65001 > nul
echo 正在关闭 VTuber (PID 23836)...
taskkill /F /PID  28620
if %errorlevel%==0 (echo 已关闭) else (echo 未找到或已关闭)
pause
