from __future__ import annotations

import argparse
import json
import shutil
import sys
import tarfile
import tempfile
import time
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_DIRS = [
    "session_evidence",
    "executions",
    "submit_locks",
    "paper_outcomes",
    "paper_performance",
    "paper_attribution",
    "paper_cash_flows",
    "promotion_evidence",
    "alerts",
    "scheduler_events",
    "paper_daily_digest_deliveries",
    "paper_weekly_digests",
    "paper_weekly_digest_deliveries",
]


def safe_extract(archive_path: Path, target_dir: Path) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    resolved_target = target_dir.resolve()
    with tarfile.open(archive_path, "r:gz") as archive:
        for member in archive.getmembers():
            destination = (target_dir / member.name).resolve()
            if resolved_target not in destination.parents and destination != resolved_target:
                raise ValueError(f"Unsafe archive member path: {member.name}")
        archive.extractall(target_dir)


def validate_restore(target_dir: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    for name in REQUIRED_DIRS:
        path = target_dir / name
        files = sorted(path.glob("*.json")) if path.exists() else []
        readable = 0
        for file_path in files[:10]:
            try:
                json.loads(file_path.read_text(encoding="utf-8"))
                readable += 1
            except Exception:
                pass
        checks.append(
            {
                "name": name,
                "ok": path.exists() and readable > 0,
                "file_count": len(files),
                "readable_sample_count": readable,
            }
        )
    blockers = [row["name"] for row in checks if not row["ok"]]
    return {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "ready": not blockers,
        "blockers": blockers,
        "checks": checks,
    }


def create_self_test_archive(work_dir: Path) -> Path:
    source = work_dir / "source"
    for name in REQUIRED_DIRS:
        directory = source / name
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "sample.json").write_text(
            json.dumps({"record_type": name, "sample": True}, ensure_ascii=False),
            encoding="utf-8",
        )
    archive_path = work_dir / "self-test-backup.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        for name in REQUIRED_DIRS:
            archive.add(source / name, arcname=name)
    return archive_path


def latest_backup(storage_dir: Path) -> Path | None:
    backup_dir = storage_dir / "backups"
    if not backup_dir.exists():
        return None
    backups = sorted(backup_dir.glob("*.tar.gz"), key=lambda item: item.stat().st_mtime, reverse=True)
    return backups[0] if backups else None


def run_restore(args: argparse.Namespace) -> dict[str, Any]:
    if args.self_test:
        with tempfile.TemporaryDirectory(prefix="quant-restore-self-test-") as raw:
            work_dir = Path(raw)
            archive_path = create_self_test_archive(work_dir)
            restore_dir = work_dir / "restored"
            safe_extract(archive_path, restore_dir)
            result = validate_restore(restore_dir)
            result.update({"archive": str(archive_path), "restore_dir": str(restore_dir), "self_test": True})
            return result

    archive_path = args.archive
    if archive_path is None:
        archive_path = latest_backup(args.storage_dir)
    if archive_path is None or not archive_path.exists():
        return {
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "ready": False,
            "blockers": ["backup_archive_missing"],
            "checks": [],
        }
    restore_dir = args.restore_dir
    if restore_dir.exists() and args.clean:
        shutil.rmtree(restore_dir)
    safe_extract(archive_path, restore_dir)
    result = validate_restore(restore_dir)
    result.update({"archive": str(archive_path), "restore_dir": str(restore_dir), "self_test": False})
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Restore and validate a quant evidence backup archive.")
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--storage-dir", type=Path, default=PROJECT_ROOT / "storage" / "quant")
    parser.add_argument("--restore-dir", type=Path, default=PROJECT_ROOT / "storage" / "quant_restore_drill")
    parser.add_argument("--clean", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json-out", default="")
    args = parser.parse_args()
    result = run_restore(args)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.json_out:
        out = Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
    print(text)
    return 0 if result.get("ready") else 1


if __name__ == "__main__":
    sys.exit(main())
