import json
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd

from quant_rl.service.quant_service import QuantRLService
from scripts.quant_rl_esg_contribution_report import build_report
from scripts.quant_rl_paper_preflight import run_preflight


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _market_frame() -> pd.DataFrame:
    dates = pd.date_range("2025-01-02", periods=6, freq="B", tz="UTC")
    return pd.DataFrame(
        {
            "symbol": ["AAPL"] * len(dates),
            "timestamp": dates,
            "open": [100, 101, 102, 103, 104, 105],
            "high": [101, 102, 103, 104, 105, 106],
            "low": [99, 100, 101, 102, 103, 104],
            "close": [100, 101, 102, 103, 104, 105],
            "volume": [1_000_000] * len(dates),
            "house_score_v2": [0.76] * len(dates),
            "house_score_v2_1": [0.82] * len(dates),
            "esg_delta": [0.01] * len(dates),
            "esg_delta_v2_1": [0.01] * len(dates),
            "esg_confidence": [1.0] * len(dates),
            "esg_staleness_days": [0] * len(dates),
            "esg_missing_flag": [0] * len(dates),
            "sector_relative_esg": [0.12] * len(dates),
            "e_score": [0.8] * len(dates),
            "s_score": [0.7] * len(dates),
            "g_score": [0.75] * len(dates),
            "vix": [18.0] * len(dates),
            "us10y_yield": [0.04] * len(dates),
            "credit_spread": [0.01] * len(dates),
        }
    )


def test_ablation_no_esg_obs_keeps_reward_signal():
    service = QuantRLService()
    env = service.build_env(_market_frame(), action_type="continuous", experiment_group="6a_no_esg_obs")

    assert "house_score_v2_1" in env.df.columns
    assert "house_score_v2_1" not in env.observation_builder.feature_columns

    env.reset()
    _, _, _, _, info = env.step(1.0)
    assert info["reward_breakdown"]["esg_bonus"] > 0


def test_ablation_no_esg_reward_keeps_observation_but_zeroes_bonus():
    service = QuantRLService()
    env = service.build_env(_market_frame(), action_type="continuous", experiment_group="6b_no_esg_reward")

    assert "house_score_v2_1" in env.observation_builder.feature_columns

    env.reset()
    _, _, _, _, info = env.step(1.0)
    assert info["reward_breakdown"]["esg_bonus"] == 0


def test_ablation_no_regime_removes_regime_features_but_keeps_esg(tmp_path: Path):
    service = QuantRLService()
    prepared = service.prepare_dataframe(
        str(_write_dataset(tmp_path / "regime_dataset.csv")),
        use_demo_if_missing=False,
        experiment_group="6c_no_regime",
    )
    env = service.build_env(prepared, action_type="continuous", experiment_group="6c_no_regime")

    assert "vix" not in env.observation_builder.feature_columns
    assert "us10y_yield" not in env.observation_builder.feature_columns
    assert "credit_spread" not in env.observation_builder.feature_columns
    assert "house_score_v2_1" in env.observation_builder.feature_columns


