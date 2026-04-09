from fastapi.testclient import TestClient

import gateway.main as main_module
from gateway.scheduler.report_scheduler import PushRule, ReportScheduler


class _FakeResult:
    def __init__(self, data):
        self.data = data


class _FakeQuery:
    def __init__(self, rows):
        self._rows = rows

    def select(self, *_args, **_kwargs):
        return self

    def gte(self, *_args, **_kwargs):
        return self

    def lte(self, *_args, **_kwargs):
        return self

    def execute(self):
        return _FakeResult(list(self._rows))


class _FakeStatsDb:
    def __init__(self):
        self._tables = {
            "esg_reports": [
                {"id": "r-1", "report_type": "weekly", "generated_at": "2026-04-09T12:00:00"},
                {"id": "r-2", "report_type": "daily", "generated_at": "2026-04-10T12:00:00"},
            ],
            "report_push_history": [
                {"push_status": "sent", "read_at": "2026-04-10T12:30:00", "click_through": True},
                {"push_status": "pending", "read_at": None, "click_through": False},
            ],
        }

    def table(self, name):
        return _FakeQuery(self._tables.get(name, []))


class _InsertCaptureQuery:
    def __init__(self, bucket):
        self._bucket = bucket

    def insert(self, payload):
        self._bucket.append(payload)
        return self

    def execute(self):
        return _FakeResult([])


class _InsertCaptureDb:
    def __init__(self, bucket):
        self._bucket = bucket

    def table(self, name):
        assert name == "push_rules"
        return _InsertCaptureQuery(self._bucket)


def test_report_statistics_route_is_not_shadowed(monkeypatch):
    monkeypatch.setattr(main_module.runtime, "get_client", lambda: _FakeStatsDb())
    client = TestClient(main_module.app)

    response = client.get(
        "/admin/reports/statistics",
        params={"period": "2026-04-01:2026-04-10", "group_by": "report_type"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["period"]["start"] == "2026-04-01"
    assert payload["total_reports"] == 2
    assert payload["by_type"]["weekly"] == 1
    assert payload["push_statistics"]["delivered"] == 1


def test_create_push_rule_serializes_datetime_fields(monkeypatch):
    inserted = []
    monkeypatch.setattr("gateway.scheduler.report_scheduler.supabase_client", _InsertCaptureDb(inserted))

    scheduler = ReportScheduler.__new__(ReportScheduler)
    scheduler.push_rules_cache = {}

    rule = PushRule(
        rule_name="serialize-check",
        condition="overall_score < 40",
        target_users="holders",
        push_channels=["in_app"],
        priority=5,
        template_id="template_low_esg_warning",
    )

    rule_id = ReportScheduler.create_push_rule(scheduler, rule)

    assert rule_id
    assert inserted
    assert isinstance(inserted[0]["created_at"], str)
    assert isinstance(inserted[0]["updated_at"], str)
    assert scheduler.push_rules_cache[rule_id].rule_name == "serialize-check"
