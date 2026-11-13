@echo off
rem SoilSense ZM: a secure https link for phones, so the phone GPS works anywhere.
rem Start the demo first (START DEMO or the desktop icon), then double-click this.
rem Uses a free Cloudflare quick tunnel: the link changes every time and stops when you close this window.
title SoilSense ZM - phone link (keep open)
cd /d "%~dp0"
set CF=cloudflared
where cloudflared >nul 2>nul || set CF="%ProgramFiles(x86)%\cloudflared\cloudflared.exe"
if not exist %CF% if not "%CF%"=="cloudflared" (
  echo cloudflared is not installed. Install it once with:
  echo     winget install --id Cloudflare.cloudflared
  echo then close this window and double-click PHONE_LINK again.
  pause
  exit /b 1
)
echo.
echo Making a secure link. In a few seconds look below for a line like:
echo     https://something-random.trycloudflare.com
echo Open that link on the phone. Keep this window open while you use it.
echo Anyone with the link can see the login page, so use proper passwords.
echo.
%CF% tunnel --url http://localhost:8000
pause
