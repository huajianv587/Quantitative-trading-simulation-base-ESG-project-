from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Copy RL artifacts into a local target directory")
    parser.add_argument("--source", default="storage/quant/rl-experiments")
    parser.add_argument("--target", default="artifacts/quant-rl-pull")
    args = parser.parse_args()

    source = (ROOT / args.source).resolve() if not Path(args.source).is_absolute() else Path(args.source)
    target = (ROOT / args.target).resolve() if not Path(args.target).is_absolute() else Path(args.target)
    target.mkdir(parents=True, exist_ok=True)

    copied: list[str] = []
    for path in source.rglob("*"):
        if path.is_file():
            relative = path.relative_to(source)
            destination = target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)
            copied.append(str(destination))

    print(json.dumps({"source": str(source), "target": str(target), "files_copied": len(copied)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
