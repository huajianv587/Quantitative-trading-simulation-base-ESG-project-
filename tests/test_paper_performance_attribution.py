from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from gateway.quant.service import QuantSystemService


def test_paper_performance_returns_curves_and_attribution(tmp_path: Path, monkeypatch):
    service = QuantSystemService()
    service.storage.base_dir = tmp_path
    monkeypatch.setattr(service, "get_execution_account", lambda **_kwargs: {"connected": True, "paper_ready": True, "account": {"equity": 110.0}})
    monkeypatch.setattr(service, "get_execution_controls", lambda: {"kill_switch_enabled": False})
    monkeypatch.setattr(service, "_paper_gate_sync_status", lambda: {"ok": True, "checked_executions": 1, "error_count": 0})

    start = datetime(2026, 1, 2, tzinfo=timezone.utc)
    for index in range(10):
        day = (start + timedelta(days=index)).date().isoformat()
        service.storage.persist_record(
            "paper_performance",
            day,
            {"snapshot_id": day, "date": day, "portfolio_nav": 100 + index, "benchmark_nav": 100 + index * 0.5, "evidence_eligible": True},
        )
    service.storage.persist_record(
        "executions",
        "execution-1",
        {
            "execution_id": "execution-1",
            "mode": "paper",
            "generated_at": start.isoformat(),
            "submitted": True,
            "orders": [
                {"symbol": "AAPL", "status": "filled", "notional": 10.0, "estimated_slippage_bps": 2.0},
                {"symbol": "MSFT", "status": "rejected", "notional": 10.0, "estimated_slippage_bps": 6.0},
            ],
        },
    )
    outcome = service._build_paper_outcome_record(
        record_kind="order",
        source_id="cid",
        index=0,
        workflow_id="workflow-1",
        execution_id="execution-1",
        symbol="AAPL",
        action="long",
        entry_at=start.isoformat(),
        entry_price=100.0,
        notional=10.0,
        features={"momentum": 70, "overall_score": 80},
        model_refs={},
        market_data_source="alpaca",
        synthetic_used=False,
    )
    outcome["status"] = "settled"
    outcome["score"] = 0.01
    service._save_paper_outcome(outcome)

    report = service.build_paper_performance_report(window_days=90)

    assert report["equity_curve"]
    assert report["drawdown_curve"]
    assert report["fill_rate"] == 0.5
    assert report["reject_rate"] == 0.5
    assert report["avg_slippage_bps"] == 4.0
    assert report["symbol_contributions"][0]["symbol"] == "AAPL"
    assert report["factor_exposures"]["momentum"] == 70
    assert "excess_return" in report["benchmark_attribution"]

