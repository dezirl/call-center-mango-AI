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
  echo .venv is missing. Run setup_new_pc.cmd or setup_gpu.cmd first.
  pause
  exit /b 1
)
echo Local TTS: Silero v5.5 Russian / v3 English
echo Silero loads one selected speaker model into memory on first speech request.

"%PYTHON_EXE%" -m pip --version >nul 2>&1
if errorlevel 1 (
  echo Pip is missing. Restoring pip in the virtual environment...
  "%PYTHON_EXE%" -m ensurepip --upgrade
  if errorlevel 1 (
    echo Could not restore pip. Recreate the .venv with setup_new_pc.cmd.
    pause
    exit /b 1
  )
)

"%PYTHON_EXE%" -c "import uvicorn" >nul 2>&1
if errorlevel 1 (
echo Uvicorn is missing. Installing Uvicorn...
  "%PYTHON_EXE%" -m pip install --no-cache-dir "uvicorn[standard]==0.50.0"
  if errorlevel 1 (
    echo Dependency installation failed. Read the error above.
    pause
    exit /b 1
  )
)

"%PYTHON_EXE%" desktop_runner.py --host 127.0.0.1 --port 0
pause
