from datetime import datetime

from pydantic import BaseModel

import gateway.scheduler.report_scheduler as scheduler_module


class _FakeResult:
    def __init__(self, data):
        self.data = data


class _FakeTable:
    def __init__(self):
        self.payload = None

    def insert(self, payload):
        self.payload = payload
        return self

    def execute(self):
        return _FakeResult([{"id": self.payload["id"]}])


class _FakeSupabaseClient:
    def __init__(self):
        self.table_ref = _FakeTable()

    def table(self, name):
        assert name == "esg_reports"
        return self.table_ref


class _DummyReport(BaseModel):
    report_type: str
    title: str
    period_start: datetime
    period_end: datetime
    generated_at: datetime


def test_save_report_serializes_nested_datetimes(monkeypatch):
    fake_client = _FakeSupabaseClient()
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
    assert fake_client.table_ref.payload["data"]["generated_at"] == "2026-04-01T12:00:00"
