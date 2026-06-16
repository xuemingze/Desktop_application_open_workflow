@echo off
chcp 65001 > nul
REM ============================================================
REM   Desktop Automation Assistant - Build Script
REM   Output: dist\desktop-auto-vYYYY.MM.DD-gHHHHHHHH.exe
REM   (git short hash always included → never overwrites)
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

REM 获取 git short hash 作为唯一标识（避免同名覆盖）
for /f "delims=" %%h in ('git rev-parse --short HEAD 2^>nul') do set "GIT_HASH=%%h"
if "%GIT_HASH%"=="" set "GIT_HASH=local"

echo [BUILD] Date: %TAG_DATE%  Hash: %GIT_HASH%

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

REM ---- 4. Run PyInstaller with unique name (git hash → never overwrite) ----
set "EXE_NAME=desktop-auto-v%TAG_DATE%-g%GIT_HASH%"
echo [BUILD] Output: %EXE_NAME%.exe
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

REM Optional: copy to desktop
set "DESKTOP=%USERPROFILE%\Desktop"
if exist "%DESKTOP%" (
    echo [COPY] Copy to Desktop?
    set /p "CHOICE=Press Y to copy, other keys to skip: "
    if /I "%CHOICE%"=="Y" (
        copy /y "dist\%EXE_NAME%.exe" "%DESKTOP%\%EXE_NAME%.exe" >nul
        if errorlevel 1 (
            echo [ERR] Copy failed
        ) else (
            echo [OK] Copied to %DESKTOP%\%EXE_NAME%.exe
        )
    )
)

echo.
pause
