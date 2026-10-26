"""Small launcher for the official RVC offline inference CLI."""

from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE
if not (PROJECT_ROOT / "infer" / "cli.py").is_file():
    PROJECT_ROOT = HERE.parent / ".native" / "rvc-project"

CLI_PATH = PROJECT_ROOT / "infer" / "cli.py"
if not CLI_PATH.is_file():
    raise SystemExit(f"RVC CLI source was not bundled: {CLI_PATH}")

sys.path.insert(0, str(PROJECT_ROOT))
os.environ["PYTHONPATH"] = str(PROJECT_ROOT) + os.pathsep + os.environ.get("PYTHONPATH", "")
ffmpeg_path = PROJECT_ROOT / "ffmpeg.exe"
if ffmpeg_path.is_file():
    os.environ["PATH"] = str(PROJECT_ROOT) + os.pathsep + os.environ.get("PATH", "")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

runpy.run_path(str(CLI_PATH), run_name="__main__")
