from __future__ import annotations

import argparse
import sys
from pathlib import Path


SECRET_MARKERS = ("TOKEN", "SECRET", "KEY", "PASSWORD")


def masked(key: str, value: str) -> str:
    if any(marker in key.upper() for marker in SECRET_MARKERS):
        return "<masked>"
    return value


def parse_assignment(raw: str) -> tuple[str, str]:
    if "=" not in raw:
        raise argparse.ArgumentTypeError(f"Invalid assignment {raw!r}; expected KEY=VALUE")
    key, value = raw.split("=", 1)
    key = key.strip()
    if not key:
        raise argparse.ArgumentTypeError("Env key cannot be empty")
    return key, value


def upsert_env(path: Path, assignments: list[tuple[str, str]]) -> list[str]:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines() if path.exists() else []
    index: dict[str, int] = {}
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key = stripped.split("=", 1)[0].strip()
        if key and key not in index:
            index[key] = idx

    changed: list[str] = []
    for key, value in assignments:
        new_line = f"{key}={value}"
        if key in index:
            if lines[index[key]] != new_line:
                lines[index[key]] = new_line
                changed.append(key)
        else:
            if lines and lines[-1].strip():
                lines.append("")
            lines.append(new_line)
            changed.append(key)

    if changed:
        path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description="Idempotently upsert selected .env keys without printing secrets.")
    parser.add_argument("--file", type=Path, required=True)
    parser.add_argument("assignments", nargs="+", type=parse_assignment)
    args = parser.parse_args()
    changed = upsert_env(args.file, args.assignments)
    summary = {
        "file": str(args.file),
        "changed": [{key: masked(key, value)} for key, value in args.assignments if key in changed],
        "changed_count": len(changed),
    }
    print(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
