"""Read-only environment probes; missing optional services remain explicit."""

import importlib.util
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import httpx


def command_probe(command: list[str]) -> dict:
    executable = shutil.which(command[0])
    if not executable:
        return {"ok": False, "reason_code": "COMMAND_NOT_FOUND", "output": None}
    try:
        result = subprocess.run(
            command, check=False, capture_output=True, text=True, timeout=15
        )
        return {
            "ok": result.returncode == 0,
            "returncode": result.returncode,
            "output": result.stdout.strip(),
            "error": result.stderr.strip(),
        }
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"ok": False, "reason_code": "PROBE_FAILED", "error": str(error)}


def doctor(data_dir: Path = Path("data")) -> dict:
    report = {
        "python": {
            "ok": (3, 11) <= sys.version_info[:2] <= (3, 12),
            "version": platform.python_version(),
            "executable": sys.executable,
        },
        "platform": {
            "ok": True,
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
        },
        "uv": command_probe(["uv", "--version"]),
        "git": command_probe(["git", "--version"]),
    }
    gpu = shutil.which("nvidia-smi")
    if not gpu and Path("/usr/lib/wsl/lib/nvidia-smi").exists():
        gpu = "/usr/lib/wsl/lib/nvidia-smi"
    report["gpu"] = command_probe(
        [
            gpu or "nvidia-smi",
            "--query-gpu=name,memory.total,memory.used,driver_version",
            "--format=csv",
        ]
    )
    if importlib.util.find_spec("torch") is None:
        report["torch"] = {
            "ok": False,
            "reason_code": "NOT_INSTALLED",
            "cuda_available": None,
        }
    else:
        report["torch"] = command_probe(
            [
                sys.executable,
                "-c",
                "import torch,json; print(json.dumps({'version':torch.__version__,'cuda_available':torch.cuda.is_available()}))",
            ]
        )
    try:
        response = httpx.get("http://127.0.0.1:11434/api/tags", timeout=3)
        response.raise_for_status()
        report["ollama"] = {"ok": True, "models": response.json().get("models", [])}
    except (httpx.HTTPError, ValueError) as error:
        report["ollama"] = {
            "ok": False,
            "reason_code": "SERVICE_UNAVAILABLE",
            "error": str(error),
        }
    try:
        with tempfile.TemporaryFile(dir=data_dir):
            pass
        report["data_directory"] = {"ok": True}
    except OSError as error:
        report["data_directory"] = {"ok": False, "error": str(error)}
    report["ok"] = report["python"]["ok"] and report["data_directory"]["ok"]
    return report
