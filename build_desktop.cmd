@echo off
setlocal
cd /d "%~dp0"
set "PATH=%~dp0tools;%PATH%"

tasklist /FI "IMAGENAME eq Voice Bridge.exe" /NH | findstr /I /C:"Voice Bridge.exe" >nul
if not errorlevel 1 (
  echo Close the running Voice Bridge app before building the portable folder.
  goto :failed
)
tasklist /FI "IMAGENAME eq voicebridge-backend.exe" /NH | findstr /I /C:"voicebridge-backend.exe" >nul
if not errorlevel 1 (
  echo Close the running Voice Bridge backend before building the portable folder.
  goto :failed
)

set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" (
  echo Run setup_new_pc.cmd or setup_gpu.cmd first.
  pause
  exit /b 1
)

echo Installing the desktop packager into the isolated environment...
"%PYTHON_EXE%" -m pip install --no-cache-dir -r requirements-build.txt
if errorlevel 1 goto :failed

if not exist "%~dp0src-tauri\backend" mkdir "%~dp0src-tauri\backend"
if exist "%~dp0dist\voicebridge-backend.exe" del /q "%~dp0dist\voicebridge-backend.exe"
echo Building the bundled local backend...
"%PYTHON_EXE%" -m PyInstaller --noconfirm --clean --onedir --name voicebridge-backend --add-data "%~dp0static;static" --add-data "%~dp0models\gigaam-v2-onnx;gigaam-v2-onnx" --add-data "%~dp0models\qwen3-1.7b;qwen3-1.7b" --add-data "%~dp0rvc-runtime\infer_cli.py;rvc-runtime" --add-data "%~dp0.native\rvc-project\infer;rvc-runtime\infer" --add-data "%~dp0.native\rvc-project\configs;rvc-runtime\configs" --add-data "%~dp0.native\rvc-project\tools;rvc-runtime\tools" --add-data "%~dp0.native\rvc-project\i18n;rvc-runtime\i18n" --add-data "%~dp0.native\rvc-project\assets\hubert_base;rvc-runtime\assets\hubert_base" --add-data "%~dp0.native\rvc-project\assets\rmvpe;rvc-runtime\assets\rmvpe" --add-data "%~dp0.native\rvc-project\ffmpeg.exe;rvc-runtime" --exclude-module tensorboard --collect-all requests --collect-all omegaconf --collect-all pywinauto --collect-all pyaudiowpatch --collect-all silero_vad --collect-all onnxruntime --collect-all onnx_asr --collect-all huggingface_hub --collect-all transformers --collect-all faiss --collect-all parselmouth --collect-all librosa --collect-all av --hidden-import mango_automation --hidden-import transformers --hidden-import faiss --hidden-import parselmouth --hidden-import librosa --hidden-import av --hidden-import ffmpeg --hidden-import sounddevice --hidden-import torchaudio --hidden-import soundfile desktop_runner.py
if errorlevel 1 goto :failed

if exist "%~dp0src-tauri\backend.new" rmdir /s /q "%~dp0src-tauri\backend.new"
if exist "%~dp0src-tauri\backend\voicebridge-backend" rmdir /s /q "%~dp0src-tauri\backend\voicebridge-backend"
if not exist "%~dp0src-tauri\backend" mkdir "%~dp0src-tauri\backend"
move /y "%~dp0dist\voicebridge-backend" "%~dp0src-tauri\backend\voicebridge-backend" >nul
if errorlevel 1 goto :failed

if not exist node_modules (
  echo Installing Tauri tooling...
  npm install
  if errorlevel 1 goto :failed
)

echo Building the native Tauri executable...
node "%~dp0node_modules\@tauri-apps\cli\tauri.js" build --no-bundle --features custom-protocol
if errorlevel 1 goto :failed

set "PORTABLE_DIR=%~dp0src-tauri\target\release\Voice Bridge Portable"
if exist "%PORTABLE_DIR%" rmdir /s /q "%PORTABLE_DIR%"
mkdir "%PORTABLE_DIR%\backend" >nul
copy /y "%~dp0src-tauri\target\release\voice-bridge.exe" "%PORTABLE_DIR%\Voice Bridge.exe" >nul
if errorlevel 1 goto :failed
xcopy /e /i /y "%~dp0src-tauri\backend\voicebridge-backend" "%PORTABLE_DIR%\backend\voicebridge-backend" >nul
if errorlevel 1 goto :failed
copy /y "%~dp0tools\check_gpu.cmd" "%PORTABLE_DIR%\Проверка GPU.cmd" >nul
if errorlevel 1 goto :failed
copy /y "%~dp0tools\portable_setup_gpu.cmd" "%PORTABLE_DIR%\setup_gpu.cmd" >nul
if errorlevel 1 goto :failed

echo Portable desktop app created in src-tauri\target\release\Voice Bridge Portable
pause
exit /b 0

:failed
echo.
echo Desktop build failed. Read the error above.
pause
exit /b 1
