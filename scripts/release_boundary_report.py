from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections import defaultdict
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CATEGORY_PREFIXES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("auth", ("gateway/api/routers/auth.py", "gateway/auth/", "gateway/ops/security.py")),
    ("runtime", ("gateway/app_runtime.py", "gateway/main.py", "gateway/api/factory.py", "gateway/api/routers/ops.py")),
    ("storage", ("gateway/quant/storage.py", "gateway/quant/market_data.py", "storage/", "data/")),
    ("frontend", ("frontend/", "dist/")),
    ("e2e", ("e2e/", "playwright.config.js")),
    ("ci", (".github/workflows/", "pytest.ini", "pyproject.toml", "requirements.txt", "package.json")),
    ("artifact-cleanup", ("model-serving/checkpoint/", "delivery/", "outputs_", "paper_exports/", ".dockerignore", ".gitignore")),
)
CHECKPOINT_PREFIX = "model-serving/checkpoint/"


def _run_git(args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or f"git {' '.join(args)} failed")
    return result.stdout


def _status_rows(base_ref: str | None) -> list[dict[str, str]]:
    if base_ref:
        output = _run_git(["-c", "core.quotePath=false", "diff", "--name-status", f"{base_ref}...HEAD"])
        rows = []
        for line in output.splitlines():
            parts = line.split("\t")
            if not parts:
                continue
            status = parts[0]
            path = parts[-1]
            rows.append({"status": status, "path": path.replace("\\", "/")})
        return rows

    output = _run_git(["-c", "core.quotePath=false", "status", "--porcelain=v1"])
    rows = []
    for line in output.splitlines():
        if not line:
            continue
        status = line[:2].strip() or "?"
        path = line[3:].strip().strip('"').replace("\\", "/")
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        rows.append({"status": status, "path": path})
    return rows


def _category_for(path: str) -> str:
    normalized = path.replace("\\", "/")
    for category, prefixes in CATEGORY_PREFIXES:
        if any(normalized == prefix.rstrip("/") or normalized.startswith(prefix) for prefix in prefixes):
            return category
    return "other"


def build_report(base_ref: str | None) -> dict[str, object]:
    rows = _status_rows(base_ref)
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    checkpoint_deletions: list[str] = []
    for row in rows:
        path = row["path"]
        status = row["status"]
        category = _category_for(path)
        grouped[category].append(row)
        if path.startswith(CHECKPOINT_PREFIX) and "D" in status:
            checkpoint_deletions.append(path)

    return {
        "base_ref": base_ref,
        "changed_file_count": len(rows),
        "groups": {category: items for category, items in sorted(grouped.items())},
        "manual_review_required": {
            "checkpoint_deletions": checkpoint_deletions,
            "required": bool(checkpoint_deletions),
            "reason": "checkpoint artifact deletions must be explicitly reviewed before release",
        },
    }


def _default_base_ref() -> str | None:
    base = os.getenv("GITHUB_BASE_REF", "").strip()
    if base:
        return f"origin/{base}"
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Group changed files by release stability boundary.")
    parser.add_argument("--base-ref", default=_default_base_ref(), help="Optional git base ref for diff mode.")
    parser.add_argument("--strict-artifacts", action="store_true", help="Fail when checkpoint artifact deletions are present.")
    args = parser.parse_args()

    report = build_report(args.base_ref)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    manual = report["manual_review_required"]
    if args.strict_artifacts and manual["required"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
