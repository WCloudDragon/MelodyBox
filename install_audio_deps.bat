@echo off
chcp 65001 >nul
echo ===== 安装 MERT 音频 Embedding 依赖 =====
echo.
echo 依赖列表:
echo   - librosa    : 音频加载与处理
echo   - soundfile  : 音频文件读写
echo   - transformers: MERT 模型加载（首次导出 ONNX 用）
echo   - torch      : ONNX 模型导出（首次导出 ONNX 用）
echo   - onnx       : ONNX 模型处理
echo   - onnxruntime: ONNX 推理（已有）
echo.

echo [1/1] 安装依赖...
D:\Download\Tools\Python\Python313\python.exe -m pip install librosa soundfile onnx transformers torch -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn

echo.
echo [验证] 检查安装...
D:\Download\Tools\Python\Python313\python.exe -c "import librosa; import soundfile; import transformers; import torch; print('所有依赖安装成功!')"

if errorlevel 1 (
  echo.
  echo ===== 安装可能不完整，请手动检查 =====
) else (
  echo.
  echo ===== 安装完成！=====
)

pause
