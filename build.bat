@echo off
chcp 65001 > nul
REM ============================================================
REM   桌面自动化助手 - 打包脚本 (tag 化命名,不覆盖历史版本)
REM
REM   输出: dist\桌面自动化助手-vYYYY.MM.DD[-HHMM].exe
REM
REM   用法:
REM     build.bat              默认: 当天日期
REM     build.bat 2026.07.15   指定日期
REM     build.bat today 14:30  指定日期+时间
REM ============================================================

setlocal

cd /d "%~dp0"

REM ---- 1. 解析参数 ----
if "%~1"=="" (
    set "TAG_DATE=%date:~0,4%.%date:~5,2%.%date:~8,2%"
    set "TAG_TIME="
) else (
    set "TAG_DATE=%~1"
    if /I not "%~2"=="" (
        set "TAG_TIME=-%~2:~0,2%%~2:~3,2%"
    ) else (
        set "TAG_TIME="
    )
)

echo [BUILD] Tag: %TAG_DATE%%TAG_TIME%

REM ---- 2. 检查 PyInstaller ----
where pyinstaller >nul 2>&1
if errorlevel 1 (
    echo [ERR] PyInstaller 未安装
    echo        pip install pyinstaller
    pause
    exit /b 1
)

REM ---- 3. 清理旧构建缓存 ----
if exist build (
    echo [CLEAN] 删除 build\
    rmdir /s /q build
)
if exist dist (
    echo [KEEP] dist\ 保留 (历史版本)
)

REM ---- 4. 调用 PyInstaller 生成通用名 ----
echo [BUILD] 运行 PyInstaller ...
pyinstaller build.spec --noconfirm --clean

if errorlevel 1 (
    echo [ERR] PyInstaller 失败
    pause
    exit /b 1
)

REM ---- 5. 重命名为 tag 版本 ----
set "ORIG=dist\桌面自动化助手.exe"
set "TAGGED=dist\桌面自动化助手-v%TAG_DATE%%TAG_TIME%.exe"

if exist "%ORIG%" (
    if exist "%TAGGED%" (
        echo [WARN] 目标已存在,加随机后缀: %TAGGED%
        set /a "RND=%RANDOM% %% 1000"
        set "TAGGED=dist\桌面自动化助手-v%TAG_DATE%%TAG_TIME%-%RND%.exe"
    )
    echo [TAG] 重命名: %ORIG% -^> %TAGGED%
    move /y "%ORIG%" "%TAGGED%"
) else (
    echo [ERR] 找不到 %ORIG%
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  ✅ 打包完成
echo  📦 输出: %TAGGED%
echo ============================================================
echo.
echo 当前 dist\ 内容:
dir /b dist\*.exe 2>nul
echo.

REM 可选: 复制到桌面方便拿
set "DESKTOP=%USERPROFILE%\Desktop"
if exist "%DESKTOP%" (
    echo [COPY] 同步到桌面?
    set /p "CHOICE=按 Y 复制到桌面,其他键跳过: "
    if /I "%CHOICE%"=="Y" (
        copy /y "%TAGGED%" "%DESKTOP%\" > nul
        echo [OK] 已复制到 %DESKTOP%
    )
)

endlocal
pause