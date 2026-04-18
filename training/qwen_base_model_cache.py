from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL_NAME = "Qwen/Qwen2.5-7B-Instruct"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "storage" / "full-training-runs" / "qwen_base_model_cache_check.json"
SMALL_HASH_LIMIT_BYTES = 50 * 1024 * 1024


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _snapshot_download(model_name: str, *, revision: str | None, local_dir: Path | None) -> Path:
    from huggingface_hub import snapshot_download

    kwargs: dict[str, Any] = {"repo_id": model_name, "revision": revision, "resume_download": True}
    if local_dir:
        kwargs["local_dir"] = str(local_dir)
        kwargs["local_dir_use_symlinks"] = False
    downloaded = snapshot_download(**kwargs)
    return Path(downloaded)


def _scan_model_dir(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {
            "exists": False,
            "path": None,
            "file_count": 0,
            "total_bytes": 0,
            "required_files": {},
            "files": [],
        }
    files = [item for item in path.rglob("*") if item.is_file()] if path.exists() else []
    required_names = ["config.json", "tokenizer_config.json"]
    required = {name: any(item.name == name for item in files) for name in required_names}
    scanned_files: list[dict[str, Any]] = []
    for item in sorted(files, key=lambda p: p.relative_to(path).as_posix()):
        size = item.stat().st_size
        entry: dict[str, Any] = {
            "path": item.relative_to(path).as_posix(),
            "size_bytes": size,
        }
        if size <= SMALL_HASH_LIMIT_BYTES:
            entry["sha256"] = _sha256(item)
        else:
            entry["sha256"] = None
            entry["sha256_note"] = "skipped_large_file"
        scanned_files.append(entry)
    return {
        "exists": path.exists(),
        "path": str(path),
        "file_count": len(files),
        "total_bytes": sum(item.stat().st_size for item in files),
        "required_files": required,
        "files": scanned_files,
    }


def check_or_download(
    *,
    model_name: str = DEFAULT_MODEL_NAME,
    local_dir: Path | None = None,
    output_path: Path = DEFAULT_OUTPUT_PATH,
    revision: str | None = None,
    download: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    resolved_dir = local_dir
    error: str | None = None
    if download and not dry_run:
        try:
            resolved_dir = _snapshot_download(model_name, revision=revision, local_dir=local_dir)
        except Exception as exc:
            error = str(exc)

    scan = _scan_model_dir(resolved_dir)
    has_required = bool(scan["exists"]) and all(scan["required_files"].values())
    status = "pass" if (dry_run or has_required) and error is None else "fail"
    if not download and not has_required and not dry_run:
        status = "warn"

    payload = {
        "generated_at": _utc_now(),
        "model_name": model_name,
        "revision": revision,
        "download_requested": bool(download),
        "dry_run": bool(dry_run),
        "hf_endpoint": os.environ.get("HF_ENDPOINT"),
        "hf_home": os.environ.get("HF_HOME"),
        "status": status,
        "error": error,
        "cache": scan,
        "note": "Qwen base weights are intentionally not bundled; AutoDL should pre-download them before LoRA training.",
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Pre-download or verify the Qwen base model cache for LoRA training.")
    parser.add_argument("--model-name", default=os.environ.get("QWEN_MODEL_NAME", DEFAULT_MODEL_NAME))
    parser.add_argument("--revision", default=os.environ.get("QWEN_REVISION"))
    parser.add_argument("--local-dir", default=os.environ.get("QWEN_LOCAL_DIR"))
    parser.add_argument("--output-path", default=os.environ.get("QWEN_CACHE_REPORT", str(DEFAULT_OUTPUT_PATH)))
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    payload = check_or_download(
        model_name=args.model_name,
        local_dir=Path(args.local_dir) if args.local_dir else None,
        output_path=Path(args.output_path),
        revision=args.revision,
        download=args.download,
        dry_run=args.dry_run,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 1 if payload["status"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
