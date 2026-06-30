@echo off
echo [1/2] Installing fastembed + langdetect...
D:\Download\Tools\Python\Python313\python.exe -m pip install fastembed langdetect --user -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn
echo.
echo [2/2] Switching to GPU DirectML version...
D:\Download\Tools\Python\Python313\python.exe -m pip install onnxruntime-directml --force-reinstall --user -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn
echo.
echo All done. Restart backend to apply.
pause >nul
