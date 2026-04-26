@echo off
setlocal EnableExtensions
cd /d %~dp0

REM Refactor v1.52-offline: portable offline runtime (embedded Python + preinstalled Win64 wheels)
if not exist "python\python.exe" (
  echo [ERROR] Embedded Python nicht gefunden: "%~dp0python\python.exe"
  echo Diese Offline-Distribution ist unvollstaendig oder wurde nicht gebaut.
  pause
  exit /b 1
)

if not exist "rhk_standalone_entry.py" (
  echo [ERROR] rhk_standalone_entry.py nicht gefunden in: "%~dp0"
  echo Bitte pruefen, ob die App-Dateien im Hauptordner liegen.
  pause
  exit /b 1
)

if not exist "python\Lib\site-packages\gradio" (
  echo [ERROR] Python-Abhaengigkeiten fehlen in "python\Lib\site-packages".
  echo Das Offline-Kit wurde nicht vollstaendig gebaut.
  pause
  exit /b 1
)

REM Offline defaults: no CDN, no browser OCR, everything stays inside this folder
set RHK_OFFLINE=1
set RHK_STANDALONE=1
set RHK_DEPLOY_PROFILE=offline
set RHK_PRIVACY_MODE=1
set RHK_ALLOW_CDN_ASSETS=0
set RHK_ENABLE_BROWSER_IMPORT=0
set RHK_ENABLE_BROWSER_OCR=0
set RHK_ALLOW_SERVER_UPLOAD=1
set RHK_RUNTIME_ROOT_DIR=%~dp0runtime
set RHK_LOG_DIR=%~dp0run_logs
set RHK_CASE_DIR=%~dp0runtime\cases
set RHK_EXPORT_DIR=%~dp0exports

REM Telemetry/analytics hard-off
set GRADIO_ANALYTICS_ENABLED=False
set HF_HUB_DISABLE_TELEMETRY=1
set DO_NOT_TRACK=1

REM Stable port preference (launcher picks a free port if busy)
set GRADIO_SERVER_PORT=7860

if not exist "run_logs" mkdir run_logs >nul 2>&1
if not exist "runtime" mkdir runtime >nul 2>&1
if not exist "exports" mkdir exports >nul 2>&1
if not exist "temp" mkdir temp >nul 2>&1
echo [INFO] Start: %DATE% %TIME% > "run_logs\run.log"

REM Launch (stdout+stderr to log)
"python\python.exe" "rhk_standalone_entry.py" >> "run_logs\run.log" 2>&1

echo.
echo [ERROR] App wurde beendet. Details: "%~dp0run_logs\run.log"
pause
exit /b 1
