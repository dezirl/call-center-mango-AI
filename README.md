# Voice Bridge

Voice Bridge is a Windows desktop application for AI-assisted recruiting calls through Mango Talker. It connects speech recognition (Groq Whisper or local GigaAM), a conversational model (local Qwen 3 or an OpenAI-compatible API), and local Silero text-to-speech. The optional RVC stage can convert the generated voice.

## Features

- Mango Talker call automation and live call controls.
- Speech-to-text with Groq Whisper or local GigaAM.
- Local Qwen 3 or a configurable OpenAI-compatible LLM provider.
- Russian and English speech synthesis with Silero.
- Optional RVC voice conversion, Hysteria VPN routing, Telegram notifications, and Vision-based contact extraction.
- A portable Windows desktop build.

## Requirements

- Windows 10 or 11, 64-bit.
- 64-bit Python 3.10, 3.11, or 3.12 for the source-based setup.
- Mango Talker installed and signed in for call automation.
- API credentials for whichever hosted STT, LLM, Vision, or Telegram services you enable.
- A Windows virtual audio cable (for example, VB-CABLE) if Mango Talker needs to use Voice Bridge's generated speech as its microphone.

## Run from source

1. Clone or download this repository.
2. In File Explorer, run `setup_new_pc.cmd` and wait for dependency installation to finish.
3. Run `start_voicebridge.cmd`.
4. Open the local application window and configure provider credentials in **Settings → Connections**. Credentials are entered on your PC; do not commit them to this repository.
5. For calls, open **Settings → Audio routing**, select the TTS output and the loopback input, and keep Mango Talker open.

The setup script creates a local `.venv` and installs the Python dependencies. Silero downloads its model the first time speech is synthesized and caches it under `%LOCALAPPDATA%\VoiceBridge\silero_models`.

### Mango Talker audio routing

If using a virtual cable, select **CABLE Input** as the Voice Bridge TTS output, then select the matching **CABLE Output** as Mango Talker's microphone. In Voice Bridge, choose a loopback device where the remote caller can be heard. Avoid routing the generated TTS back into the STT input, or the app may recognize its own voice.

Voice Bridge uses an already installed Windows audio device; it does not install or create a virtual audio driver.

## Optional local models and GPU

Large model weights are intentionally excluded from GitHub. Hosted providers work without downloading the optional local LLM weights. To use local Qwen 3, obtain the compatible `Qwen3-1.7B-Q4_K_M.gguf` model and place it in `models/qwen3-1.7b/`. For local GigaAM, place its ONNX model in `gigaam-v2-onnx/`.

For NVIDIA acceleration, install a compatible NVIDIA driver, run `setup_gpu.cmd`, then select GPU where available. CPU mode remains available.

## Build the portable desktop app

Install the Rust stable toolchain and Node.js, then run:

```cmd
build_desktop.cmd
```

The build script creates the portable application under `src-tauri\target\release\Voice Bridge Portable`. The output includes a bundled backend and is intentionally excluded from Git. The build also expects the local model assets and optional RVC runtime files referenced by `build_desktop.cmd`; those large or separately sourced assets are not included in this GitHub repository and must be prepared locally before building the full portable package.

## Configuration and privacy

- Provider keys and call settings are configured in the application.
- `.env.example` is a template only. Copy it to `.env` if you choose to configure supported environment variables; keep the real `.env` file private.
- Do not commit API keys, Telegram bot tokens, candidate data, call recordings, generated audio, local model weights, or portable build output.
- Treat extracted contact details and call transcripts as personal data and handle them according to your organization's policies and applicable law.

## Upload the project to GitHub

The `.gitignore` excludes virtual environments, build output, local data, secrets, and large model weights. From PowerShell, open this project folder and run:

```powershell
git init
git add .
git status
git commit -m "Initial Voice Bridge source"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/YOUR-REPOSITORY.git
git push -u origin main
```

First, create an empty repository on GitHub and replace the URL above with its HTTPS URL. Review the output of `git status` before committing. GitHub blocks individual files larger than 100 MB; keep model weights and packaged builds out of the repository, or use Git LFS / GitHub Releases if you intentionally need to distribute them. Never force-push over existing work you want to keep.

## License

No project license is currently specified. Add a `LICENSE` file before redistributing this project or accepting external contributions.
