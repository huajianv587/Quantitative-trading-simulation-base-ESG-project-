from __future__ import annotations

import argparse
import hashlib
import json
import os
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARCHIVE_PATH = PROJECT_ROOT / "delivery" / "esg_quant_autodl_sync.tar.gz"

INCLUDE_FILES = [
    ".env.example",
    ".env.quant_rl.example",
    "README.md",
    "data/__init__.py",
    "pyproject.toml",
    "pytest.ini",
    "requirements.txt",
    "requirements-quant-rl.txt",
    "docker-compose.5090.yml",
]

INCLUDE_DIRS = [
    "api",
    "backtest",
    "config",
    "configs",
    "database",
    "docs",
    "esg_reports",
    "gateway",
    "quant_rl",
    "rag",
    "reporting",
    "risk",
    "scripts",
    "training",
    "data/advanced_decision",
    "data/alpha_ranker",
    "data/data_ingestion_scripts",
    "data/event_classifier",
    "data/governance",
    "data/ingestion",
    "data/p1_stack",
    "data/p2_stack",
    "data/rag_training_data",
    "model-serving",
    "storage/esg_corpus",
    "storage/rag/esg_reports_openai_3072",
    "storage/quant/rl-experiments/paper-run",
]

EXCLUDED_PARTS = {
    ".git",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".pytest_cache",
    ".cache",
    "node_modules",
    "delivery",
    "dist",
    "build",
    "test-results",
    "playwright-report",
}

EXCLUDED_SUFFIXES = {
    ".pyc",
    ".pyo",
    ".log",
    ".tmp",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_value(project_root: Path, args: list[str]) -> str | None:
    import subprocess

    try:
        result = subprocess.run(
            ["git", *args],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _git_snapshot(project_root: Path) -> dict[str, Any]:
    return {
        "commit": _git_value(project_root, ["rev-parse", "HEAD"]),
        "branch": _git_value(project_root, ["branch", "--show-current"]),
        "status_short": _git_value(project_root, ["status", "--short"]),
    }


def _is_excluded(path: Path, project_root: Path, *, include_existing_checkpoints: bool, include_local_models: bool) -> bool:
    relative = path.relative_to(project_root)
    parts = set(relative.parts)
    if ".env" == relative.as_posix():
        return True
    if parts & EXCLUDED_PARTS:
        return True
    if path.suffix in EXCLUDED_SUFFIXES:
        return True
    rel = relative.as_posix()
    if rel.startswith("model-serving/checkpoint/") and not include_existing_checkpoints:
        return True
    if rel == "training/full_training_run_manifest.json":
        return True
    if rel.startswith("training/p0_assets/models/") and not include_local_models:
        return True
    if rel.startswith("training/p1_assets/") or rel.startswith("training/p2_assets/"):
        return True
    return False


def _iter_files(
    project_root: Path,
    *,
    include_existing_checkpoints: bool,
    include_local_models: bool,
) -> Iterable[Path]:
    seen: set[Path] = set()
    candidates: list[Path] = []
    candidates.extend(project_root / item for item in INCLUDE_FILES)
    candidates.extend(project_root / item for item in INCLUDE_DIRS)

    for candidate in candidates:
        if not candidate.exists():
            continue
        if candidate.is_file():
            if not _is_excluded(
                candidate,
                project_root,
                include_existing_checkpoints=include_existing_checkpoints,
                include_local_models=include_local_models,
            ):
                resolved = candidate.resolve()
                if resolved not in seen:
                    seen.add(resolved)
                    yield candidate
            continue
        for path in candidate.rglob("*"):
            if not path.is_file():
                continue
            if _is_excluded(
                path,
                project_root,
                include_existing_checkpoints=include_existing_checkpoints,
                include_local_models=include_local_models,
            ):
                continue
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            yield path


def build_bundle(
    *,
    project_root: Path,
    archive_path: Path,
    include_existing_checkpoints: bool = False,
    include_local_models: bool = True,
    allow_dirty: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    project_root = project_root.resolve()
    archive_path = archive_path.resolve()
    git = _git_snapshot(project_root)
    dirty = bool(git.get("status_short"))
    if dirty and not allow_dirty:
        raise SystemExit("Refusing to build AutoDL bundle from a dirty git worktree. Use --allow-dirty for tests only.")

    files = sorted(
        _iter_files(
            project_root,
            include_existing_checkpoints=include_existing_checkpoints,
            include_local_models=include_local_models,
        ),
        key=lambda item: item.relative_to(project_root).as_posix(),
    )
    entries: list[dict[str, Any]] = []
    total_bytes = 0
    for path in files:
        relative = path.relative_to(project_root).as_posix()
        size = path.stat().st_size
        total_bytes += size
        entries.append(
            {
                "path": relative,
                "size_bytes": size,
                "sha256": _sha256(path),
            }
        )

    manifest = {
        "generated_at": _utc_now(),
        "project_root": str(project_root),
        "archive_path": str(archive_path),
        "archive_name": archive_path.name,
        "git": git,
        "include_existing_checkpoints": bool(include_existing_checkpoints),
        "include_local_models": bool(include_local_models),
        "dry_run": bool(dry_run),
        "file_count": len(entries),
        "total_bytes": total_bytes,
        "entries": entries,
        "excluded": {
            "env": ".env",
            "git": ".git",
            "venv": ".venv/venv/env",
            "delivery": "old archives and generated bundles",
            "checkpoints": "model-serving/checkpoint unless --include-existing-checkpoints",
        },
    }

    if dry_run:
        return manifest

    archive_path.parent.mkdir(parents=True, exist_ok=True)
    bundle_root_name = project_root.name
    manifest_bytes = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
    with tarfile.open(archive_path, "w:gz") as archive:
        for path in files:
            relative = path.relative_to(project_root).as_posix()
            archive.add(path, arcname=f"{bundle_root_name}/{relative}", recursive=False)
        info = tarfile.TarInfo(name=f"{bundle_root_name}/bundle_manifest.json")
        info.size = len(manifest_bytes)
        info.mtime = int(datetime.now(timezone.utc).timestamp())
        import io

        archive.addfile(info, io.BytesIO(manifest_bytes))

    archive_sha = _sha256(archive_path)
    sha_path = archive_path.with_suffix(archive_path.suffix + ".sha256")
    if archive_path.name.endswith(".tar.gz"):
        sha_path = archive_path.with_name(archive_path.name[:-7] + ".sha256")
    sha_path.write_text(f"{archive_sha}  {archive_path.name}\n", encoding="utf-8")

    manifest["archive_size_bytes"] = archive_path.stat().st_size
    manifest["archive_sha256"] = archive_sha
    manifest["sha256_path"] = str(sha_path)
    manifest_path = archive_path.with_name(archive_path.name + ".manifest.json")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest["manifest_path"] = str(manifest_path)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the full AutoDL Stage 1 sync tarball.")
    parser.add_argument("--project-root", default=str(PROJECT_ROOT))
    parser.add_argument("--archive-path", default=str(DEFAULT_ARCHIVE_PATH))
    parser.add_argument("--include-existing-checkpoints", action="store_true")
    parser.add_argument("--no-local-models", action="store_true", help="Do not include local FinBERT/DeBERTa assets.")
    parser.add_argument("--allow-dirty", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    manifest = build_bundle(
        project_root=Path(args.project_root),
        archive_path=Path(args.archive_path),
        include_existing_checkpoints=args.include_existing_checkpoints,
        include_local_models=not args.no_local_models,
        allow_dirty=args.allow_dirty,
        dry_run=args.dry_run,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
