from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_NAMESPACE_ROOT = ROOT / "storage" / "quant" / "rl-experiments" / "paper-run"
DEFAULT_MANIFEST_PATH = DEFAULT_NAMESPACE_ROOT / "protocol" / "expected_run_manifest.json"
DEFAULT_REPORT_PATH = DEFAULT_NAMESPACE_ROOT / "summary" / "expected_run_verification.json"
DEFAULT_SAMPLES = ["full_2022_2025", "post_esg_effective"]
DEFAULT_FORMULAS = ["v2", "v2_1"]
DEFAULT_GROUPS = [
    "B1_buyhold",
    "B2_macd",
    "B3_sac_noesg",
    "B4_sac_esg",
    "OURS_full",
    "6a_no_esg_obs",
    "6b_no_esg_reward",
    "6c_no_regime",
]
DEFAULT_SEEDS = [42, 123, 456]
NO_ESG_GROUPS = {"B1_buyhold", "B2_macd", "B3_sac_noesg"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _git_commit() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return None


def _split(raw: str | None, default: list[str]) -> list[str]:
    if not raw:
        return list(default)
    return [item.strip() for item in raw.replace(",", " ").split() if item.strip()]


def _split_ints(raw: str | None, default: list[int]) -> list[int]:
    if not raw:
        return list(default)
    return [int(item.strip()) for item in raw.replace(",", " ").split() if item.strip()]


def build_expected_manifest(
    *,
    namespace_root: Path = DEFAULT_NAMESPACE_ROOT,
    samples: list[str] | None = None,
    formulas: list[str] | None = None,
    groups: list[str] | None = None,
    seeds: list[int] | None = None,
) -> dict[str, Any]:
    namespace_root = Path(namespace_root)
    samples = samples or list(DEFAULT_SAMPLES)
    formulas = formulas or list(DEFAULT_FORMULAS)
    groups = groups or list(DEFAULT_GROUPS)
    seeds = seeds or list(DEFAULT_SEEDS)

    runs: list[dict[str, Any]] = []
    for sample in samples:
        for formula in formulas:
            sample_root = namespace_root / f"formula_{formula}" / f"sample_{sample}"
            for group in groups:
                dataset_role = "no_esg" if group in NO_ESG_GROUPS else "house_esg"
                for seed in seeds:
                    run_dir = sample_root / "results" / group / f"seed{seed}"
                    runs.append(
                        {
                            "sample": sample,
                            "formula": formula,
                            "group": group,
                            "seed": seed,
                            "dataset_role": dataset_role,
                            "sample_root": str(sample_root),
                            "run_dir": str(run_dir),
                            "required_files": {
                                "metrics_json": str(run_dir / "metrics.json"),
                                "equity_curve_csv": str(run_dir / "equity_curve.csv"),
                                "run_status_json": str(run_dir / "run_status.json"),
                                "run_log": str(run_dir / "run.log"),
                            },
                            "group_log": str(sample_root / "logs" / f"{group}.log"),
                            "summary_dir": str(sample_root / "summary"),
                        }
                    )

    return {
        "generated_at": _utc_now(),
        "git_commit": _git_commit(),
        "namespace_root": str(namespace_root),
        "samples": samples,
        "formulas": formulas,
        "groups": groups,
        "seeds": seeds,
        "expected_run_count": len(runs),
        "matrix_shape": {
            "samples": len(samples),
            "formulas": len(formulas),
            "groups": len(groups),
            "seeds": len(seeds),
        },
        "runs": runs,
    }


def write_expected_manifest(manifest: dict[str, Any], path: Path = DEFAULT_MANIFEST_PATH) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest["manifest_path"] = str(path)
    return manifest


def _file_status(path: Path) -> dict[str, Any]:
    payload: dict[str, Any] = {"path": str(path), "exists": path.exists()}
    if path.exists() and path.is_file():
        payload["size_bytes"] = path.stat().st_size
    return payload


def verify_expected_manifest(
    *,
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
    report_path: Path | None = DEFAULT_REPORT_PATH,
    require_completed_status: bool = True,
) -> dict[str, Any]:
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    missing: list[dict[str, Any]] = []
    failed_statuses: list[dict[str, Any]] = []
    verified: list[dict[str, Any]] = []

    for run in manifest.get("runs") or []:
        file_checks = {name: _file_status(Path(path)) for name, path in (run.get("required_files") or {}).items()}
        group_log = _file_status(Path(run["group_log"]))
        absent = [name for name, item in file_checks.items() if not item["exists"]]
        if not group_log["exists"]:
            absent.append("group_log")
        if absent:
            missing.append({**{key: run.get(key) for key in ("sample", "formula", "group", "seed")}, "missing": absent})
        status_payload: dict[str, Any] | None = None
        status_path = Path((run.get("required_files") or {}).get("run_status_json", ""))
        if status_path.exists():
            try:
                status_payload = json.loads(status_path.read_text(encoding="utf-8"))
            except Exception as exc:
                failed_statuses.append({**{key: run.get(key) for key in ("sample", "formula", "group", "seed")}, "status": "invalid_json", "error": str(exc)})
            else:
                status = status_payload.get("status")
                if require_completed_status and status not in {"completed", "skipped_existing"}:
                    failed_statuses.append({**{key: run.get(key) for key in ("sample", "formula", "group", "seed")}, "status": status})
        verified.append(
            {
                "sample": run.get("sample"),
                "formula": run.get("formula"),
                "group": run.get("group"),
                "seed": run.get("seed"),
                "files": file_checks,
                "group_log": group_log,
                "run_status": status_payload,
            }
        )

    status = "fail" if missing or failed_statuses else "pass"
    report = {
        "generated_at": _utc_now(),
        "status": status,
        "manifest_path": str(manifest_path),
        "expected_run_count": int(manifest.get("expected_run_count") or 0),
        "verified_run_count": len(verified),
        "missing_count": len(missing),
        "failed_status_count": len(failed_statuses),
        "missing": missing,
        "failed_statuses": failed_statuses,
        "verified": verified,
    }
    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        report["report_path"] = str(report_path)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Build or verify the frozen paper-run expected run matrix.")
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build")
    build.add_argument("--namespace-root", default=str(DEFAULT_NAMESPACE_ROOT))
    build.add_argument("--output-path", default=str(DEFAULT_MANIFEST_PATH))
    build.add_argument("--samples", default=" ".join(DEFAULT_SAMPLES))
    build.add_argument("--formulas", default=" ".join(DEFAULT_FORMULAS))
    build.add_argument("--groups", default=" ".join(DEFAULT_GROUPS))
    build.add_argument("--seeds", default=",".join(str(seed) for seed in DEFAULT_SEEDS))

    verify = sub.add_parser("verify")
    verify.add_argument("--manifest-path", default=str(DEFAULT_MANIFEST_PATH))
    verify.add_argument("--report-path", default=str(DEFAULT_REPORT_PATH))
    verify.add_argument("--allow-running", action="store_true", help="Only check files, not completed run_status values.")

    args = parser.parse_args()
    if args.command == "build":
        manifest = build_expected_manifest(
            namespace_root=Path(args.namespace_root),
            samples=_split(args.samples, DEFAULT_SAMPLES),
            formulas=_split(args.formulas, DEFAULT_FORMULAS),
            groups=_split(args.groups, DEFAULT_GROUPS),
            seeds=_split_ints(args.seeds, DEFAULT_SEEDS),
        )
        manifest = write_expected_manifest(manifest, Path(args.output_path))
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        return 0

    report = verify_expected_manifest(
        manifest_path=Path(args.manifest_path),
        report_path=Path(args.report_path),
        require_completed_status=not args.allow_running,
    )
    print(json.dumps({k: v for k, v in report.items() if k != "verified"}, ensure_ascii=False, indent=2))
    return 1 if report["status"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
