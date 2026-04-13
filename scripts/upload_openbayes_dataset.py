from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUNDLE_DIR = PROJECT_ROOT / "delivery" / "openbayes" / "esg_quant_p0_training_bundle"
for env_name in (".env", ".envl"):
    env_path = PROJECT_ROOT / env_name
    if env_path.exists():
        load_dotenv(env_path, override=False)


def run_command(command: list[str], *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Upload the prepared ESG Quant P0 bundle to OpenBayes.")
    parser.add_argument("--dataset-id", default=os.getenv("OPENBAYES_DATASET_ID", "HucMvPZuFf0"), help="OpenBayes dataset id.")
    parser.add_argument("--version", type=int, default=int(os.getenv("OPENBAYES_DATASET_VERSION", "1")), help="Target dataset version.")
    parser.add_argument("--bundle-dir", default=str(DEFAULT_BUNDLE_DIR), help="Local bundle directory to upload.")
    parser.add_argument("--token", default=os.getenv("OPENBAYES_TOKEN", ""), help="OpenBayes token. Falls back to OPENBAYES_TOKEN.")
    parser.add_argument("--include-local-models", action="store_true", help="Rebuild bundle with downloaded optional model files.")
    parser.add_argument("--rebuild", action="store_true", help="Rebuild the bundle before uploading.")
    parser.add_argument("--open", action="store_true", help="Open dataset page in browser after successful upload.")
    args = parser.parse_args()

    bundle_dir = Path(args.bundle_dir)
    if args.rebuild or not bundle_dir.exists():
        build_cmd = [
            sys.executable,
            "scripts/build_openbayes_dataset.py",
            "--output-dir",
            str(bundle_dir),
            "--clean",
        ]
        if args.include_local_models:
            build_cmd.append("--include-local-models")
        build_result = run_command(build_cmd, env=os.environ.copy())
        if build_result.returncode != 0:
            print(
                json.dumps(
                    {
                        "ok": False,
                        "stage": "build_bundle",
                        "stdout": build_result.stdout,
                        "stderr": build_result.stderr,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 1

    token = str(args.token or "").strip()
    if not token:
        print(
            json.dumps(
                {
                    "ok": False,
                    "stage": "login",
                    "message": "Missing OPENBAYES_TOKEN. Add it to .env or pass --token.",
                    "dataset_id": args.dataset_id,
                    "bundle_dir": str(bundle_dir),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1

    login_result = run_command(["bayes", "login", token], env=os.environ.copy())
    if login_result.returncode != 0:
        print(
            json.dumps(
                {
                    "ok": False,
                    "stage": "login",
                    "stdout": login_result.stdout,
                    "stderr": login_result.stderr,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1

    upload_cmd = [
        "bayes",
        "data",
        "upload",
        args.dataset_id,
        "--version",
        str(args.version),
        "--path",
        str(bundle_dir),
    ]
    if args.open:
        upload_cmd.append("--open")
    upload_result = run_command(upload_cmd, env=os.environ.copy())
    ok = upload_result.returncode == 0
    print(
        json.dumps(
            {
                "ok": ok,
                "stage": "upload",
                "dataset_id": args.dataset_id,
                "version": args.version,
                "bundle_dir": str(bundle_dir),
                "stdout": upload_result.stdout,
                "stderr": upload_result.stderr,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
