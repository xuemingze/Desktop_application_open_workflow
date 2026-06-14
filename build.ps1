# ============================================================
#   桌面自动化助手 - 打包脚本 (PowerShell 版,tag 化命名)
#
#   输出: dist\桌面自动化助手-vYYYY.MM.DD[-HHMM].exe
#
#   用法:
#     .\build.ps1
#     .\build.ps1 -Date 2026.07.15
#     .\build.ps1 -Date 2026.07.15 -Time 14:30
#     .\build.ps1 -NoBuild       # 仅重命名现有 dist 下的产物
# ============================================================

param(
    [string]$Date = "",
    [string]$Time = "",
    [switch]$NoBuild = $false,
    [switch]$CopyToDesktop = $false
)

$ErrorActionPreference = "Stop"

# ---- 切换到脚本目录 ----
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $ScriptDir
try {

    # ---- 1. 解析 tag ----
    if (-not $Date) {
        $Date = Get-Date -Format "yyyy.MM.dd"
    }
    if ($Time) {
        $TimeStr = "-" + ($Time -replace ":", "").Substring(0, [Math]::Min(4, $Time.Length))
    } else {
        $TimeStr = ""
    }
    $Tag = "$Date$TimeStr"
    Write-Host "[BUILD] Tag: $Tag" -ForegroundColor Cyan

    # ---- 2. 检查 PyInstaller ----
    $pyinst = Get-Command pyinstaller -ErrorAction SilentlyContinue
    if (-not $pyinst -and -not $NoBuild) {
        Write-Host "[ERR] PyInstaller 未安装" -ForegroundColor Red
        Write-Host "      pip install pyinstaller"
        exit 1
    }

    # ---- 3. 清理 build ----
    if (Test-Path "build") {
        Write-Host "[CLEAN] 删除 build\" -ForegroundColor Yellow
        Remove-Item -Recurse -Force "build"
    }
    if (Test-Path "dist") {
        Write-Host "[KEEP] dist\ 保留 (历史版本)" -ForegroundColor Yellow
    }

    # ---- 4. 跑 PyInstaller ----
    if (-not $NoBuild) {
        Write-Host "[BUILD] 运行 PyInstaller ..." -ForegroundColor Cyan
        & pyinstaller build.spec --noconfirm --clean
        if ($LASTEXITCODE -ne 0) {
            Write-Host "[ERR] PyInstaller 失败" -ForegroundColor Red
            exit 1
        }
    }

    # ---- 5. 重命名为 tag 版本 ----
    $orig = "dist\桌面自动化助手.exe"
    $tagged = "dist\桌面自动化助手-v$Tag.exe"

    if (-not (Test-Path $orig)) {
        Write-Host "[ERR] 找不到 $orig" -ForegroundColor Red
        exit 1
    }

    if (Test-Path $tagged) {
        $rnd = Get-Random -Maximum 999
        $tagged = "dist\桌面自动化助手-v$Tag-$rnd.exe"
        Write-Host "[WARN] 同名已存在,加后缀: $tagged" -ForegroundColor Yellow
    }

    Write-Host "[TAG] 重命名: $orig -> $tagged" -ForegroundColor Green
    Move-Item -Force $orig $tagged

    # ---- 6. 输出结果 ----
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host " ✅ 打包完成"
    Write-Host " 📦 输出: $tagged"
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "当前 dist\ 内容:" -ForegroundColor Cyan
    Get-ChildItem dist\*.exe -ErrorAction SilentlyContinue | ForEach-Object {
        $size = "{0:N1}" -f ($_.Length / 1MB)
        Write-Host "  $($_.Name)  ($size MB)"
    }

    # ---- 7. 可选复制到桌面 ----
    if ($CopyToDesktop) {
        $dest = [Environment]::GetFolderPath("Desktop")
        if (Test-Path $dest) {
            Copy-Item -Force $tagged $dest
            Write-Host "[OK] 已复制到 $dest" -ForegroundColor Green
        }
    } else {
        $ans = Read-Host "同步到桌面? (Y/N)"
        if ($ans -eq 'Y' -or $ans -eq 'y') {
            $dest = [Environment]::GetFolderPath("Desktop")
            Copy-Item -Force $tagged $dest
            Write-Host "[OK] 已复制到 $dest" -ForegroundColor Green
        }
    }
}
finally {
    Pop-Location
}