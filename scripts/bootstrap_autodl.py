from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _python() -> str:
    return sys.executable or shutil.which("python") or "python"


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap an AutoDL 5090 node for ESG Quant RL experiments")
    parser.add_argument("--skip-install", action="store_true")
    args = parser.parse_args()

    result = {
        "python": _python(),
        "root": str(ROOT),
        "requirements": str(ROOT / "requirements-quant-rl.txt"),
        "gpu_probe": None,
        "install": "skipped" if args.skip_install else "pending",
    }

    if not args.skip_install:
        subprocess.check_call([_python(), "-m", "pip", "install", "-r", str(ROOT / "requirements-quant-rl.txt")], cwd=ROOT)
        result["install"] = "done"

    try:
        probe = subprocess.check_output(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"], text=True)
        result["gpu_probe"] = probe.strip().splitlines()
    except Exception as exc:
        result["gpu_probe"] = [f"nvidia-smi unavailable: {exc}"]

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
