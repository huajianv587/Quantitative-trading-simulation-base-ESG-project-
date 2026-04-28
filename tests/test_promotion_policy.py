from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from gateway.quant.promotion_policy import load_promotion_policy
from gateway.quant.service import QuantSystemService


def test_custom_promotion_policy_blocks_low_filled_orders(tmp_path: Path, monkeypatch):
    policy_path = tmp_path / "promotion_policy.json"
    policy_path.write_text(
        json.dumps({"live_canary": {"min_filled_orders": 2}, "paper_promoted": {"min_valid_days": 2}}),
        encoding="utf-8",
    )
    monkeypatch.setattr("gateway.quant.promotion_policy.settings.PROMOTION_POLICY_PATH", str(policy_path))
    policy = load_promotion_policy()

    assert policy["live_canary"]["min_filled_orders"] == 2

    service = QuantSystemService()
    service.storage.base_dir = tmp_path / "storage"
    monkeypatch.setattr(service, "get_execution_account", lambda **_kwargs: {"connected": True, "paper_ready": True})
    monkeypatch.setattr(service, "get_execution_controls", lambda: {"kill_switch_enabled": False})
    monkeypatch.setattr(service, "_paper_gate_sync_status", lambda: {"ok": True, "checked_executions": 1, "error_count": 0})

    start = datetime(2026, 1, 2, tzinfo=timezone.utc)
    for index in range(65):
        day = (start + timedelta(days=index)).date().isoformat()
        service.storage.persist_record(
            "paper_performance",
            f"{index:03d}-{day}",
            {"snapshot_id": f"{index:03d}-{day}", "date": day, "portfolio_nav": 100 + index, "benchmark_nav": 100, "evidence_eligible": True},
        )

    report = service.evaluate_promotion(window_days=90, persist=True)

    assert "filled_orders" in report["recommendation"]["blockers"]
    assert report["evidence_storage"]["record_type"] == "promotion_evidence"
