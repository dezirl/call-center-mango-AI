@echo off
setlocal
cd /d "%~dp0"
set "INSTALL_TMP=%~dp0.install_tmp"
if not exist "%INSTALL_TMP%" mkdir "%INSTALL_TMP%"
set "TEMP=%INSTALL_TMP%"
set "TMP=%INSTALL_TMP%"
set "PIP_NO_CACHE_DIR=1"

set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" (
  echo .venv is missing. Run setup_new_pc.cmd first.
  pause
  exit /b 1
)

echo Checking the NVIDIA runtime. If this PC has no NVIDIA GPU,
echo The Voice Bridge wrapper will continue in CPU mode when CUDA is unavailable.
"%PYTHON_EXE%" -m pip --version >nul 2>&1
if errorlevel 1 (
  echo Pip is missing in the virtual environment. Restoring pip...
  "%PYTHON_EXE%" -m ensurepip --upgrade
  if errorlevel 1 (
    echo Could not restore pip. Run setup_new_pc.cmd first.
    pause
    exit /b 1
  )
)

echo Installing Voice Bridge dependencies...
"%PYTHON_EXE%" -m pip install --no-cache-dir --upgrade -r requirements.txt
if errorlevel 1 (
  echo Application dependency repair failed.
  pause
  exit /b 1
)

echo Installing Silero TTS dependencies...
"%PYTHON_EXE%" -m pip uninstall -y onnxruntime onnxruntime-gpu >nul 2>&1
"%PYTHON_EXE%" -m pip install --no-cache-dir -r "%~dp0silero_requirements.txt"
if errorlevel 1 (
  echo Silero dependency installation failed.
  pause
  exit /b 1
)
echo Installing the CUDA build of PyTorch...
"%PYTHON_EXE%" -m pip install --no-cache-dir --upgrade "torch==2.7.0" "torchaudio==2.7.0" --index-url https://download.pytorch.org/whl/cu126
if errorlevel 1 (
  echo CUDA PyTorch installation failed.
  pause
  exit /b 1
)

echo Checking installed packages...
"%PYTHON_EXE%" -m pip check
if errorlevel 1 (
  echo Dependency conflicts remain. Read the messages above.
  pause
  exit /b 1
)

where nvidia-smi >nul 2>&1
if errorlevel 1 (echo nvidia-smi not found. Install the NVIDIA driver on the target PC.) else (nvidia-smi -L)
pause
