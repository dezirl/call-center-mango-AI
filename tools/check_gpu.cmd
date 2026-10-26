@echo off
setlocal
cd /d "%~dp0"
echo === NVIDIA driver ===
where nvidia-smi
nvidia-smi
echo.
echo === Bundled PyTorch / CUDA ===
"%~dp0backend\voicebridge-backend\voicebridge-backend.exe" --check-gpu
echo.
pause
