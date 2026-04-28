from __future__ import annotations

from pathlib import Path

from gateway.quant.provenance import SyntheticEvidenceGuard
from gateway.quant.service import QuantSystemService


def test_synthetic_guard_ignores_field_names_and_blocks_values():
    guard = SyntheticEvidenceGuard()

    clean = guard.inspect({"synthetic_used": False, "market_data_source": "alpaca"})
    synthetic = guard.inspect({"market_data_source": "synthetic", "note": "demo"})

    assert clean.synthetic_used is False
    assert clean.evidence_eligible is True
    assert synthetic.synthetic_used is True
    assert synthetic.evidence_eligible is False


def test_paper_gate_excludes_synthetic_performance_points(tmp_path: Path, monkeypatch):
    service = QuantSystemService()
    service.storage.base_dir = tmp_path
    monkeypatch.setattr(service, "_paper_gate_sync_status", lambda: {"ok": True, "checked_executions": 0, "error_count": 0})

    clean = {"date": "2026-01-02", "portfolio_nav": 100.0, "benchmark_nav": 100.0, "evidence_eligible": True}
    synthetic = {"date": "2026-01-05", "portfolio_nav": 101.0, "benchmark_nav": 100.1, "synthetic_used": True}

    points = service._normalize_paper_gate_points([clean, synthetic])

    assert points == [{"date": "2026-01-02", "portfolio_nav": 100.0, "benchmark_nav": 100.0}]

