@echo off
chcp 65001 >nul
rem Development only: resolve the source root from this script's location.
cd /d "%~dp0.."
if errorlevel 1 exit /b 1
set PYTHONUTF8=1
py -3.12 -m venv .venv
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe -m pip install -r requirements-build.txt
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe build_app.py
if errorlevel 1 exit /b 1
echo 已生成项目札记文件夹，请保留其中的 _internal。
pause
