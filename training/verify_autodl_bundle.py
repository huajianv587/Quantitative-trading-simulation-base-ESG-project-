from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARCHIVE = PROJECT_ROOT / "delivery" / "esg_quant_autodl_sync.tar.gz"

FORBIDDEN_EXACT = {".env"}
FORBIDDEN_PREFIXES = {
    ".git/",
    ".venv/",
    "venv/",
    "env/",
    "data/auth/",
    "delivery/",
    "model-serving/checkpoint/",
}

REQUIRED_PATHS = [
    "bundle_manifest.json",
    "storage/esg_corpus/manifest.json",
    "storage/rag/esg_reports_openai_3072/embedding_manifest.json",
    "storage/rag/esg_reports_openai_3072/chunk_manifest.csv",
    "storage/rag/esg_reports_openai_3072/embeddings.jsonl",
    "storage/quant/rl-experiments/paper-run/protocol/frozen_inputs_full_2022_2025.json",
    "storage/quant/rl-experiments/paper-run/protocol/frozen_inputs_post_esg_effective.json",
    "storage/quant/rl-experiments/paper-run/quality/full_2022_2025/no_esg/data_quality_report.json",
    "storage/quant/rl-experiments/paper-run/quality/full_2022_2025/house_esg/data_quality_report.json",
    "storage/quant/rl-experiments/paper-run/quality/post_esg_effective/no_esg/data_quality_report.json",
    "storage/quant/rl-experiments/paper-run/quality/post_esg_effective/house_esg/data_quality_report.json",
    "storage/quant/rl/datasets/paper-run_full_2022_2025_l4_no_esg/merged_market.csv",
    "storage/quant/rl/datasets/paper-run_full_2022_2025_l5_house_esg/merged_market.csv",
    "storage/quant/rl/datasets/paper-run_post_esg_effective_l4_no_esg/merged_market.csv",
    "storage/quant/rl/datasets/paper-run_post_esg_effective_l5_house_esg/merged_market.csv",
    "scripts/run_5090_stage1_all.sh",
    "scripts/autodl_run_paper_experiments.sh",
    "scripts/download_qwen_base_model.sh",
    "training/full_model_preflight.py",
    "training/full_model_data_audit.py",
    "training/train_full_model_suite.py",
]

PY_COMPILE_PATHS = [
    "scripts/quant_rl_expected_run_manifest.py",
    "scripts/quant_rl_esg_contribution_report.py",
    "scripts/sync_esg_embedding_manifest.py",
    "training/full_model_preflight.py",
    "training/full_model_data_audit.py",
    "training/train_full_model_suite.py",
    "training/qwen_base_model_cache.py",
]

