# 启动桌面自动化助手 (PowerShell 版本)
# 用法: 右键此文件 -> "使用 PowerShell 运行"
$ErrorActionPreference = "Stop"
$env:PYTHONIOENCODING = "utf-8"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$py = Join-Path $root ".venv\Scripts\pythonw.exe"
if (-not (Test-Path $py)) {
    Write-Host "[ERROR] venv not found: $py" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}
& $py (Join-Path $root "desktop_auto.py") $args
