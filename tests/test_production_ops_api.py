from pathlib import Path

from fastapi.testclient import TestClient

import gateway.main as main_module


def _client() -> TestClient:
    return TestClient(main_module.app)


def test_schema_health_reports_required_production_tables():
    response = _client().get("/api/v1/platform/schema-health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in {"ready", "degraded", "blocked"}
    tables = {row["table"]: row for row in payload["tables"]}
    for table in [
        "strategy_registry",
        "autopilot_policies",
        "daily_reviews",
        "paper_performance_snapshots",
        "paper_outcomes",
        "session_evidence",
        "scheduler_events",
        "submit_locks",
        "quant_jobs",
        "quant_job_events",
        "data_source_configs",
        "provider_health_checks",
        "data_quality_runs",
    ]:
        assert table in tables
        assert tables[table]["status"] in {"ready", "degraded", "blocked"}
        assert tables[table]["migration_file"].endswith("006_create_production_ops.sql")


def test_release_health_includes_schema_jobs_data_and_safety():
    response = _client().get("/api/v1/platform/release-health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in {"ready", "degraded", "blocked"}
    checks = payload["checks"]
    for key in ["api", "frontend", "schema", "job_queue", "data_config", "trading_safety", "e2e_acceptance"]:
        assert key in checks


def test_job_queue_create_status_cancel_retry_and_logs():
    client = _client()
    created = client.post(
        "/api/v1/jobs",
        json={"job_type": "release_health_smoke", "run_immediately": False, "payload": {"acceptance_namespace": "pytest"}},
    )
    assert created.status_code == 200
    job = created.json()
    assert job["status"] == "queued"
    job_id = job["job_id"]

    loaded = client.get(f"/api/v1/jobs/{job_id}")
    assert loaded.status_code == 200
    assert loaded.json()["job_id"] == job_id

    listed = client.get("/api/v1/jobs?limit=10")
    assert listed.status_code == 200
    listed_payload = listed.json()
    assert listed_payload["status"] in {"ready", "degraded", "blocked"}
    assert any(item["job_id"] == job_id for item in listed_payload["jobs"])

    cancelled = client.post(f"/api/v1/jobs/{job_id}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"

    retried = client.post(f"/api/v1/jobs/{job_id}/retry")
    assert retried.status_code == 200
    assert retried.json()["status"] in {"succeeded", "queued", "running"}

    logs = client.get(f"/api/v1/jobs/{job_id}/logs")
    assert logs.status_code == 200
    assert logs.json()["events"]


def test_job_queue_unsupported_job_degrades_with_next_actions():
    response = _client().post("/api/v1/jobs", json={"job_type": "unknown_long_task"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "degraded"
    assert payload["reason"]
    assert payload["next_actions"]


def test_data_config_center_and_provider_save_contract():
    client = _client()
    center = client.get("/api/v1/data/config-center")
    assert center.status_code == 200
    payload = center.json()
    assert payload["status"] in {"ready", "degraded", "blocked"}
    assert payload["providers"]
    assert any(item["provider_id"] == "alpaca_paper" for item in payload["providers"])

    saved = client.post(
        "/api/v1/data/config-center/providers",
        json={"provider_id": "pytest_provider", "priority": 5, "api_key": "secret-value", "acceptance_namespace": "pytest"},
    )
    assert saved.status_code == 200
    saved_payload = saved.json()
    assert saved_payload["provider_id"] == "pytest_provider"
    assert "api_key" not in saved_payload["payload"]
    assert saved_payload["payload"]["api_key_masked"]


def test_trading_safety_center_hard_disables_live_auto_submit():
    response = _client().get("/api/v1/trading/safety-center")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in {"ready", "degraded", "blocked"}
    assert payload["live_auto_submit"]["allowed"] is False
    assert "hard rule" in payload["live_auto_submit"]["reason"]
    assert payload["paper_auto_submit"]["allowed"] in {True, False}


def test_automation_timeline_declares_all_required_stages():
    response = _client().get("/api/v1/trading/automation/timeline")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in {"ready", "degraded", "blocked"}
    assert [stage["stage"] for stage in payload["stages"]] == [
        "preopen",
        "workflow",
        "risk_gate",
        "paper_plan",
        "paper_submit",
        "broker_sync",
        "outcomes",
        "report",
    ]


def test_production_ops_migration_contains_required_tables_and_indexes():
    migration = Path("database/migrations/006_create_production_ops.sql").read_text(encoding="utf-8")
    for table in [
        "strategy_registry",
        "strategy_allocations",
        "autopilot_policies",
        "debate_runs",
        "daily_reviews",
        "paper_performance_snapshots",
        "paper_outcomes",
        "session_evidence",
        "scheduler_events",
        "submit_locks",
        "quant_jobs",
        "quant_job_events",
        "data_source_configs",
        "provider_health_checks",
        "data_quality_runs",
    ]:
        assert f"create table if not exists {table}" in migration
    assert "payload jsonb" in migration
    assert "create unique index if not exists quant_jobs_job_id_uidx" in migration
