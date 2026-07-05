@echo off
chcp 65001 >nul
echo ===== MelodyBox Flask 后端打包 (PyInstaller) =====
echo.

cd /d "%~dp0backend"

echo [1/3] 清理旧构建...
if exist "dist" rmdir /s /q "dist"
if exist "build" rmdir /s /q "build"
if exist "..\flask-dist" rmdir /s /q "..\flask-dist"

echo [2/3] 使用 PyInstaller 打包...
D:\flask_env\Scripts\pyinstaller.exe --onedir --name melodybox-api ^
  --hidden-import mutagen --hidden-import flask --hidden-import flask_cors ^
  --hidden-import librosa --hidden-import soundfile --hidden-import audioread ^
  --hidden-import onnxruntime --hidden-import onnxruntime.transformers ^
  --nowindowed --clean app.py

if errorlevel 1 (
  echo 打包失败!
  pause
  exit /b 1
)

echo [3/3] 复制到项目根目录...
move "dist\melodybox-api" "..\flask-dist" >nul
if exist "build" rmdir /s /q "build"
if exist "melodybox-api.spec" del "melodybox-api.spec"

echo.
echo ===== 完成 =====
echo Flask 可执行文件: flask-dist\melodybox-api.exe
echo.
echo 打包发布步骤:
echo   1. npm run build:flask     - 打包 Flask
echo   2. npm run electron:build  - 完整打包
echo.
echo 开发模式一键启动:
echo   npm run dev:all
echo.
pause
