from fastapi.testclient import TestClient

import gateway.main as main_module
from gateway.config import settings


ADMIN_HEADERS = {"x-api-key": settings.ADMIN_API_KEY}


class _FakeResult:
    def __init__(self, data):
        self.data = data


class _FakeTableQuery:
    def __init__(self, rows):
        self._rows = rows
        self._filters = []
        self._limit = None
        self._order = None

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, key, value):
        self._filters.append((key, value))
        return self

    def gte(self, *_args, **_kwargs):
        return self

    def lte(self, *_args, **_kwargs):
        return self

    def order(self, key, desc=False):
        self._order = (key, desc)
        return self

    def limit(self, value):
        self._limit = value
        return self

    def execute(self):
        rows = [dict(row) for row in self._rows]
        for key, value in self._filters:
            rows = [row for row in rows if row.get(key) == value]
        if self._order is not None:
            key, desc = self._order
            rows.sort(key=lambda row: row.get(key) or "", reverse=desc)
        if self._limit is not None:
            rows = rows[:self._limit]
        return _FakeResult(rows)


class _FakeSupabaseClient:
    def __init__(self, tables):
        self._tables = tables

    def table(self, name):
        return _FakeTableQuery(self._tables.get(name, []))


class _FakeReport:
    def __init__(self, report_type: str):
        self.report_type = report_type

    def dict(self):
        return {"report_type": self.report_type, "title": "mock-report"}


class _FakeReportGenerator:
    def generate_daily_report(self, companies):
        assert companies
        return _FakeReport("daily")

    def generate_weekly_report(self, companies):
        assert companies
        return _FakeReport("weekly")

    def generate_monthly_report(self, companies):
        assert companies
        return _FakeReport("monthly")


class _FakeReportScheduler:
    def __init__(self):
        self.saved_reports = []

    def _save_report(self, report):
        self.saved_reports.append(report)
        return f"{report.report_type}-report-id"


class _FakeDataSourceManager:
    def __init__(self):
        self.calls = []

    def sync_company_snapshot(self, company, ticker=None, industry=None, force_refresh=False):
        self.calls.append((company, force_refresh))
        return company != "BadCo"


def test_health_endpoint_returns_basic_status():
    client = TestClient(main_module.app)

    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["app_mode"] in {"local", "hybrid", "prod"}
    assert "runtime" in data
    assert "modules" in data
    assert "ready" in data
    assert "operational_readiness" in data
    assert data["app_id"] == "quant-terminal"
    assert data["service_name"] == "Quant Terminal"
    assert data["landing_entry"].endswith("/")
    assert data["ui_entry"].endswith("/app/")
    assert data["api_base_url"].startswith("http://testserver")


def test_livez_is_lightweight_process_probe():
    client = TestClient(main_module.app)

    response = client.get("/livez")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["app_id"] == "quant-terminal"


def test_ready_endpoint_tracks_rag_initialization(monkeypatch):
    client = TestClient(main_module.app)
    previous = getattr(main_module.app.state, "query_engine", None)
    previous_scorer = main_module.runtime.esg_scorer
    previous_scheduler = main_module.runtime.report_scheduler
    try:
        main_module.runtime.esg_scorer = object()
        main_module.runtime.report_scheduler = object()
        monkeypatch.setattr(
            main_module.runtime.quant_system,
            "build_cached_readiness",
            lambda: {
                "ready": main_module.app.state.query_engine is not None,
                "cached": True,
                "blockers": [] if main_module.app.state.query_engine is not None else ["rag"],
                "components": {},
            },
        )
        main_module.app.state.query_engine = None
        not_ready = client.get("/health/ready")
        assert not_ready.status_code == 503
        assert not_ready.json()["ready"] is False

        main_module.app.state.query_engine = object()
        ready = client.get("/health/ready")
        assert ready.status_code == 200
        assert ready.json()["ready"] is True
    finally:
        main_module.app.state.query_engine = previous
        main_module.runtime.esg_scorer = previous_scorer
        main_module.runtime.report_scheduler = previous_scheduler


