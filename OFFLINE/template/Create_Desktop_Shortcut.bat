@echo off
setlocal
cd /d %~dp0

REM Creates a Desktop shortcut that starts the offline app (one click)
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\RHK Befundassistent (Offline).lnk');" ^
  "$s.TargetPath='%~dp0Start_RHK.bat';" ^
  "$s.WorkingDirectory='%~dp0';" ^
  "$s.WindowStyle=1;" ^
  "$s.Save();"

echo [OK] Shortcut erstellt: Desktop\RHK Befundassistent (Offline).lnk
pause
