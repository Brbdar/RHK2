@echo off
setlocal
cd /d %~dp0
set "PYTHON_BIN=%PYTHON_BIN%"
if "%PYTHON_BIN%"=="" set "PYTHON_BIN=python"
"%PYTHON_BIN%" "%~dp0..\tools\build_windows_offline_kit.py" --output-dir "%~dp0dist\RHK_OFFLINE_WIN64" --force
if errorlevel 1 (
  echo.
  echo [ERROR] Build fehlgeschlagen.
  pause
  exit /b 1
)
