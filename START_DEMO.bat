@echo off
rem SoilSense ZM: start the demo with one double-click.
rem Starts the server, opens the dashboard and runs the probe program.
rem The probe follows whichever field is open on the dashboards Live page.
title SoilSense ZM - probe
cd /d "%~dp0"

if not exist data mkdir data
if not exist data\secret_key.txt python -c "import secrets; print(secrets.token_hex(32))" > data\secret_key.txt
set /p SOILSENSE_SECRET_KEY=<data\secret_key.txt

echo Starting the SoilSense server in a second window...
start "SoilSense ZM - server (keep open)" cmd /k python -m uvicorn backend.main:app --port 8000
timeout /t 5 /nobreak >nul
start "" "http://localhost:8000/#/fields"

echo.
choice /c YN /m "Calibrate the probe first? (needed once a day, have pH 7 and pH 4 buffers ready)"
if errorlevel 2 goto live
python -m bridge.bridge calibrate

:live
echo.
echo In the dashboard: open a field and press "Live probe reading".
python -m bridge.bridge live
echo.
echo The probe program has stopped. You can close this window.
pause
