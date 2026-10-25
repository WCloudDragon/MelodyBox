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
  exit /b 1
)

echo [3/3] 复制到项目根目录...
move "dist\melodybox-api" "..\flask-dist" >nul
if exist "build" rmdir /s /q "build"
if exist "melodybox-api.spec" del "melodybox-api.spec"

echo [4/4] 修正 VC 运行时版本...
rem torch 自带的 MSVCP140 是 14.31，onnxruntime 用它会在导入时崩溃，这里统一换成系统版本
for %%f in (MSVCP140.dll MSVCP140_1.dll MSVCP140_ATOMIC_WAIT.dll VCOMP140.DLL VCRUNTIME140.dll VCRUNTIME140_1.dll) do (
  if exist "%SystemRoot%\System32\%%f" copy /y "%SystemRoot%\System32\%%f" "..\flask-dist\_internal\%%f" >nul
)

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
