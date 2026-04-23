from __future__ import annotations

from types import SimpleNamespace

from gateway.scheduler import scanner as scanner_module


class _FakeResult:
    def __init__(self, data):
        self.data = data


class _FakeTable:
    def __init__(self, rows):
        self._rows = rows
        self._filters = []
        self._order = None
        self._limit = None
        self._insert_payload = None
        self._update_payload = None

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, key, value):
        self._filters.append((key, value))
        return self

    def order(self, key, desc=False):
        self._order = (key, desc)
        return self

    def limit(self, value):
        self._limit = value
        return self

    def insert(self, payload):
        self._insert_payload = payload
        return self

    def update(self, payload):
        self._update_payload = payload
        return self

    def _filtered_rows(self):
        rows = [dict(row) for row in self._rows]
        for key, value in self._filters:
            rows = [row for row in rows if row.get(key) == value]
        if self._order is not None:
            key, desc = self._order
            rows.sort(key=lambda row: str(row.get(key) or ""), reverse=desc)
        if self._limit is not None:
            rows = rows[: self._limit]
        return rows

    def execute(self):
        if self._insert_payload is not None:
            payload = dict(self._insert_payload)
            payload.setdefault("id", f"row-{len(self._rows) + 1}")
            self._rows.append(payload)
            return _FakeResult([payload])
        if self._update_payload is not None:
            updated = []
            for row in self._rows:
                if all(row.get(key) == value for key, value in self._filters):
                    row.update(self._update_payload)
                    updated.append(dict(row))
            return _FakeResult(updated)
        return _FakeResult(self._filtered_rows())


class _FakeDB:
    def __init__(self):
        self.tables = {
            "esg_events": [],
            "scan_jobs": [],
            "scan_source_state": [],
            "user_preferences": [],
            "user_holdings": [],
        }

    def table(self, name):
        self.tables.setdefault(name, [])
        return _FakeTable(self.tables[name])


class _FakeDataSourceManager:
    def __init__(self, *, newsapi_key="", finnhub_api_key="", sec_edgar_email=""):
        self.newsapi_key = newsapi_key
        self.finnhub_api_key = finnhub_api_key
        self.sec_edgar_email = sec_edgar_email

    def _resolve_symbol(self, company_name):
        return {"Apple": "AAPL", "Microsoft": "MSFT"}.get(company_name)

    def _fetch_sec_filing_text(self, *_args, **_kwargs):
        return ""

    def _excerpt_around(self, *_args, **_kwargs):
        return None


def _build_scanner(monkeypatch, fake_db=None, fake_manager=None):
    db = fake_db or _FakeDB()
    manager = fake_manager or _FakeDataSourceManager()
    monkeypatch.setattr(scanner_module, "get_client", lambda: db)
    monkeypatch.setattr(scanner_module, "DataSourceManager", lambda: manager)
    scanner = scanner_module.Scanner()
    scanner.db = db
    scanner.data_source_manager = manager
    return scanner, db, manager


def test_scanner_run_scan_saves_real_news_events(monkeypatch):
    scanner, fake_db, _manager = _build_scanner(
        monkeypatch,
        fake_manager=_FakeDataSourceManager(newsapi_key="news-key"),
    )
    monkeypatch.setattr(scanner, "_get_tracked_companies", lambda: ["Apple"])
    monkeypatch.setattr(
        scanner,
        "_fetch_newsapi_articles",
        lambda company_name: [
            {
                "title": "Apple raises renewable energy target",
                "description": "New climate roadmap filed by Apple.",
                "url": "https://news.example/apple-renewable",
                "source": "NewsAPI",
                "published_at": "2026-04-20T10:00:00+00:00",
                "company": company_name,
            }
        ],
    )

    result = scanner.run_scan()

    assert result["total_events"] == 1
    assert result["saved_events"] == 1
    assert len(fake_db.tables["esg_events"]) == 1
    assert fake_db.tables["esg_events"][0]["company"] == "Apple"
    assert result["lanes"]["news"]["events_found"] == 1
    assert result["lanes"]["reports"]["status"] == "blocked"
    assert result["lanes"]["compliance"]["status"] == "blocked"


def test_scanner_news_lane_blocks_without_real_sources(monkeypatch):
    scanner, _fake_db, _manager = _build_scanner(monkeypatch)
    monkeypatch.setattr(scanner, "_get_tracked_companies", lambda: ["Apple"])

    lane = scanner._scan_news_lane()

    assert lane["status"] == "blocked"
    assert lane["blocked_reason"] == "news_sources_unavailable"
    assert lane["events_found"] == 0
    assert lane["source_status"]["newsapi"]["blocked_reason"] == "source_not_configured"
    assert lane["source_status"]["finnhub"]["blocked_reason"] == "source_not_configured"


