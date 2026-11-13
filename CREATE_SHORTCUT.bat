@echo off
rem Puts a "SoilSense ZM" shortcut with the SoilSense icon on your desktop.
rem Double-click this file once. Afterwards use the desktop shortcut to start the demo.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$d=[Environment]::GetFolderPath('Desktop'); $s=(New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $d 'SoilSense ZM.lnk')); $s.TargetPath='%~dp0START_DEMO.bat'; $s.WorkingDirectory='%~dp0'; $s.IconLocation='%~dp0dashboard\soilsense.ico'; $s.Description='Start SoilSense ZM'; $s.Save()"
if errorlevel 1 (
  echo Could not create the shortcut. Right-click START_DEMO.bat, Send to, Desktop instead.
) else (
  echo Done: "SoilSense ZM" is on your desktop.
)
pause
