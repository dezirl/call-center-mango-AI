@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

set "INSTALL_TMP=%~dp0.install_tmp"
if not exist "%INSTALL_TMP%" mkdir "%INSTALL_TMP%"
set "TEMP=%INSTALL_TMP%"
set "TMP=%INSTALL_TMP%"
set "PIP_NO_CACHE_DIR=1"

echo Voice Bridge - first-time setup
echo.
echo This setup uses 64-bit Python 3.10, 3.11 or 3.12 for Silero TTS.
echo.

rem Pick a Python version that has a matching PyTorch wheel. Do not use an
rem unversioned "python" command first: on many PCs it points to Python 3.13+.
set "PYTHON_EXE="
if exist "D:\Python\python.exe" call :try_python "D:\Python\python.exe"

if not defined PYTHON_EXE (
  where py >nul 2>&1
  if not errorlevel 1 (
    for %%V in (3.12 3.11 3.10) do (
      if not defined PYTHON_EXE (
      py -%%V -c "import struct,sys; raise SystemExit(0 if sys.version_info[:2] in ((3,10),(3,11),(3,12)) and struct.calcsize('P') == 8 else 1)" >nul 2>&1
        if not errorlevel 1 (
          for /f "delims=" %%P in ('py -%%V -c "import sys; print(sys.executable)"') do set "PYTHON_EXE=%%P"
        )
      )
    )
  )
)

if not defined PYTHON_EXE (
  where python >nul 2>&1
  if not errorlevel 1 (
    for /f "delims=" %%P in ('where python') do (
      if not defined PYTHON_EXE call :try_python "%%P"
    )
  )
)

if not defined PYTHON_EXE (
  where py >nul 2>&1
  if not errorlevel 1 (
    echo Compatible Python was not found. Installing Python 3.12 with the Python install manager...
    py install 3.12
    if not errorlevel 1 (
      py -3.12 -c "import struct,sys; raise SystemExit(0 if sys.version_info[:2] == (3,12) and struct.calcsize('P') == 8 else 1)" >nul 2>&1
      if not errorlevel 1 (
        for /f "delims=" %%P in ('py -3.12 -c "import sys; print(sys.executable)"') do set "PYTHON_EXE=%%P"
      )
    )
  )
)

if not defined PYTHON_EXE goto :no_python
echo Using Python:
"%PYTHON_EXE%" --version
"%PYTHON_EXE%" -c "import struct,sys; print('Architecture:', struct.calcsize('P')*8, 'bit')"
echo.

set "BOOTSTRAP_EXE=%PYTHON_EXE%"
set "VENV_PYTHON=%~dp0.venv\Scripts\python.exe"
set "VENV_OK="
if exist "%VENV_PYTHON%" call :check_python "%VENV_PYTHON%"
if exist "%VENV_PYTHON%" if not defined VENV_OK (
  echo Existing .venv uses an unsupported Python. Recreating it...
  rmdir /s /q "%~dp0.venv"
)

if not exist "%~dp0.venv\Scripts\python.exe" (
  echo Creating an isolated Python environment...
  "%BOOTSTRAP_EXE%" -m venv "%~dp0.venv"
  if errorlevel 1 goto :failed
)
set "PYTHON_EXE=%VENV_PYTHON%"

"%PYTHON_EXE%" -m pip --version >nul 2>&1
if errorlevel 1 (
  echo Pip is missing in the virtual environment. Restoring pip...
  "%PYTHON_EXE%" -m ensurepip --upgrade
  if errorlevel 1 goto :failed
)

echo Upgrading pip...
"%PYTHON_EXE%" -m pip install --no-cache-dir --upgrade pip
if errorlevel 1 goto :failed

:install_app
echo Installing Voice Bridge dependencies...
"%PYTHON_EXE%" -m pip install --no-cache-dir -r requirements.txt
if errorlevel 1 goto :failed

echo Installing Silero TTS dependencies...
"%PYTHON_EXE%" -m pip uninstall -y onnxruntime onnxruntime-gpu >nul 2>&1
"%PYTHON_EXE%" -m pip install --no-cache-dir -r "%~dp0silero_requirements.txt"
if errorlevel 1 goto :failed

echo Checking installed packages...
"%PYTHON_EXE%" -m pip check
if errorlevel 1 goto :failed

echo.
echo Setup complete. Silero TTS v5.5 will load on first speech request.
echo Start the app with start_voicebridge.cmd
pause
exit /b 0

:try_python
set "CANDIDATE=%~1"
if not exist "%CANDIDATE%" exit /b 0
set "PYTHON_OK="
call :check_python "%CANDIDATE%"
if defined PYTHON_OK set "PYTHON_EXE=%CANDIDATE%"
exit /b 0

:check_python
set "CANDIDATE=%~1"
if not exist "%CANDIDATE%" exit /b 0
set "PYTHON_OK="
"%CANDIDATE%" -c "import struct,sys; raise SystemExit(0 if sys.version_info[:2] in ((3,10),(3,11),(3,12)) and struct.calcsize('P') == 8 else 1)" >nul 2>&1
if not errorlevel 1 set "PYTHON_OK=1"
if defined PYTHON_OK set "VENV_OK=1"
exit /b 0

:no_python
echo.
echo ERROR: compatible 64-bit Python 3.10, 3.11 or 3.12 was not found.
echo If the Python install manager is available, run: py install 3.12
echo Otherwise install Python 3.11 x64 from https://www.python.org/downloads/windows/
echo During installation enable "Add python.exe to PATH", then run this file again.
pause
exit /b 1

:failed
echo.
echo Setup failed. Read the error above, then run this file again.
pause
exit /b 1
