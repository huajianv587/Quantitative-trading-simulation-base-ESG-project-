from __future__ import annotations

from types import SimpleNamespace

from gateway.agents.esg_scorer import ESGScoringFramework
from gateway.scheduler.data_sources import CompanyData, DataSourceManager
from gateway.scheduler.report_generator import ESGReportGenerator


def test_fetch_from_sec_edgar_extracts_governance_signals(monkeypatch):
    manager = DataSourceManager()

    monkeypatch.setattr(
        manager,
        "_resolve_sec_company",
        lambda company_name, ticker=None: {
            "cik": "0000123456",
            "ticker": "AAPL",
            "title": "Apple Inc.",
        },
    )
    monkeypatch.setattr(
        manager,
        "_fetch_sec_submissions",
        lambda cik: {
            "filings": {
                "recent": {
                    "form": ["DEF 14A", "10-K"],
                    "accessionNumber": ["0000123456-26-000001", "0000123456-25-000002"],
                    "primaryDocument": ["proxy.htm", "annual.htm"],
                    "filingDate": ["2026-01-08", "2025-10-31"],
                }
            }
        },
    )

    sample_text = (
        "Our board of directors consists of 10 directors. "
        "9 of our 10 directors are independent. "
        "We separate the roles of chair and chief executive officer and maintain a lead independent director. "
        "Our audit committee includes a financial expert and all members are independent. "
        "The company maintains an anti-corruption code of ethics and whistleblower hotline."
    )
    monkeypatch.setattr(manager, "_fetch_sec_filing_text", lambda *args, **kwargs: sample_text)

    payload = manager._fetch_from_sec_edgar("Apple", ticker="AAPL")
    assert payload is not None
    assert payload["sec_cik"] == "0000123456"
    assert payload["board_size"] == 10
    assert payload["independent_directors_percentage"] == 90.0
    assert payload["ceo_duality"] is False
    assert payload["anti_corruption_policy"] is True
    assert payload["whistleblower_program"] is True
    assert payload["audit_committee_effectiveness"] == "strong"
    assert payload["sec_governance_evidence"]


def test_score_esg_fast_mode_skips_live_llm(monkeypatch):
    scorer = ESGScoringFramework()
    monkeypatch.setattr("gateway.agents.esg_scorer.chat", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("chat should not be called")))

    report = scorer.score_esg(
        "Example Corp",
        {
            "ticker": "EXM",
            "industry": "Software",
            "environmental": {"renewable_energy_percentage": 42},
            "social": {"employee_satisfaction": 78},
            "governance": {"board_size": 9},
            "financial": {},
            "external_ratings": {},
            "data_sources": ["sec_edgar", "newsapi"],
        },
        prefer_fast_mode=True,
    )

    assert report.company_name == "Example Corp"
    assert report.overall_score > 0
    assert report.confidence_score > 0


def test_weekly_report_exposes_grounding_bundle(monkeypatch):
    company_data = CompanyData(
        company_name="TestCo",
        ticker="TST",
        environmental={"carbon_emissions": "down"},
        social={"employee_satisfaction": 80},
        governance={
            "sec_governance_evidence": [
                {
                    "label": "board_composition",
                    "form": "DEF 14A",
                    "filed_at": "2026-01-08",
                    "source": "SEC DEF 14A",
                    "url": "https://example.com/sec",
                    "snippet": "TestCo board oversight expanded and the audit committee remains fully independent.",
                }
            ]
        },
        recent_news=[
            {
                "title": "TestCo expands renewable data center footprint",
                "description": "TestCo disclosed a new renewable energy procurement agreement.",
                "url": "https://example.com/news",
                "source": "NewsAPI",
                "published_at": "2026-04-13T00:00:00Z",
            }
        ],
        data_sources=["sec_edgar", "newsapi"],
    )

    monkeypatch.setattr("gateway.scheduler.data_sources.DataSourceManager.fetch_company_data", lambda self, company_name: company_data)

    fake_dimension = lambda score, summary: SimpleNamespace(overall_score=score, summary=summary)
    fake_report = SimpleNamespace(
        overall_score=78.5,
        overall_trend="up",
        e_scores=fake_dimension(76.0, "Environmental metrics improved."),
        s_scores=fake_dimension(80.0, "Social indicators stable."),
        g_scores=fake_dimension(79.0, "Governance remains resilient."),
        peer_rank="top_quartile",
        confidence_score=0.82,
    )
    monkeypatch.setattr("gateway.scheduler.report_generator.ESGScoringFramework.score_esg", lambda self, *args, **kwargs: fake_report)

    report = ESGReportGenerator().generate_weekly_report(["TestCo"])

    assert report.company_analyses
    analysis = report.company_analyses[0]
    assert analysis.citations
    assert analysis.grounding_status in {"grounded", "partial", "weak"}
    assert report.evidence_summary["citation_count"] >= 1