def test_analyze_endpoint_accepts_query_params(monkeypatch):
    monkeypatch.setattr(
        main_module.runtime,
        "run_agent",
        lambda question, session_id="": {
            "final_answer": f"answer:{question}:{session_id}",
            "esg_scores": {"overall": 88},
            "confidence": 0.91,
            "analysis_summary": "ok",
        },
    )
    monkeypatch.setattr(main_module.runtime, "save_message", lambda *args, **kwargs: None)
    client = TestClient(main_module.app)

    response = client.post("/agent/analyze", params={"question": "Tesla", "session_id": "s1"})

    assert response.status_code == 200
    data = response.json()
    assert data["question"] == "Tesla"
    assert data["answer"] == "answer:Tesla:s1"
    assert data["esg_scores"]["overall"] == 88


def test_analyze_endpoint_accepts_json_body(monkeypatch):
    monkeypatch.setattr(
        main_module.runtime,
        "run_agent",
        lambda question, session_id="": {
            "final_answer": "json-body-ok",
            "esg_scores": {},
            "confidence": 0.75,
            "analysis_summary": "body",
        },
    )
    monkeypatch.setattr(main_module.runtime, "save_message", lambda *args, **kwargs: None)
    client = TestClient(main_module.app)

    response = client.post("/agent/analyze", json={"question": "Apple", "session_id": "json-session"})

    assert response.status_code == 200
    assert response.json()["answer"] == "json-body-ok"


