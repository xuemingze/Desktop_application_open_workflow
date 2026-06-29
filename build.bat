@echo off
chcp 65001 > nul
REM ============================================================
REM   Desktop Automation Assistant - Build Script
REM   Output: dist\desktop-auto-vYYYY.MM.DD-HHMMSS-gHHHHHHHH.exe
REM   (timestamp first for natural list sorting; git short hash included → never overwrites)
REM
REM   Usage:
REM     build.bat                    Default: today's date
REM     build.bat 2026.07.15         Specify date
REM ============================================================

setlocal

cd /d "%~dp0"

REM ---- 1. Parse arguments ----
if "%~1"=="" (
    set "TAG_DATE=%date:~0,4%.%date:~5,2%.%date:~8,2%"
) else (
    set "TAG_DATE=%~1"
)

REM 获取当前时间戳 + git short hash（时间在前，方便文件列表排序；保证每次 build 绝不覆盖）
for /f "delims=" %%h in ('git rev-parse --short HEAD 2^>nul') do set "GIT_HASH=%%h"
if "%GIT_HASH%"=="" set "GIT_HASH=local"
for /f "delims=" %%t in ('powershell -Command "(Get-Date).ToString('HHmmss')"') do set "BUILD_TIME=%%t"

echo [BUILD] Date: %TAG_DATE%  Hash: %GIT_HASH%  Time: %BUILD_TIME%

REM ---- 2. Check PyInstaller (优先使用项目 venv) ----
set "PYINSTALLER_CMD=pyinstaller"
if exist ".venv\Scripts\pyinstaller.exe" (
    set "PYINSTALLER_CMD=.venv\Scripts\pyinstaller.exe"
    echo [INFO] Using venv PyInstaller: .venv\Scripts\pyinstaller.exe
) else (
    where pyinstaller >nul 2>&1
    if errorlevel 1 (
        echo [ERR] PyInstaller not installed.
        echo        Run: pip install pyinstaller
        pause
        exit /b 1
    )
    echo [INFO] Using system PyInstaller
)

REM ---- 3. Clean old build cache ----
if exist build (
    echo [CLEAN] Removing build\
    rmdir /s /q build
)
if exist dist (
    echo [KEEP] dist\ preserved (historical versions)
)

REM ---- 4. Run PyInstaller with unique name (time + git hash → natural sorting, never overwrite) ----
set "EXE_NAME=desktop-auto-v%TAG_DATE%-%BUILD_TIME%-g%GIT_HASH%"
set "BUILD_EXE_NAME=%EXE_NAME%"
%PYINSTALLER_CMD% build.spec --noconfirm --clean

if errorlevel 1 (
    echo [ERR] PyInstaller failed
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  PACKAGE BUILT
echo  Output: dist\%EXE_NAME%.exe
echo ============================================================
echo.
echo Current dist\ contents:
dir /b dist\*.exe 2>nul
echo.
