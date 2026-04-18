from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "storage" / "full-training-runs" / "preflight" / "full_model_preflight.json"
DEFAULT_JOBS = ["lora", "alpha", "p1", "sequence", "event", "p2", "bandit", "gnn", "ppo"]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from training.full_model_data_audit import TRACK_SPECS, audit_project


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _jobs(raw: str) -> list[str]:
    if not raw.strip() or raw.strip().lower() == "all":
        return list(DEFAULT_JOBS)
    selected = [item.strip().lower() for item in raw.split(",") if item.strip()]
    unknown = sorted(set(selected) - set(DEFAULT_JOBS))
    if unknown:
        raise SystemExit(f"Unknown full-suite job(s): {', '.join(unknown)}")
    return selected


def _module_exists(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def _gpu_check(*, require_cuda: bool, smoke: bool, allow_cpu_smoke: bool) -> dict[str, Any]:
    payload: dict[str, Any] = {"name": "cuda", "status": "pass", "require_cuda": require_cuda}
    try:
        import torch

        payload.update(
            {
                "torch_version": getattr(torch, "__version__", None),
                "torch_cuda_version": getattr(getattr(torch, "version", None), "cuda", None),
                "cuda_available": bool(torch.cuda.is_available()),
                "device_count": int(torch.cuda.device_count()) if torch.cuda.is_available() else 0,
            }
        )
        if torch.cuda.is_available():
            payload["device_name"] = torch.cuda.get_device_name(0)
    except Exception as exc:
        payload.update({"status": "fail", "error": f"torch unavailable: {exc}"})
        return payload

    if require_cuda and not payload["cuda_available"]:
        if smoke and allow_cpu_smoke:
            payload["status"] = "warn"
            payload["message"] = "CUDA is not visible; CPU smoke was explicitly allowed."
        else:
            payload["status"] = "fail"
            payload["message"] = "CUDA is required for full 5090 training."
    return payload


def _dependency_check(jobs: list[str], *, smoke: bool) -> dict[str, Any]:
    required = {"pandas", "numpy", "sklearn", "joblib"}
    if {"lora", "event"} & set(jobs):
        required.update({"transformers", "datasets"})
    if "lora" in jobs:
        required.update({"peft", "accelerate"})
    if {"lora", "sequence", "event", "gnn", "ppo"} & set(jobs):
        required.add("torch")
    if "ppo" in jobs and not smoke:
        required.update({"gymnasium", "stable_baselines3"})

    missing = sorted(module for module in required if not _module_exists(module))
    return {
        "name": "python_dependencies",
        "status": "fail" if missing else "pass",
        "required": sorted(required),
        "missing": missing,
    }


def _disk_check(path: Path, min_free_gb: float) -> dict[str, Any]:
    path.mkdir(parents=True, exist_ok=True)
    usage = shutil.disk_usage(path)
    free_gb = usage.free / (1024**3)
    return {
        "name": "disk_space",
        "status": "pass" if free_gb >= min_free_gb else "fail",
        "path": str(path),
        "free_gb": round(free_gb, 3),
        "min_free_gb": float(min_free_gb),
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Preflight checks for the full 5090 training suite.")
    parser.add_argument("--project-root", default=str(PROJECT_ROOT))
    parser.add_argument("--jobs", default="all")
    parser.add_argument("--output-path", default=str(DEFAULT_OUTPUT_PATH))
    parser.add_argument("--require-cuda", action="store_true")
    parser.add_argument("--allow-cpu-smoke", action="store_true")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--min-free-gb", type=float, default=20.0)
    parser.add_argument("--require-paper-grade", action="store_true")
    args = parser.parse_args()

    project_root = Path(args.project_root)
    selected_jobs = _jobs(args.jobs)
    audit_jobs = [job for job in selected_jobs if job in TRACK_SPECS]
    checks: list[dict[str, Any]] = [
        {
            "name": "python_version",
            "status": "fail" if sys.version_info >= (3, 13) else "pass",
            "version": sys.version,
        },
        _gpu_check(require_cuda=args.require_cuda, smoke=args.smoke, allow_cpu_smoke=args.allow_cpu_smoke),
        _dependency_check(selected_jobs, smoke=args.smoke),
        _disk_check(project_root / "storage", args.min_free_gb),
    ]

    audit = audit_project(
        project_root=project_root,
        require_paper_grade=args.require_paper_grade,
        jobs=audit_jobs,
    )
    checks.append(
        {
            "name": "data_audit",
            "status": audit["status"],
            "issue_count": len(audit["issues"]),
            "issues": audit["issues"],
        }
    )

    status = "fail" if any(check["status"] == "fail" for check in checks) else "pass"
    payload = {
        "generated_at": _utc_now(),
        "project_root": str(project_root),
        "jobs": selected_jobs,
        "smoke": bool(args.smoke),
        "status": status,
        "checks": checks,
    }
    _write_json(Path(args.output_path), payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 1 if status == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
