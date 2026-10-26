@echo off
setlocal
cd /d "%~dp0"

set "TTS_DEVICE=gpu"

echo Fast TTS mode: Silero TTS CUDA
call "%~dp0start_voicebridge.cmd"
