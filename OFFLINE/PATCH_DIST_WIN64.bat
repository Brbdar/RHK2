@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d %~dp0

REM Refactor v1.42-offline: patch an already built dist that has app\* sources

set "DIST=%~dp0dist\RHK_OFFLINE_WIN64"
if not exist "%DIST%" (
  echo [ERROR] Dist nicht gefunden: "%DIST%"
  echo Erwartet: OFFLINE\dist\RHK_OFFLINE_WIN64
  pause
  exit /b 1
)

cd /d "%DIST%"

REM If sources are inside \app\, flatten them into dist root
if not exist "rhk_base.py" (
  if exist "app\rhk_base.py" (
    echo [INFO] Verschiebe App-Dateien aus \app\ nach Root...
    for %%F in (app\*.py app\*.yaml app\*.yml app\*.md app\*.txt app\requirements.txt app\runtime.txt) do (
      if exist "%%F" copy /Y "%%F" ".\" >nul
    )
  )
)

REM Patch python._pth to include site-packages and project root
if exist "python" (
  for %%P in (python\python*._pth python\python*.pth) do (
    if exist "%%P" (
      echo [INFO] Patche %%P
      findstr /C:"Lib\site-packages" "%%P" >nul || echo Lib\site-packages>>"%%P"
      findstr /X /C:".." "%%P" >nul || echo ..>>"%%P"
      findstr /R /C:"^[ ]*import[ ]\+site[ ]*$" "%%P" >nul || echo import site>>"%%P"
      goto :pthdone
    )
  )
)
:pthdone

REM Ensure Start_RHK.bat exists
if not exist "Start_RHK.bat" (
  echo [INFO] Kopiere Start_RHK.bat Template...
  copy /Y "%~dp0template\Start_RHK.bat" "Start_RHK.bat" >nul
)

echo [OK] Patch abgeschlossen. Starte jetzt: dist\RHK_OFFLINE_WIN64\Start_RHK.bat
pause
