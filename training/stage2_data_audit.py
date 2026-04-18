from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = PROJECT_ROOT / "storage" / "stage2_data_quality" / "stage2_data_manifest.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "storage" / "stage2_data_quality" / "audit" / "stage2_data_audit.json"

EXPECTED_UNIVERSE = {
    "AAPL",
    "MSFT",
    "NVDA",
    "GOOGL",
    "JPM",
    "BAC",
    "GS",
    "MS",
    "XOM",
    "CVX",
    "NEE",
    "ENPH",
    "AMZN",
    "WMT",
    "COST",
    "PG",
    "JNJ",
    "PFE",
    "UNH",
    "ABT",
}
REQUIRED_TRACKS = ["lora", "event", "alpha", "p1", "p2"]
REQUIRED_SOURCE_FIELDS = ["provider", "source_uri", "timestamp", "checksum", "license_note"]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _issue(issues: list[dict[str, str]], severity: str, rule: str, message: str, track: str = "") -> None:
    issues.append({"severity": severity, "track": track, "rule": rule, "message": message})


def _has_split(track_payload: dict[str, Any], split: str) -> bool:
    for dataset in track_payload.get("datasets", []):
        if dataset.get("split") == split and int(dataset.get("rows") or 0) > 0:
            return True
    return False


def _validate_sources(issues: list[dict[str, str]], track: str, dataset: dict[str, Any]) -> None:
    sources = dataset.get("sources") or []
    if not sources:
        _issue(issues, "fail", "missing_source", f"{track} dataset {dataset.get('path')} has no source records.", track)
        return
    for index, source in enumerate(sources):
        missing = [field for field in REQUIRED_SOURCE_FIELDS if not source.get(field)]
        if missing:
            _issue(
                issues,
                "fail",
                "incomplete_source",
                f"{track} dataset {dataset.get('path')} source #{index} missing {', '.join(missing)}.",
                track,
            )


def audit_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    issues: list[dict[str, str]] = []

    for field in ["version", "generated_at", "universe", "splits", "tracks"]:
        if field not in manifest:
            _issue(issues, "fail", "missing_manifest_field", f"Manifest missing top-level field {field}.")

    splits = manifest.get("splits") or {}
    for split in ["train", "val", "test"]:
        payload = splits.get(split)
        if not isinstance(payload, dict) or not payload.get("start") or not payload.get("end"):
            _issue(issues, "fail", "missing_split", f"Split {split} needs start and end.")

    universe = set(str(item) for item in manifest.get("universe", []))
    if universe != EXPECTED_UNIVERSE:
        _issue(
            issues,
            "warn",
            "universe_mismatch",
            "Stage 2 universe differs from the ESG/RL 20-company universe.",
        )

    tracks = manifest.get("tracks") or {}
    for track in REQUIRED_TRACKS:
        if track not in tracks:
            _issue(issues, "fail", "missing_track", f"Required Stage 2 track {track} is absent.", track)
            continue
        track_payload = tracks[track]
        status = str(track_payload.get("status", ""))
        if status not in {"planned", "collecting", "reviewing", "paper_grade", "not_paper_grade"}:
            _issue(issues, "fail", "invalid_track_status", f"{track} has invalid status {status}.", track)
        for split in ["train", "val", "test"]:
            if not _has_split(track_payload, split):
                _issue(issues, "fail", "missing_or_empty_split", f"{track} has no non-empty {split} dataset.", track)
        if not track_payload.get("lineage"):
            _issue(issues, "fail", "missing_lineage", f"{track} needs raw-to-processed lineage.", track)
        for dataset in track_payload.get("datasets", []):
            if not dataset.get("path"):
                _issue(issues, "fail", "missing_dataset_path", f"{track} dataset missing path.", track)
            _validate_sources(issues, track, dataset)

        review = track_payload.get("review") or {}
        if track in {"lora", "event"}:
            if float(review.get("dual_review_rate") or 0.0) < 0.10:
                _issue(issues, "fail", "low_dual_review_rate", f"{track} dual review rate is below 10%.", track)
        if track == "event":
            kappa = review.get("cohen_kappa")
            if kappa is None or float(kappa) < 0.70:
                _issue(issues, "fail", "low_label_agreement", "event classifier Cohen's kappa is below 0.70.", track)

        leakage = track_payload.get("leakage_audit") or {}
        if track in {"alpha", "p1", "p2"} and leakage.get("status") != "pass":
            _issue(issues, "fail", "leakage_audit_not_passed", f"{track} needs a passing leakage audit.", track)

    status = "fail" if any(issue["severity"] == "fail" for issue in issues) else "pass"
    return {
        "generated_at": _utc_now(),
        "status": status,
        "issues": issues,
        "paper_grade_ready": status == "pass",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Stage 2 paper-grade data manifest.")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        report = {
            "generated_at": _utc_now(),
            "status": "fail",
            "issues": [
                {
                    "severity": "fail",
                    "track": "",
                    "rule": "manifest_missing",
                    "message": f"{manifest_path} does not exist.",
                }
            ],
            "paper_grade_ready": False,
        }
    else:
        report = audit_manifest(json.loads(manifest_path.read_text(encoding="utf-8")))

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report["status"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
