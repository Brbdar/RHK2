@echo off
setlocal EnableExtensions

set "DIST=%~dp0dist\RHK_OFFLINE_WIN64"
if not exist "%DIST%\Start_RHK.bat" (
  echo [ERROR] Offline-Kit nicht gefunden: "%DIST%"
  echo Bitte zuerst OFFLINE\BUILD_OFFLINE_WIN64.bat ausfuehren.
  pause
  exit /b 1
)

call "%DIST%\Start_RHK.bat"
