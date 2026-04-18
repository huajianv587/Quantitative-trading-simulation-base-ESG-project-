from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from training.full_model_data_audit import audit_project

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_full_model_suite_dry_run_writes_isolated_manifest_and_logs(tmp_path):
    run_root = tmp_path / "runs"
    checkpoint_root = tmp_path / "checkpoints"
    result = subprocess.run(
        [
            sys.executable,
            "training/train_full_model_suite.py",
            "--jobs",
            "alpha",
            "--run-id",
            "unit",
            "--run-root",
            str(run_root),
            "--checkpoint-root",
            str(checkpoint_root),
            "--dry-run",
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    manifest_path = run_root / "unit" / "full_training_manifest.json"
    status_path = run_root / "unit" / "status" / "train_alpha_ranker.json"
    stdout_path = run_root / "unit" / "logs" / "train_alpha_ranker.stdout.log"
    assert manifest_path.exists()
    assert status_path.exists()
    assert stdout_path.exists()

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    train_status = json.loads(status_path.read_text(encoding="utf-8"))
    assert manifest["stage1_label"] == "stage1_baseline_checkpoint"
    assert str(checkpoint_root / "unit" / "alpha_ranker") in train_status["command"]
    assert train_status["checkpoint_dir"] == str(checkpoint_root / "unit" / "alpha_ranker")


def test_full_model_suite_resume_skips_completed_step(tmp_path):
    run_root = tmp_path / "runs"
    status_dir = run_root / "resume" / "status"
    status_dir.mkdir(parents=True)
    status_path = status_dir / "train_alpha_ranker.json"
    status_path.write_text(
        json.dumps({"step": "train_alpha_ranker", "status": "completed"}),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "training/train_full_model_suite.py",
            "--jobs",
            "alpha",
            "--run-id",
            "resume",
            "--run-root",
            str(run_root),
            "--checkpoint-root",
            str(tmp_path / "checkpoints"),
            "--dry-run",
            "--resume",
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(status_path.read_text(encoding="utf-8"))
    assert payload["status"] == "completed"
    assert payload["resume_action"] == "skipped_completed"


def test_full_model_data_audit_stage1_warnings_do_not_fail():
    report = audit_project(project_root=PROJECT_ROOT, jobs=["alpha", "event"])

    assert report["status"] == "pass"
    assert any(issue["rule"] == "missing_independent_test" for issue in report["issues"])
    assert report["tracks"]["alpha"]["role"] == "stage1_baseline_checkpoint"


def test_full_model_preflight_allows_cpu_smoke(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            "training/full_model_preflight.py",
            "--jobs",
            "alpha",
            "--require-cuda",
            "--smoke",
            "--allow-cpu-smoke",
            "--min-free-gb",
            "0",
            "--output-path",
            str(tmp_path / "preflight.json"),
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads((tmp_path / "preflight.json").read_text(encoding="utf-8"))
    assert payload["status"] == "pass"
