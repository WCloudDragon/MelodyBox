@echo off
title MelodyBox Dev

echo [1/3] Starting Flask in parallel...
start "MelodyBox-Flask" cmd /c "cd /d %~dp0backend && D:\Download\Tools\Python\Python313\python.exe app.py"

echo [2/3] Starting Vite + Electron in parallel...
echo       The main window will appear after Flask is ready.
npm run electron:dev

echo Closing Flask...
taskkill /f /fi "WINDOWTITLE eq MelodyBox-Flask" >nul 2>&1
timeout /t 2 /nobreak >nul
