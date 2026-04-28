from __future__ import annotations

from pathlib import Path
from time import perf_counter
from types import SimpleNamespace

from quant_rl.service.quant_service import QuantRLService


def test_overview_has_frontier_stack():
    overview = QuantRLService().overview()
    assert 'frontier' in overview['stack']


def test_overview_defaults_to_fast_paginated_run_summary(tmp_path: Path):
    service = QuantRLService.__new__(QuantRLService)
    runs = [
        {
            "run_id": f"run-{index}",
            "created_at": f"2026-01-{(index % 28) + 1:02d}T00:00:00+00:00",
            "algorithm": "sac",
            "phase": "backtest",
            "status": "trained",
            "config": {"dataset_path": str(tmp_path / "missing.csv")},
            "metrics": {},
            "artifacts": {},
        }
        for index in range(212)
    ]
    service.repo = SimpleNamespace(list_runs=lambda: runs)
    service.trading_store = SimpleNamespace(list_strategies=lambda: [])
    service.market_depth = SimpleNamespace(status=lambda **_kwargs: (_ for _ in ()).throw(AssertionError("market depth should be opt-in")))
    service.recorder = SimpleNamespace(protocol=lambda: {}, output_status=lambda: {})
    service.settings = SimpleNamespace(
        storage_dir=tmp_path / "rl",
        experiment_root=tmp_path / "experiments",
        sqlite_db_path=tmp_path / "metadata.sqlite3",
        checkpoints_dir=tmp_path / "checkpoints",
        reports_dir=tmp_path / "reports",
        r2_bucket="",
        r2_endpoint_url="",
        supabase_url="",
        supabase_key="",
    )
    service.market_data = SimpleNamespace(status=lambda: {})
    service.data_sources = None
    service.esg_scorer = None

    started = perf_counter()
    overview = service.overview()
    elapsed = perf_counter() - started

    assert elapsed < 2.0
    assert len(overview["runs"]) == 20
    assert overview["pagination"]["total"] == 212
    assert overview["runs"][0]["eligibility_status"] == "not_requested"
