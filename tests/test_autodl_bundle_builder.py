from __future__ import annotations

import tarfile
from pathlib import Path

from training.build_autodl_sync_bundle import build_bundle
from training.verify_autodl_bundle import verify_bundle


def test_autodl_bundle_excludes_env_and_checkpoints(tmp_path):
    project = tmp_path / "repo"
    (project / "scripts").mkdir(parents=True)
    (project / "training").mkdir()
    (project / "data" / "alpha_ranker").mkdir(parents=True)
    (project / "data" / "auth").mkdir(parents=True)
    (project / "storage" / "quant" / "rl" / "datasets" / "paper-run_full_2022_2025_l4_no_esg").mkdir(parents=True)
    (project / "storage" / "esg_corpus").mkdir(parents=True)
    (project / "model-serving" / "checkpoint" / "alpha_ranker").mkdir(parents=True)

    (project / ".env").write_text("SECRET=do-not-ship\n", encoding="utf-8")
    (project / "README.md").write_text("unit\n", encoding="utf-8")
    (project / "scripts" / "run.sh").write_text("echo hi\n", encoding="utf-8")
    (project / "training" / "train.py").write_text("print('hi')\n", encoding="utf-8")
    (project / "data" / "alpha_ranker" / "train.csv").write_text("x\n1\n", encoding="utf-8")
    (project / "data" / "auth" / "secret.json").write_text("{}", encoding="utf-8")
    (project / "storage" / "esg_corpus" / "manifest.json").write_text("{}", encoding="utf-8")
    (project / "storage" / "quant" / "rl" / "datasets" / "paper-run_full_2022_2025_l4_no_esg" / "merged_market.csv").write_text("x\n1\n", encoding="utf-8")
    (project / "model-serving" / "checkpoint" / "alpha_ranker" / "model.joblib").write_text("model", encoding="utf-8")

    archive = tmp_path / "esg_quant_autodl_sync.tar.gz"
    manifest = build_bundle(project_root=project, archive_path=archive, allow_dirty=True)

    included = {entry["path"] for entry in manifest["entries"]}
    assert ".env" not in included
    assert "data/auth/secret.json" not in included
    assert "model-serving/checkpoint/alpha_ranker/model.joblib" not in included
    assert "scripts/run.sh" in included
    assert "storage/quant/rl/datasets/paper-run_full_2022_2025_l4_no_esg/merged_market.csv" in included
    assert archive.exists()
    assert (tmp_path / "esg_quant_autodl_sync.sha256").exists()

    with tarfile.open(archive, "r:gz") as handle:
        names = set(handle.getnames())
    assert f"{project.name}/.env" not in names
    assert f"{project.name}/scripts/run.sh" in names


def test_autodl_bundle_can_dry_run_with_local_models_excluded(tmp_path):
    project = tmp_path / "repo"
    (project / "training" / "p0_assets" / "models" / "finbert").mkdir(parents=True)
    (project / "training" / "p0_assets" / "models" / "finbert" / "config.json").write_text("{}", encoding="utf-8")

    manifest = build_bundle(
        project_root=project,
        archive_path=tmp_path / "bundle.tar.gz",
        include_local_models=False,
        allow_dirty=True,
        dry_run=True,
    )

    included = {entry["path"] for entry in manifest["entries"]}
    assert "training/p0_assets/models/finbert/config.json" not in included
    assert manifest["dry_run"] is True


def test_autodl_bundle_verifier_detects_forbidden_env(tmp_path):
    project = tmp_path / "repo"
    project.mkdir()
    (project / ".env").write_text("SECRET=bad\n", encoding="utf-8")
    (project / "ok.py").write_text("print('ok')\n", encoding="utf-8")
    archive = tmp_path / "bundle.tar.gz"
    with tarfile.open(archive, "w:gz") as handle:
        handle.add(project / ".env", arcname=f"{project.name}/.env")
        handle.add(project / "ok.py", arcname=f"{project.name}/ok.py")

    report = verify_bundle(
        archive_path=archive,
        output_path=tmp_path / "verify.json",
        required_paths=[],
        run_data_audit=False,
    )

    assert report["status"] == "fail"
    forbidden = next(check for check in report["checks"] if check["name"] == "forbidden_files")
    assert ".env" in forbidden["forbidden"]
