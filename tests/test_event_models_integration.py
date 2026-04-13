from __future__ import annotations

from gateway.scheduler import event_extractor as event_extractor_module
from gateway.scheduler import risk_scorer as risk_scorer_module


class _StubClassifier:
    def classify(self, text: str):
        return {
            "label": "critical",
            "probability": 0.92,
            "model_name": "stub-controversy",
            "scores": {"critical": 0.92, "high": 0.05, "medium": 0.02, "low": 0.01},
        }


def test_event_extractor_merges_controversy_classifier_signal(monkeypatch):
    monkeypatch.setattr(event_extractor_module, "get_client", lambda: None)
    monkeypatch.setattr(event_extractor_module, "get_event_classifier_runtime", lambda: _StubClassifier())
    monkeypatch.setattr(
        event_extractor_module,
        "chat",
        lambda *args, **kwargs: """
        {
          "title": "Factory spill escalates governance scrutiny",
          "description": "The company disclosed a spill and regulator review.",
          "company": "TestCo",
          "event_type": "compliance_violation",
          "key_metrics": {"fine_exposure": "unknown"},
          "impact_area": "G",
          "severity": "medium",
          "evidence": "Regulators opened a review."
        }
        """,
    )

    extractor = event_extractor_module.EventExtractor()
    payload = extractor.extract_event(
        event_id="evt-1",
        raw_content="Regulators opened a review after a spill.",
        source="newsapi",
        company="TestCo",
    )

    assert payload is not None
    assert payload.severity == "critical"
    assert payload.key_metrics["controversy_label"] == "critical"
    assert payload.key_metrics["controversy_probability"] == 0.92
    assert payload.key_metrics["controversy_model_name"] == "stub-controversy"


def test_risk_scorer_calibrates_score_with_controversy_signal(monkeypatch):
    monkeypatch.setattr(risk_scorer_module, "get_client", lambda: None)
    monkeypatch.setattr(
        risk_scorer_module,
        "chat",
        lambda *args, **kwargs: """
        {
          "risk_level": "medium",
          "score": 48,
          "reasoning": "Baseline operational incident with contained direct impact.",
          "affected_dimensions": {"environmental": 30, "social": 25, "governance": 40},
          "recommendation": "Monitor filings and management response."
        }
        """,
    )

    scorer = risk_scorer_module.RiskScorer()
    payload = scorer.score_event(
        "evt-2",
        {
            "title": "Probe widens after incident",
            "description": "Stakeholders expect a tougher regulatory response.",
            "event_type": "compliance_violation",
            "impact_area": "G",
            "severity": "medium",
            "key_metrics": {
                "controversy_label": "critical",
                "controversy_probability": 0.9,
            },
        },
    )

    assert payload is not None
    assert payload["risk_level"] == "critical"
    assert payload["score"] > 48
    assert "controversy classifier" in payload["reasoning"].lower()
