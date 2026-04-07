from gateway.scheduler.data_sources import DataSourceManager, CompanyData
import gateway.db.supabase_client as supabase_module


class _FakeResult:
    def __init__(self, data):
        self.data = data


class _FakeTable:
    def __init__(self):
        self.insert_payload = None
        self.update_payload = None
        self.filters = []

    def insert(self, payload):
        self.insert_payload = payload
        return self

    def update(self, payload):
        self.update_payload = payload
        return self

    def eq(self, key, value):
        self.filters.append((key, value))
        return self

    def execute(self):
        return _FakeResult([{"id": "snapshot-1"}])


class _FakeSupabaseClient:
    def __init__(self):
        self.snapshot_table = _FakeTable()

    def table(self, name):
        assert name == "company_data_snapshot"
        return self.snapshot_table


def test_sync_company_snapshot_uses_runtime_schema(monkeypatch):
    fake_client = _FakeSupabaseClient()
    monkeypatch.setattr(supabase_module, "supabase_client", fake_client, raising=False)

    manager = DataSourceManager()
    monkeypatch.setattr(
        manager,
        "fetch_company_data",
        lambda *args, **kwargs: CompanyData(
            company_name="Tesla",
            ticker="TSLA",
            industry="Automotive",
            environmental={"carbon_emissions": 12},
            social={"employee_satisfaction_score": 80},
            governance={"board_size": 9},
            financial={"market_cap": 1000},
            external_ratings={"msci_rating": "AA"},
            data_sources=["alpha_vantage"],
        ),
    )

    assert manager.sync_company_snapshot("Tesla", ticker="TSLA", force_refresh=True) is True

    payload = fake_client.snapshot_table.insert_payload
    assert payload["company_name"] == "Tesla"
    assert payload["industry"] == "Automotive"
    assert "esg_score_report" in payload
    assert "financial_metrics" in payload
    assert "external_ratings" in payload
    assert "esg_data" not in payload
