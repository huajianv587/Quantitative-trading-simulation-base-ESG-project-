from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

import gateway.scheduler.report_scheduler as scheduler_module


class _FakeResult:
    def __init__(self, data):
        self.data = data


class _FakeTableQuery:
    def __init__(self, rows):
        self._rows = rows
        self._filters = []
        self.payload = None

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, key, value):
        self._filters.append((key, value))
        return self

    def insert(self, payload):
        self.payload = payload
        return self

    def execute(self):
        if self.payload is not None:
            self._rows.append(dict(self.payload))
            return _FakeResult([{"id": self.payload.get("id", "report-1")}])
        rows = [dict(row) for row in self._rows]
        for key, value in self._filters:
            rows = [row for row in rows if row.get(key) == value]
        return _FakeResult(rows)


class _FakeSupabaseClient:
    def __init__(self, tables=None):
        self._tables = tables or {}

    def table(self, name):
        self._tables.setdefault(name, [])
        return _FakeTableQuery(self._tables[name])


class _DummyReport(BaseModel):
    report_type: str
    title: str
    period_start: datetime
    period_end: datetime
    generated_at: datetime
    company_analyses: list = []
    risk_alerts: list = []
    report_statistics: dict = {}


class _FakeGenerator:
    def __init__(self):
        self.calls = []

    def generate_monthly_report(self, companies):
        self.calls.append(("monthly", list(companies)))
        return _DummyReport(
            report_type="monthly",
            title="Monthly",
            period_start=datetime(2026, 4, 1, 0, 0, 0),
            period_end=datetime(2026, 4, 30, 23, 59, 59),
            generated_at=datetime(2026, 4, 30, 23, 59, 59),
            report_statistics={"portfolio_average_score": 80},
        )


def test_save_report_serializes_nested_datetimes(monkeypatch):
    fake_client = _FakeSupabaseClient({"esg_reports": []})
    monkeypatch.setattr(scheduler_module, "supabase_client", fake_client)

    scheduler = scheduler_module.ReportScheduler.__new__(scheduler_module.ReportScheduler)
    report = _DummyReport(
        report_type="daily",
        title="Daily",
        period_start=datetime(2026, 4, 1, 0, 0, 0),
        period_end=datetime(2026, 4, 1, 12, 0, 0),
        generated_at=datetime(2026, 4, 1, 12, 0, 0),
    )

    report_id = scheduler._save_report(report)

    assert report_id
    payload = fake_client._tables["esg_reports"][0]
    assert payload["data"]["generated_at"] == "2026-04-01T12:00:00"


def test_tracked_companies_merge_preferences_and_holdings(monkeypatch):
    fake_client = _FakeSupabaseClient(
        {
            "user_preferences": [
                {"interested_companies": ["Apple", "NVIDIA"]},
                {"interested_companies": ["Apple", "Microsoft"]},
            ],
            "user_holdings": [
                {"company_name": "Tesla"},
                {"company": "Microsoft"},
            ],
        }
    )
    monkeypatch.setattr(scheduler_module, "supabase_client", fake_client)

    scheduler = scheduler_module.ReportScheduler.__new__(scheduler_module.ReportScheduler)

    assert scheduler._get_all_tracked_companies() == ["Apple", "Microsoft", "NVIDIA", "Tesla"]


def test_monthly_report_uses_holdings_only(monkeypatch):
    fake_client = _FakeSupabaseClient(
        {
            "user_preferences": [{"interested_companies": ["Apple", "NVIDIA"]}],
            "user_holdings": [{"company_name": "Tesla"}],
        }
    )
    monkeypatch.setattr(scheduler_module, "supabase_client", fake_client)

    scheduler = scheduler_module.ReportScheduler.__new__(scheduler_module.ReportScheduler)
    scheduler.report_generator = _FakeGenerator()
    scheduler.push_rules_cache = {}
    scheduler.data_source_manager = None
    scheduler.notifier = None
    scheduler._save_report = lambda report: "monthly-report-id"
    scheduler.intelligent_push = lambda *_args, **_kwargs: None

    result = scheduler.generate_monthly_report()

    assert result["status"] == "completed"
    assert result["companies"] == ["Tesla"]
    assert scheduler.report_generator.calls == [("monthly", ["Tesla"])]


def test_daily_report_blocks_without_tracked_companies(monkeypatch):
    fake_client = _FakeSupabaseClient({"user_preferences": [], "user_holdings": []})
    monkeypatch.setattr(scheduler_module, "supabase_client", fake_client)

    scheduler = scheduler_module.ReportScheduler.__new__(scheduler_module.ReportScheduler)
    scheduler.report_generator = _FakeGenerator()
    scheduler.push_rules_cache = {}
    scheduler.data_source_manager = None
    scheduler.notifier = None

    result = scheduler.generate_and_push_daily_report()

    assert result["status"] == "blocked"
    assert result["block_reason"] == "tracked_companies_missing"


def test_monthly_report_blocks_without_holdings(monkeypatch):
    fake_client = _FakeSupabaseClient(
        {
            "user_preferences": [{"interested_companies": ["Apple"]}],
            "user_holdings": [],
        }
    )
    monkeypatch.setattr(scheduler_module, "supabase_client", fake_client)

    scheduler = scheduler_module.ReportScheduler.__new__(scheduler_module.ReportScheduler)
    scheduler.report_generator = _FakeGenerator()
    scheduler.push_rules_cache = {}
    scheduler.data_source_manager = None
    scheduler.notifier = None

    result = scheduler.generate_monthly_report()

    assert result["status"] == "blocked"
    assert result["block_reason"] == "portfolio_holdings_missing"
