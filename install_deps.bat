@echo off
echo [1/3] Installing fastembed + langdetect...
D:\Download\Tools\Python\Python313\python.exe -m pip install fastembed langdetect -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn
echo.
echo [2/3] Switching to GPU DirectML version...
D:\Download\Tools\Python\Python313\python.exe -m pip install onnxruntime-directml --force-reinstall -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn
echo.
echo [3/3] Installing audio embedding deps (MERT-v1-95M)...
D:\Download\Tools\Python\Python313\python.exe -m pip install librosa soundfile onnx transformers torch -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn
echo.
echo All done. Restart backend to apply.
pause >nul
