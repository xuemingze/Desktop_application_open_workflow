@echo off
@chcp 65001 >nul
"%~dp0.venv\Scripts\pythonw.exe" "%~dp0desktop_auto.py" %*
