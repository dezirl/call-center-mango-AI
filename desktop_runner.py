from __future__ import annotations

import argparse
import json
import runpy
import socket
import sys
from pathlib import Path


if "--rvc-cli" in sys.argv[1:]:
    rvc_args = [argument for argument in sys.argv[1:] if argument != "--rvc-cli"]
    resource_dir = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    rvc_cli = resource_dir / "rvc-runtime" / "infer_cli.py"
    if not rvc_cli.is_file():
        print(f"RVC CLI source was not bundled: {rvc_cli}", file=sys.stderr, flush=True)
        raise SystemExit(1)
    sys.argv = [str(rvc_cli), *rvc_args]
    runpy.run_path(str(rvc_cli), run_name="__main__")
    raise SystemExit(0)

import uvicorn

from app import app, gigaam_stt_service, tts_service


def find_free_port(host: str) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind((host, 0))
        return int(probe.getsockname()[1])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0, help="Use 0 to choose a free local port.")
    parser.add_argument("--check-gpu", action="store_true", help="Print the NVIDIA/PyTorch diagnosis and exit.")
    args = parser.parse_args()
    if args.check_gpu:
        info = tts_service.device_info()
        info["stt"] = gigaam_stt_service.info()
        print(json.dumps(info, ensure_ascii=False, indent=2), flush=True)
        gpu_ready = info["gpuAvailable"] and "CUDAExecutionProvider" in info["stt"]["availableProviders"]
        raise SystemExit(0 if gpu_ready else 2)

    backend_port = args.port or find_free_port(args.host)
    print(f"Voice Bridge backend: http://{args.host}:{backend_port}", flush=True)
    uvicorn.run(app, host=args.host, port=backend_port)
