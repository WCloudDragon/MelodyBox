@echo off
title MelodyBox Dev

echo [1/3] Starting Flask...
start "MelodyBox-Flask" cmd /c "cd /d %~dp0backend && D:\Download\Tools\Python\Python313\python.exe app.py"

echo [2/3] Waiting for Flask (max 30s)...
set retry=0
:wait_flask
set /a retry=retry+1
if %retry% gtr 30 (
    echo Timeout! Make sure Flask can start on port 5000.
    pause
    exit /b 1
)
timeout /t 1 /nobreak >nul
D:\Download\Tools\Python\Python313\python.exe -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/api/health', timeout=2)" >nul 2>&1
if errorlevel 1 goto wait_flask
echo Flask ready!
echo.

echo [3/3] Starting Electron + Vite...
npm run electron:dev

echo Closing Flask...
taskkill /f /fi "WINDOWTITLE eq MelodyBox-Flask" >nul 2>&1
timeout /t 2 /nobreak >nul