def test_scanner_reports_lane_uses_real_sec_filings(monkeypatch):
    scanner, _fake_db, _manager = _build_scanner(
        monkeypatch,
        fake_manager=_FakeDataSourceManager(sec_edgar_email="sec@example.com"),
    )
    monkeypatch.setattr(scanner, "_get_tracked_companies", lambda: ["Apple"])
    monkeypatch.setattr(
        scanner,
        "_collect_sec_filings",
        lambda company_name, forms: (
            {"cik": "0000320193", "ticker": "AAPL", "title": "Apple Inc."},
            [
                {
                    "company": "Apple Inc.",
                    "ticker": "AAPL",
                    "cik": "0000320193",
                    "form": "10-K",
                    "accession_number": "0000320193-26-000001",
                    "primary_document": "a10k.htm",
                    "filed_at": "2026-04-20T00:00:00+00:00",
                    "url": "https://www.sec.gov/Archives/apple-10k",
                    "source": "SEC 10-K",
                }
            ],
        ),
    )

    lane = scanner._scan_reports_lane()

    assert lane["status"] == "completed"
    assert lane["events_found"] == 1
    assert lane["events"][0].source == "sec_edgar"
    assert lane["events"][0].source_url == "https://www.sec.gov/Archives/apple-10k"
    assert lane["events"][0].company == "Apple Inc."


def test_scanner_compliance_lane_uses_sec_only_snippets(monkeypatch):
    manager = _FakeDataSourceManager(sec_edgar_email="sec@example.com")
    manager._fetch_sec_filing_text = lambda *_args, **_kwargs: "The audit committee disclosed a material weakness in controls."
    manager._excerpt_around = lambda *_args, **_kwargs: "material weakness in controls"
    scanner, _fake_db, _ = _build_scanner(monkeypatch, fake_manager=manager)
    monkeypatch.setattr(scanner, "_get_tracked_companies", lambda: ["Apple"])
    monkeypatch.setattr(
        scanner,
        "_collect_sec_filings",
        lambda company_name, forms: (
            {"cik": "0000320193", "ticker": "AAPL", "title": "Apple Inc."},
            [
                {
                    "company": "Apple Inc.",
                    "ticker": "AAPL",
                    "cik": "0000320193",
                    "form": "8-K",
                    "accession_number": "0000320193-26-000002",
                    "primary_document": "a8k.htm",
                    "filed_at": "2026-04-21T00:00:00+00:00",
                    "url": "https://www.sec.gov/Archives/apple-8k",
                    "source": "SEC 8-K",
                }
            ],
        ),
    )

    lane = scanner._scan_compliance_lane()

    assert lane["status"] == "completed"
    assert lane["events_found"] == 1
    assert lane["events"][0].source == "sec_edgar"
    assert "governance/compliance update" in lane["events"][0].title
    assert "material weakness" in lane["events"][0].description


def test_scanner_news_checkpoint_prevents_duplicate_rescan(monkeypatch):
    scanner, fake_db, _manager = _build_scanner(
        monkeypatch,
        fake_manager=_FakeDataSourceManager(newsapi_key="news-key"),
    )
    monkeypatch.setattr(scanner, "_get_tracked_companies", lambda: ["Apple"])
    monkeypatch.setattr(
        scanner,
        "_fetch_newsapi_articles",
        lambda company_name: [
            {
                "title": "Apple raises renewable energy target",
                "description": "New climate roadmap filed by Apple.",
                "url": "https://news.example/apple-renewable",
                "source": "NewsAPI",
                "published_at": "2026-04-20T10:00:00+00:00",
                "company": company_name,
            }
        ],
    )

    first = scanner.run_scan()
    second = scanner.run_scan()

    assert first["saved_events"] == 1
    assert second["saved_events"] == 0
    assert second["total_events"] == 0
    assert len(fake_db.tables["esg_events"]) == 1
    assert len(fake_db.tables["scan_source_state"]) >= 1


def test_save_events_handles_empty_batch(monkeypatch):
    scanner, fake_db, _manager = _build_scanner(monkeypatch)

    assert scanner.save_events([]) == []
    assert fake_db.tables["esg_events"] == []
