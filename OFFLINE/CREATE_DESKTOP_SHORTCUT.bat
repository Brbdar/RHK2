@echo off
setlocal enableextensions

REM ==========================================================
REM Create desktop shortcut for one-click launch (Offline)
REM ==========================================================

set "HERE=%~dp0"
set "TARGET=%HERE%Start_RHK.bat"

REM If executed from the BUILD kit (OFFLINE\), use dist output
if not exist "%TARGET%" (
  set "TARGET=%HERE%..\dist\RHK_OFFLINE_WIN64\Start_RHK.bat"
)

if not exist "%TARGET%" (
  echo [ERROR] Start_RHK.bat nicht gefunden.
  echo Erwartet: "%HERE%Start_RHK.bat" oder "%HERE%..\dist\RHK_OFFLINE_WIN64\Start_RHK.bat"
  pause
  exit /b 1
)

set "DESK=%PUBLIC%\Desktop"
set "LNK=%DESK%\RHK Befundassistent (Offline).lnk"

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$WshShell = New-Object -ComObject WScript.Shell; " ^
  "$s = $WshShell.CreateShortcut('%LNK%'); " ^
  "$s.TargetPath = '%TARGET%'; " ^
  "$s.WorkingDirectory = Split-Path '%TARGET%'; " ^
  "$s.IconLocation = $env:SystemRoot + '\System32\shell32.dll,220'; " ^
  "$s.Save();" || (
    echo [ERROR] Shortcut Erstellung fehlgeschlagen (PowerShell/Policy).
    pause
    exit /b 1
  )

echo OK: Shortcut erstellt: "%LNK%"
pause