BASH_CHECK_PATHS = [
    "scripts/run_5090_stage1_all.sh",
    "scripts/autodl_run_paper_experiments.sh",
    "scripts/download_qwen_base_model.sh",
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_output_path(archive_path: Path) -> Path:
    if archive_path.name.endswith(".tar.gz"):
        return archive_path.with_name(archive_path.name[:-7] + ".verify.json")
    return archive_path.with_suffix(archive_path.suffix + ".verify.json")


def _safe_extract(archive_path: Path, target_dir: Path) -> None:
    target_resolved = target_dir.resolve()
    with tarfile.open(archive_path, "r:gz") as archive:
        for member in archive.getmembers():
            destination = (target_dir / member.name).resolve()
            if not str(destination).startswith(str(target_resolved)):
                raise RuntimeError(f"Unsafe tar member path: {member.name}")
        archive.extractall(target_dir)


def _bundle_root(extract_dir: Path) -> Path:
    children = [path for path in extract_dir.iterdir() if path.is_dir()]
    if len(children) != 1:
        raise RuntimeError(f"Expected exactly one top-level directory in bundle, found {len(children)}")
    return children[0]


def _relative_members(bundle_root: Path) -> list[str]:
    return sorted(path.relative_to(bundle_root).as_posix() for path in bundle_root.rglob("*") if path.is_file())


def _forbidden_members(members: list[str]) -> list[str]:
    forbidden: list[str] = []
    for member in members:
        if member in FORBIDDEN_EXACT:
            forbidden.append(member)
            continue
        if any(member.startswith(prefix) for prefix in FORBIDDEN_PREFIXES):
            forbidden.append(member)
    return forbidden


def _run_command(command: list[str], *, cwd: Path, timeout: int = 120) -> dict[str, Any]:
    try:
        result = subprocess.run(command, cwd=cwd, text=True, capture_output=True, timeout=timeout, check=False)
    except Exception as exc:
        return {"command": command, "returncode": -1, "stdout": "", "stderr": str(exc), "status": "fail"}
    return {
        "command": command,
        "returncode": result.returncode,
        "stdout": result.stdout[-4000:],
        "stderr": result.stderr[-4000:],
        "status": "pass" if result.returncode == 0 else "fail",
    }


def verify_bundle(
    *,
    archive_path: Path = DEFAULT_ARCHIVE,
    output_path: Path | None = None,
    work_dir: Path | None = None,
    keep_extract: bool = False,
    required_paths: list[str] | None = None,
    run_data_audit: bool = True,
) -> dict[str, Any]:
    archive_path = Path(archive_path)
    output_path = output_path or _default_output_path(archive_path)
    checks: list[dict[str, Any]] = []
    extract_parent: Path | None = None

    try:
        if work_dir is None:
            extract_parent = Path(tempfile.mkdtemp(prefix="autodl_bundle_verify_"))
        else:
            work_dir.mkdir(parents=True, exist_ok=True)
            extract_parent = work_dir
        _safe_extract(archive_path, extract_parent)
        root = _bundle_root(extract_parent)
        members = _relative_members(root)

        forbidden = _forbidden_members(members)
        checks.append({"name": "forbidden_files", "status": "fail" if forbidden else "pass", "forbidden": forbidden})

        required = required_paths if required_paths is not None else REQUIRED_PATHS
        missing_required = [path for path in required if path not in members]
        checks.append({"name": "required_files", "status": "fail" if missing_required else "pass", "missing": missing_required})

        compile_targets = [str(root / path) for path in PY_COMPILE_PATHS if (root / path).exists()]
        if compile_targets:
            checks.append({"name": "py_compile", **_run_command([sys.executable, "-m", "py_compile", *compile_targets], cwd=root)})
        else:
            checks.append({"name": "py_compile", "status": "fail", "error": "no compile targets found"})

        bash_path = shutil.which("bash")
        if bash_path:
            bash_results = [_run_command([bash_path, "-n", path], cwd=root) for path in BASH_CHECK_PATHS if (root / path).exists()]
            checks.append({"name": "bash_syntax", "status": "fail" if any(item["status"] == "fail" for item in bash_results) else "pass", "results": bash_results})
        else:
            checks.append({"name": "bash_syntax", "status": "warn", "message": "bash is not available on this host"})

        if run_data_audit:
            audit_output = extract_parent / "audit"
            checks.append(
                {
                    "name": "full_model_data_audit",
                    **_run_command(
                        [
                            sys.executable,
                            "training/full_model_data_audit.py",
                            "--project-root",
                            str(root),
                            "--jobs",
                            "all",
                            "--output-dir",
                            str(audit_output),
                        ],
                        cwd=root,
                        timeout=180,
                    ),
                }
            )

        status = "fail" if any(check["status"] == "fail" for check in checks) else "pass"
        payload = {
            "generated_at": _utc_now(),
            "archive_path": str(archive_path),
            "extract_root": str(root),
            "status": status,
            "checks": checks,
        }
    finally:
        if extract_parent is not None and not keep_extract and work_dir is None:
            shutil.rmtree(extract_parent, ignore_errors=True)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    payload["output_path"] = str(output_path)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract and verify the AutoDL sync bundle before upload/use.")
    parser.add_argument("--archive", default=str(DEFAULT_ARCHIVE))
    parser.add_argument("--output-path", default=None)
    parser.add_argument("--work-dir", default=None)
    parser.add_argument("--keep-extract", action="store_true")
    parser.add_argument("--skip-data-audit", action="store_true")
    args = parser.parse_args()

    payload = verify_bundle(
        archive_path=Path(args.archive),
        output_path=Path(args.output_path) if args.output_path else None,
        work_dir=Path(args.work_dir) if args.work_dir else None,
        keep_extract=args.keep_extract,
        run_data_audit=not args.skip_data_audit,
    )
    print(json.dumps({k: v for k, v in payload.items() if k != "checks"}, ensure_ascii=False, indent=2))
    return 1 if payload["status"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
