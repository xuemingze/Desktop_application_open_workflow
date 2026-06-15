# ============================================================
#   Desktop Automation Assistant - PowerShell Build Script
#   Tag-based naming, never overwrites historical versions
#
#   Output: dist\desktop-auto-vYYYY.MM.DD[-HHMM].exe
#
#   Usage:
#     .\build.ps1
#     .\build.ps1 -Date 2026.07.15
#     .\build.ps1 -Date 2026.07.15 -Time 14:30
#     .\build.ps1 -CopyToDesktop
# ============================================================

param(
    [string]$Date = "",
    [string]$Time = "",
    [switch]$NoBuild = $false,
    [switch]$CopyToDesktop = $false
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $ScriptDir
try {
    if (-not $Date) {
        $Date = Get-Date -Format "yyyy.MM.dd"
    }

    if ($Time) {
        $digits = ($Time -replace ":", "")
        if ($digits.Length -gt 4) { $digits = $digits.Substring(0, 4) }
        $TimeStr = "-$digits"
    } else {
        # 自动使用当前时间作为时间后缀
        $TimeStr = "-" + (Get-Date -Format "HHmm")
    }

    $Tag = "$Date$TimeStr"
    $ExeName = "desktop-auto-v$Tag"
    $Output = "dist\$ExeName.exe"

    Write-Host "[BUILD] Tag: $Tag" -ForegroundColor Cyan

    if (-not $NoBuild) {
        $pyinstaller = Get-Command pyinstaller -ErrorAction SilentlyContinue
        if (-not $pyinstaller -and (Test-Path ".venv\Scripts\pyinstaller.exe")) {
            $pyinstaller = ".venv\Scripts\pyinstaller.exe"
        }
        if (-not $pyinstaller) {
            Write-Host "[ERR] PyInstaller not installed." -ForegroundColor Red
            Write-Host "      Run: pip install pyinstaller"
            exit 1
        }

        if (Test-Path "build") {
            Write-Host "[CLEAN] Removing build\" -ForegroundColor Yellow
            Remove-Item -Recurse -Force "build"
        }
        if (Test-Path "dist") {
            Write-Host "[KEEP] dist\ preserved (historical versions)" -ForegroundColor Yellow
        }

        Write-Host "[BUILD] Running PyInstaller ... Output: $Output" -ForegroundColor Cyan
        $env:BUILD_EXE_NAME = $ExeName
        & $pyinstaller build.spec --noconfirm --clean
        if ($LASTEXITCODE -ne 0) {
            Write-Host "[ERR] PyInstaller failed" -ForegroundColor Red
            exit 1
        }
    }

    if (-not (Test-Path $Output)) {
        Write-Host "[ERR] Expected output not found: $Output" -ForegroundColor Red
        exit 1
    }

    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host " PACKAGE BUILT"
    Write-Host " Output: $Output"
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Current dist\ contents:" -ForegroundColor Cyan
    Get-ChildItem dist\*.exe -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | ForEach-Object {
        $size = "{0:N1}" -f ($_.Length / 1MB)
        Write-Host "  $($_.Name)  ($size MB)"
    }

    if ($CopyToDesktop) {
        $dest = [Environment]::GetFolderPath("Desktop")
        if (Test-Path $dest) {
            Copy-Item -Force $Output (Join-Path $dest "$ExeName.exe")
            Write-Host "[OK] Copied to desktop: $ExeName.exe" -ForegroundColor Green
        }
    }
}
finally {
    Pop-Location
}
