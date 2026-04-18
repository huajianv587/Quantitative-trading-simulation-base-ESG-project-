from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from training.stage2_data_audit import EXPECTED_UNIVERSE, audit_manifest

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _source() -> dict[str, str]:
    return {
        "provider": "unit",
        "source_uri": "https://example.test/source",
        "timestamp": "2025-01-02T00:00:00Z",
        "checksum": "sha256:unit",
        "license_note": "unit-test",
    }


def _dataset(track: str, split: str) -> dict[str, object]:
    return {
        "path": f"storage/stage2_data_quality/datasets/{track}/{split}.jsonl",
        "split": split,
        "rows": 12,
        "sources": [_source()],
        "label_columns": ["label"],
        "target_columns": ["target"],
    }


def _valid_manifest() -> dict[str, object]:
    tracks = {}
    for track in ["lora", "event", "alpha", "p1", "p2"]:
        tracks[track] = {
            "status": "paper_grade",
            "datasets": [_dataset(track, "train"), _dataset(track, "val"), _dataset(track, "test")],
            "lineage": "raw -> reviewed -> split",
            "review": {
                "dual_review_rate": 0.12,
                "cohen_kappa": 0.75,
                "adjudication_log": f"storage/stage2_data_quality/adjudication/{track}.csv",
            },
            "leakage_audit": {"status": "pass", "notes": "unit"},
        }
    return {
        "version": "stage2-paper-grade-v1",
        "generated_at": "2026-04-18T00:00:00Z",
        "universe": sorted(EXPECTED_UNIVERSE),
        "splits": {
            "train": {"start": "2022-01-01", "end": "2023-12-31"},
            "val": {"start": "2024-01-01", "end": "2024-12-31"},
            "test": {"start": "2025-01-01", "end": "2025-12-31"},
        },
        "tracks": tracks,
    }


def test_stage2_audit_accepts_complete_paper_grade_manifest():
    report = audit_manifest(_valid_manifest())

    assert report["status"] == "pass"
    assert report["paper_grade_ready"] is True


def test_stage2_audit_fails_missing_test_split():
    manifest = _valid_manifest()
    manifest["tracks"]["event"]["datasets"] = [
        item for item in manifest["tracks"]["event"]["datasets"] if item["split"] != "test"
    ]

    report = audit_manifest(manifest)

    assert report["status"] == "fail"
    assert any(issue["rule"] == "missing_or_empty_split" and issue["track"] == "event" for issue in report["issues"])


def test_stage2_prepare_plan_writes_only_stage2_artifacts(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            "training/stage2_prepare_plan.py",
            "--output-root",
            str(tmp_path / "stage2"),
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "stage2" / "stage2_prepare_plan.json").exists()
    assert (tmp_path / "stage2" / "stage2_data_manifest.json").exists()
    assert (tmp_path / "stage2" / "label_queue" / "event.csv").exists()

    manifest = json.loads((tmp_path / "stage2" / "stage2_data_manifest.json").read_text(encoding="utf-8"))
    assert manifest["tracks"]["event"]["status"] == "planned"