def test_report_generation_accepts_async_alias(monkeypatch):
    fake_scheduler = _FakeReportScheduler()
    monkeypatch.setattr(main_module.runtime, "report_generator", _FakeReportGenerator())
    monkeypatch.setattr(main_module.runtime, "report_scheduler", fake_scheduler)
    client = TestClient(main_module.app)

    response = client.post(
        "/admin/reports/generate",
        headers=ADMIN_HEADERS,
        json={"report_type": "daily", "companies": ["Tesla"], "async": False},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["report_id"] == "daily-report-id"
    assert fake_scheduler.saved_reports


def test_report_generation_rejects_invalid_async_type(monkeypatch):
    monkeypatch.setattr(main_module.runtime, "report_generator", _FakeReportGenerator())
    client = TestClient(main_module.app)

    response = client.post(
        "/admin/reports/generate",
        headers=ADMIN_HEADERS,
        json={"report_type": "yearly", "companies": ["Tesla"], "async": True},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid report type"


def test_latest_report_route_returns_flattened_payload(monkeypatch):
    fake_db = _FakeSupabaseClient(
        {
            "esg_reports": [
                {
                    "id": "report-1",
                    "report_type": "daily",
                    "title": "Daily ESG Report",
                    "period_start": "2026-04-01T00:00:00",
                    "period_end": "2026-04-01T12:00:00",
                    "generated_at": "2026-04-01T12:00:00",
                    "data": {
                        "title": "Daily ESG Report",
                        "generated_at": "2026-04-01T12:00:00",
                        "company_analyses": [{"company_name": "Tesla", "esg_score": 75}],
                    },
                }
            ]
        }
    )
    monkeypatch.setattr(main_module.runtime, "get_client", lambda: fake_db)
    client = TestClient(main_module.app)

    response = client.get("/admin/reports/latest", params={"report_type": "daily"}, headers=ADMIN_HEADERS)

    assert response.status_code == 200
    data = response.json()
    assert data["report_id"] == "report-1"
    assert data["title"] == "Daily ESG Report"
    assert data["company_analyses"][0]["company_name"] == "Tesla"


def test_esg_score_endpoint_preserves_service_unavailable(monkeypatch):
    monkeypatch.setattr(main_module.runtime, "esg_scorer", object())
    monkeypatch.setattr(main_module.runtime, "data_source_manager", None)
    client = TestClient(main_module.app)

    response = client.post("/agent/esg-score", json={"company": "Tesla"})

    assert response.status_code == 503
    assert response.json()["detail"] == "Data Source Manager not ready"


def test_sync_status_tracks_background_result(monkeypatch):
    fake_manager = _FakeDataSourceManager()
    monkeypatch.setattr(main_module.runtime, "data_source_manager", fake_manager)
    client = TestClient(main_module.app)

    response = client.post(
        "/admin/data-sources/sync",
        headers=ADMIN_HEADERS,
        json={"companies": ["Tesla", "BadCo"], "force_refresh": True},
    )

    assert response.status_code == 200
    job_id = response.json()["job_id"]

    status_response = client.get(f"/admin/data-sources/sync/{job_id}", headers=ADMIN_HEADERS)
    assert status_response.status_code == 200
    payload = status_response.json()
    assert payload["status"] == "completed_with_errors"
    assert payload["companies_synced"] == 1
    assert payload["companies_failed"] == 1
    assert fake_manager.calls == [("Tesla", True), ("BadCo", True)]


def test_push_rule_test_endpoint_uses_latest_real_report(monkeypatch):
    fake_rule = type(
        "FakeRule",
        (),
        {"condition": "overall_score < 40", "push_channels": ["email", "webhook"]},
    )()
    fake_scheduler = type("FakeScheduler", (), {"push_rules_cache": {"rule-1": fake_rule}})()
    fake_db = _FakeSupabaseClient(
        {
            "esg_reports": [
                {
                    "id": "report-old",
                    "report_type": "weekly",
                    "generated_at": "2026-04-01T10:00:00",
                    "data": {"overall_score": 72},
                },
                {
                    "id": "report-new",
                    "report_type": "daily",
                    "generated_at": "2026-04-02T10:00:00",
                    "data": {"overall_score": 35},
                },
            ]
        }
    )
    monkeypatch.setattr(main_module.runtime, "ensure_optional_services", lambda **_kwargs: None)
    monkeypatch.setattr(main_module.runtime, "report_scheduler", fake_scheduler)
    monkeypatch.setattr(main_module.runtime, "get_client", lambda: fake_db)
    monkeypatch.setattr(main_module.runtime, "report_jobs", {})
    client = TestClient(main_module.app)

    response = client.post(
        "/admin/push-rules/rule-1/test",
        headers=ADMIN_HEADERS,
        json={"test_user_id": "u-1"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["report_id"] == "report-new"
    assert data["report_type"] == "daily"
    assert data["results"]["matched"] is True
    assert data["results"]["channels_tested"] == ["email", "webhook"]


def test_push_rule_test_endpoint_accepts_explicit_report_id(monkeypatch):
    fake_rule = type(
        "FakeRule",
        (),
        {"condition": "overall_score >= 80", "push_channels": ["in_app"]},
    )()
    fake_scheduler = type("FakeScheduler", (), {"push_rules_cache": {"rule-1": fake_rule}})()
    fake_db = _FakeSupabaseClient(
        {
            "esg_reports": [
                {
                    "id": "report-a",
                    "report_type": "daily",
                    "generated_at": "2026-04-01T10:00:00",
                    "data": {"overall_score": 25},
                },
                {
                    "id": "report-b",
                    "report_type": "daily",
                    "generated_at": "2026-04-03T10:00:00",
                    "data": {"overall_score": 91},
                },
            ]
        }
    )
    monkeypatch.setattr(main_module.runtime, "ensure_optional_services", lambda **_kwargs: None)
    monkeypatch.setattr(main_module.runtime, "report_scheduler", fake_scheduler)
    monkeypatch.setattr(main_module.runtime, "get_client", lambda: fake_db)
    monkeypatch.setattr(main_module.runtime, "report_jobs", {})
    client = TestClient(main_module.app)

    response = client.post(
        "/admin/push-rules/rule-1/test",
        headers=ADMIN_HEADERS,
        json={"test_user_id": "u-1", "report_id": "report-a"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["report_id"] == "report-a"
    assert data["results"]["matched"] is False
    assert data["results"]["channels_tested"] == ["in_app"]


def test_push_rule_test_endpoint_blocks_without_real_report(monkeypatch):
    fake_rule = type(
        "FakeRule",
        (),
        {"condition": "overall_score < 40", "push_channels": ["email"]},
    )()
    fake_scheduler = type("FakeScheduler", (), {"push_rules_cache": {"rule-1": fake_rule}})()
    fake_db = _FakeSupabaseClient({"esg_reports": []})
    monkeypatch.setattr(main_module.runtime, "ensure_optional_services", lambda **_kwargs: None)
    monkeypatch.setattr(main_module.runtime, "report_scheduler", fake_scheduler)
    monkeypatch.setattr(main_module.runtime, "get_client", lambda: fake_db)
    monkeypatch.setattr(main_module.runtime, "report_jobs", {})
    client = TestClient(main_module.app)

    response = client.post(
        "/admin/push-rules/rule-1/test",
        headers=ADMIN_HEADERS,
        json={"test_user_id": "u-1"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "blocked"
    assert data["block_reason"] == "real_report_required"
    assert data["report_id"] is None
    assert data["results"]["matched"] is False


def test_user_subscriptions_endpoint_reads_database(monkeypatch):
    fake_db = _FakeSupabaseClient(
        {
            "user_report_subscriptions": [
                {
                    "id": "sub-1",
                    "user_id": "user_123",
                    "report_types": ["daily"],
                    "companies": ["Tesla"],
                    "alert_threshold": {"esg_score": 40},
                    "push_channels": ["email"],
                    "frequency": "daily",
                    "subscribed_at": "2026-04-01T12:00:00",
                    "updated_at": "2026-04-01T12:30:00",
                }
            ]
        }
    )
    monkeypatch.setattr(main_module.runtime, "get_client", lambda: fake_db)
    client = TestClient(main_module.app)

    response = client.get("/user/reports/subscriptions", params={"user_id": "user_123"})

    assert response.status_code == 200
    data = response.json()
    assert data["subscriptions"][0]["subscription_id"] == "sub-1"
    assert data["subscriptions"][0]["companies"] == ["Tesla"]


def test_scheduler_scan_status_exposes_lane_summary(monkeypatch):
    fake_status = {
        "status": "completed",
        "source_summary": {
            "news": {"status": "completed", "events_found": 2, "events_saved": 2},
            "reports": {"status": "blocked", "events_found": 0, "events_saved": 0},
            "compliance": {"status": "degraded", "events_found": 0, "events_saved": 0},
        },
        "blocked_reason": None,
        "next_actions": ["refresh sources"],
        "checkpoint_state": {"newsapi": {"latest_checkpoint": {"apple": {}}}},
    }
    fake_orchestrator = type("FakeOrchestrator", (), {"get_scan_status": lambda self: fake_status})()
    monkeypatch.setattr(main_module.runtime, "get_orchestrator", lambda: fake_orchestrator)
    client = TestClient(main_module.app)

    response = client.get("/scheduler/scan/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["data"]["source_summary"]["news"]["events_found"] == 2
    assert payload["data"]["source_summary"]["reports"]["status"] == "blocked"


def test_scheduler_statistics_exposes_lane_statistics(monkeypatch):
    monkeypatch.setattr(
        main_module.runtime,
        "get_scheduler_statistics",
        lambda days=7: {
            "period_days": days,
            "total_scans": 3,
            "lane_statistics": {
                "news": {"runs": 3, "events_found": 4, "events_saved": 4, "blocked_runs": 0},
                "reports": {"runs": 3, "events_found": 1, "events_saved": 1, "blocked_runs": 1},
                "compliance": {"runs": 3, "events_found": 0, "events_saved": 0, "blocked_runs": 2},
            },
        },
    )
    client = TestClient(main_module.app)

    response = client.get("/scheduler/statistics", params={"days": 14})

    assert response.status_code == 200
    payload = response.json()
    assert payload["period_days"] == 14
    assert payload["lane_statistics"]["news"]["events_found"] == 4
    assert payload["lane_statistics"]["reports"]["blocked_runs"] == 1
