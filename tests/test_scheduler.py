from gateway.scheduler import scanner as scanner_module


class _FakeResult:
    def __init__(self, data):
        self.data = data


class _FakeTable:
    def __init__(self, store):
        self._store = store
        self._payload = None

    def insert(self, payload):
        self._payload = payload
        return self

    def execute(self):
        row = dict(self._payload)
        row["id"] = f"event-{len(self._store) + 1}"
        self._store.append(row)
        return _FakeResult([row])


class _FakeDB:
    def __init__(self):
        self.saved_rows = []

    def table(self, name):
        assert name == "esg_events"
        return _FakeTable(self.saved_rows)


def test_scanner_run_scan_saves_all_events(monkeypatch):
    fake_db = _FakeDB()
    monkeypatch.setattr(scanner_module, "get_client", lambda: fake_db)

    scanner = scanner_module.Scanner()
    result = scanner.run_scan()

    assert result["total_events"] == 3
    assert result["saved_events"] == 3
    assert result["event_ids"] == ["event-1", "event-2", "event-3"]
    assert len(fake_db.saved_rows) == 3
    assert {row["company"] for row in fake_db.saved_rows} == {"Tesla", "Microsoft", "SEC"}


def test_scanner_returns_sample_events_without_cursor(monkeypatch):
    fake_db = _FakeDB()
    monkeypatch.setattr(scanner_module, "get_client", lambda: fake_db)

    scanner = scanner_module.Scanner()
    events, next_cursor = scanner.scan_news_feeds()

    assert len(events) == 1
    assert next_cursor is None
    assert events[0].company == "Tesla"
    assert events[0].source == "news_api"


def test_save_events_handles_empty_batch(monkeypatch):
    fake_db = _FakeDB()
    monkeypatch.setattr(scanner_module, "get_client", lambda: fake_db)

    scanner = scanner_module.Scanner()

    assert scanner.save_events([]) == []
    assert fake_db.saved_rows == []
