@echo off
setlocal
set "ROOT=%~dp0"
cd /d "%ROOT%"

echo Voice Bridge GPU setup
echo.
echo The portable backend already contains the CUDA-enabled PyTorch runtime.
echo Only a compatible NVIDIA driver is required on this PC.
echo.

where nvidia-smi >nul 2>&1
if errorlevel 1 (
  echo NVIDIA driver was not found. Install the current driver from:
  echo https://www.nvidia.com/Download/index.aspx
  echo The application will still be able to use CPU mode.
  pause
  exit /b 2
)

echo === NVIDIA driver ===
nvidia-smi -L
echo.
echo === Bundled PyTorch / CUDA / ONNX Runtime ===
set "BACKEND=%ROOT%backend\voicebridge-backend\voicebridge-backend.exe"
if not exist "%BACKEND%" set "BACKEND=%ROOT%..\src-tauri\backend\voicebridge-backend\voicebridge-backend.exe"

if exist "%BACKEND%" (
  "%BACKEND%" --check-gpu
) else (
  echo Backend executable was not found next to this setup script.
  echo Run this file from inside the completed Voice Bridge Portable folder.
  pause
  exit /b 1
)

echo.
echo If gpuAvailable is true, start Voice Bridge.exe and select GPU in Settings.
pause
exit /b 0