def _write_dataset(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame = _market_frame()
    frame.to_csv(path, index=False)
    return path


def _write_suite_dataset(path: Path) -> Path:
    rows = []
    for start in ("2022-01-03", "2024-01-02", "2025-01-02"):
        dates = pd.date_range(start, periods=4, freq="B", tz="UTC")
        for idx, date in enumerate(dates):
            close = 100 + len(rows) + idx
            rows.append(
                {
                    "symbol": "AAPL",
                    "timestamp": date.isoformat(),
                    "open": close,
                    "high": close + 1,
                    "low": close - 1,
                    "close": close,
                    "volume": 1_000_000,
                    "provider": "alpaca",
                }
            )
    frame = pd.DataFrame(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)
    return path


def _write_protocol(path: Path, sample: str, dataset_path: Path) -> Path:
    payload = {
        "sample": sample,
        "paper_run_blocked": None,
        "data_quality": {"no_esg": {"status": "pass"}, "house_esg": {"status": "pass"}},
        "datasets": {
            "no_esg": {"merged_dataset_path": str(dataset_path)},
            "house_esg": {"merged_dataset_path": str(dataset_path)},
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_experiment_suite_uses_sample_isolated_output_roots(tmp_path: Path):
    dataset = _write_suite_dataset(tmp_path / "market.csv")
    env = os.environ.copy()
    env["QUANT_RL_STORAGE_DIR"] = str(tmp_path / "storage")
    env["QUANT_RL_SQLITE_DB_PATH"] = str(tmp_path / "storage" / "metadata.sqlite3")

    for sample in ("full_2022_2025", "post_esg_effective"):
        sample_root = tmp_path / f"formula_v2/sample_{sample}"
        protocol = _write_protocol(tmp_path / f"protocol_{sample}.json", sample, dataset)
        result = subprocess.run(
            [
                sys.executable,
                "scripts/quant_rl_experiment_suite.py",
                "--run-namespace",
                "paper-run",
                "--sample",
                sample,
                "--formula-mode",
                "v2",
                "--dataset-path",
                str(dataset),
                "--groups",
                "B1_buyhold",
                "--protocol-file",
                str(protocol),
                "--sample-output-root",
                str(sample_root),
                "--output-summary",
                str(sample_root / "summary.json"),
            ],
            cwd=PROJECT_ROOT,
            env=env,
            text=True,
            capture_output=True,
            timeout=60,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        assert (sample_root / "results" / "B1_buyhold" / "metrics.json").exists()
        assert (sample_root / "results" / "B1_buyhold" / "run_status.json").exists()

    full_metrics = tmp_path / "formula_v2/sample_full_2022_2025/results/B1_buyhold/metrics.json"
    post_metrics = tmp_path / "formula_v2/sample_post_esg_effective/results/B1_buyhold/metrics.json"
    assert full_metrics.exists()
    assert post_metrics.exists()
    assert full_metrics != post_metrics


def _write_metric_and_curve(root: Path, group: str, seed: int, sharpe: float, offset: float) -> None:
    run_dir = root / "results" / group / f"seed{seed}"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "metrics.json").write_text(
        json.dumps(
            {
                "group": group,
                "seed": seed,
                "annual_return": offset,
                "sharpe_ratio": sharpe,
                "sortino_ratio": sharpe,
                "max_drawdown": 0.1,
                "calmar_ratio": sharpe,
                "turnover_rate": 0.2,
                "win_rate": 0.55,
            }
        ),
        encoding="utf-8",
    )
    pd.DataFrame(
        {
            "date": ["2025-01-02", "2025-01-03", "2025-01-06"],
            "portfolio_value": [100000, 100000 * (1 + offset), 100000 * (1 + offset * 2)],
            "daily_return": [0.0, offset, offset],
            "position": [0.0, 1.0, 1.0],
            "regime": ["", "", ""],
        }
    ).to_csv(run_dir / "equity_curve.csv", index=False)


def test_contribution_report_writes_equity_bootstrap_and_markdown(tmp_path: Path):
    _write_metric_and_curve(tmp_path, "B3_sac_noesg", 42, 0.5, 0.001)
    _write_metric_and_curve(tmp_path, "B4_sac_esg", 42, 0.8, 0.002)
    _write_metric_and_curve(tmp_path, "OURS_full", 42, 1.0, 0.003)

    report = build_report(tmp_path / "results", tmp_path / "summary", metadata={"sample": "full_2022_2025"})

    assert report["equity_curve_comparisons"][0]["paired_days"] > 0
    assert Path(report["equity_curve_bootstrap_csv_path"]).exists()
    assert Path(report["paper_tables_markdown_path"]).exists()


def _write_preflight_artifacts(root: Path) -> None:
    records = []
    for idx in range(10):
        records.append({"ticker": f"M{idx}", "year": 2025, "download_status": "not_published_yet", "local_path": None})
    for year in (2022, 2023, 2024):
        records.append({"ticker": "AAPL", "year": year, "download_status": "exists", "local_path": f"esg_reports/AAPL/AAPL_ESG_{year}.pdf"})

    esg_root = root / "storage" / "esg_corpus"
    rag_root = root / "storage" / "rag" / "esg_reports_openai_3072"
    esg_root.mkdir(parents=True, exist_ok=True)
    rag_root.mkdir(parents=True, exist_ok=True)
    for name in ("coverage_report.json", "evidence_chain_report.json"):
        (esg_root / name).write_text("{}", encoding="utf-8")
    (esg_root / "house_scores_v2.json").write_text("[]", encoding="utf-8")
    (esg_root / "manifest.json").write_text(json.dumps({"records": records}), encoding="utf-8")
    (rag_root / "embedding_manifest.json").write_text(
        json.dumps(
            {
                "model": "text-embedding-3-large",
                "dimension": 3072,
                "chunks": 12,
                "current_corpus_chunks": 12,
                "records": records,
            }
        ),
        encoding="utf-8",
    )


def test_paper_preflight_requires_cuda_unless_cpu_smoke_allowed(tmp_path: Path, monkeypatch):
    import scripts.quant_rl_paper_preflight as preflight

    _write_preflight_artifacts(tmp_path)
    monkeypatch.setattr(preflight, "ROOT", tmp_path)
    monkeypatch.setenv("QUANT_RL_PREFLIGHT_ASSUME_CUDA", "0")

    blocked = preflight.run_preflight(namespace="paper-run", sample="full_2022_2025", require_cuda=True, allow_cpu_smoke=False)
    allowed = run_preflight(namespace="paper-run", sample="full_2022_2025", require_cuda=True, allow_cpu_smoke=True)

    assert blocked["status"] == "fail"
    assert any(check["name"] == "cuda_required" and check["status"] == "fail" for check in blocked["checks"])
    assert allowed["status"] == "pass"
