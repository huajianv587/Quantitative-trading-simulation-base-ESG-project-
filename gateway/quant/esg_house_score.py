from __future__ import annotations

from dataclasses import dataclass
from typing import Any


FORMULA_VERSION = "JHJ_HOUSE_SCORE_V1"


@dataclass(slots=True)
class HouseScoreBreakdown:
    house_score: float
    house_grade: str
    formula_version: str
    pillar_breakdown: dict[str, float]
    disclosure_confidence: float
    controversy_penalty: float
    data_gap_penalty: float
    materiality_adjustment: float
    trend_bonus: float
    house_explanation: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "house_score": round(self.house_score, 2),
            "house_grade": self.house_grade,
            "formula_version": self.formula_version,
            "pillar_breakdown": {key: round(value, 2) for key, value in self.pillar_breakdown.items()},
            "disclosure_confidence": round(self.disclosure_confidence, 4),
            "controversy_penalty": round(self.controversy_penalty, 2),
            "data_gap_penalty": round(self.data_gap_penalty, 2),
            "materiality_adjustment": round(self.materiality_adjustment, 2),
            "trend_bonus": round(self.trend_bonus, 2),
            "house_explanation": self.house_explanation,
        }


SECTOR_MATERIALITY_WEIGHTS: dict[str, dict[str, float]] = {
    "technology": {"E": -0.5, "S": 0.7, "G": 1.1},
    "semiconductors": {"E": 0.9, "S": 0.4, "G": 0.9},
    "utilities": {"E": 1.3, "S": 0.3, "G": 0.7},
    "energy": {"E": 1.5, "S": 0.2, "G": 0.6},
    "financials": {"E": -0.4, "S": 0.8, "G": 1.2},
    "banks": {"E": -0.4, "S": 0.8, "G": 1.2},
    "health care": {"E": 0.2, "S": 1.1, "G": 0.8},
    "consumer staples": {"E": 0.6, "S": 0.8, "G": 0.6},
    "consumer discretionary": {"E": 0.7, "S": 0.9, "G": 0.7},
    "industrials": {"E": 1.1, "S": 0.5, "G": 0.7},
    "default": {"E": 0.7, "S": 0.6, "G": 0.8},
}


def _bounded(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, float(value)))


def _normalize_text(*parts: str | None) -> str:
    return " ".join(str(part or "").strip().lower() for part in parts if str(part or "").strip())


def _materiality_adjustment(sector: str | None, industry: str | None, e_score: float, s_score: float, g_score: float) -> float:
    label = _normalize_text(industry, sector)
    matched = next((weights for key, weights in SECTOR_MATERIALITY_WEIGHTS.items() if key != "default" and key in label), None)
    weights = matched or SECTOR_MATERIALITY_WEIGHTS["default"]
    weighted_center = (
        weights["E"] * (float(e_score) - 50.0)
        + weights["S"] * (float(s_score) - 50.0)
        + weights["G"] * (float(g_score) - 50.0)
    ) / 75.0
    return _bounded(weighted_center, -8.0, 8.0)


def _disclosure_confidence(data_sources: list[str] | None, data_lineage: list[str] | None, metric_coverage_ratio: float) -> float:
    source_count = len(list(data_sources or []))
    lineage_count = len(list(data_lineage or []))
    confidence = 0.42 + min(source_count * 0.08, 0.24) + min(lineage_count * 0.03, 0.15) + metric_coverage_ratio * 0.19
    return _bounded(confidence, 0.18, 0.98)


def _trend_bonus(overall_score: float, esg_delta: float | None = None, historical_data: dict[str, Any] | None = None) -> float:
    delta = float(esg_delta or 0.0)
    if historical_data and isinstance(historical_data, dict):
        prior = historical_data.get("prior_overall_score")
        if isinstance(prior, (int, float)):
            delta = max(delta, (float(overall_score) - float(prior)) / 100.0)
    scaled = delta * 140.0
    if overall_score >= 75:
        scaled += 0.8
    return _bounded(scaled, 0.0, 6.0)


def _controversy_penalty(recent_news: list[dict[str, Any]] | None, controversy_hints: list[str] | None) -> float:
    texts: list[str] = []
    for item in recent_news or []:
        texts.append(_normalize_text(item.get("title"), item.get("description"), item.get("event_type")))
    texts.extend(_normalize_text(item) for item in controversy_hints or [])
    joined = " ".join(texts)
    if not joined:
        return 0.0
    weight = 0.0
    negative_markers = {
        "fraud": 6.0,
        "brib": 5.5,
        "probe": 4.5,
        "lawsuit": 4.0,
        "fine": 3.5,
        "spill": 5.0,
        "breach": 4.0,
        "whistle": 4.5,
        "violation": 3.5,
        "controvers": 3.0,
    }
    for marker, penalty in negative_markers.items():
        if marker in joined:
            weight += penalty
    return -_bounded(weight, 0.0, 15.0)


def _data_gap_penalty(metric_coverage_ratio: float, disclosure_confidence: float) -> float:
    missing_ratio = 1.0 - _bounded(metric_coverage_ratio, 0.0, 1.0)
    penalty = missing_ratio * 7.5 + (1.0 - disclosure_confidence) * 4.5
    return -_bounded(penalty, 0.0, 10.0)


def _grade(score: float) -> str:
    if score >= 85:
        return "AAA"
    if score >= 78:
        return "AA"
    if score >= 70:
        return "A"
    if score >= 60:
        return "BBB"
    if score >= 50:
        return "BB"
    if score >= 40:
        return "B"
    return "CCC"


def compute_house_score(
    *,
    company_name: str,
    sector: str | None,
    industry: str | None,
    e_score: float,
    s_score: float,
    g_score: float,
    disclosure_quality: float | None = None,
    data_sources: list[str] | None = None,
    data_lineage: list[str] | None = None,
    recent_news: list[dict[str, Any]] | None = None,
    controversy_hints: list[str] | None = None,
    esg_delta: float | None = None,
    historical_data: dict[str, Any] | None = None,
    metric_coverage_ratio: float = 1.0,
) -> HouseScoreBreakdown:
    disclosure_quality_score = float(disclosure_quality) if disclosure_quality is not None else (
        58.0 + min(len(list(data_sources or [])) * 6.0, 22.0) + min(len(list(data_lineage or [])) * 2.5, 10.0)
    )
    disclosure_quality_score = _bounded(disclosure_quality_score, 35.0, 96.0)

    base_score = (
        0.34 * float(e_score)
        + 0.28 * float(s_score)
        + 0.28 * float(g_score)
        + 0.10 * disclosure_quality_score
    )
    materiality_adjustment = _materiality_adjustment(sector, industry, e_score, s_score, g_score)
    disclosure_conf = _disclosure_confidence(data_sources, data_lineage, metric_coverage_ratio)
    trend_bonus = _trend_bonus(base_score, esg_delta=esg_delta, historical_data=historical_data)
    controversy_penalty = _controversy_penalty(recent_news, controversy_hints)
    data_gap_penalty = _data_gap_penalty(metric_coverage_ratio, disclosure_conf)
    final_score = _bounded(base_score + materiality_adjustment + trend_bonus + controversy_penalty + data_gap_penalty, 0.0, 100.0)
    grade = _grade(final_score)
    explanation = (
        f"{company_name} {FORMULA_VERSION} = base {base_score:.1f}"
        f" + materiality {materiality_adjustment:+.1f}"
        f" + trend {trend_bonus:+.1f}"
        f" {controversy_penalty:+.1f}"
        f" {data_gap_penalty:+.1f}"
        f" => {final_score:.1f} ({grade})."
    )

    return HouseScoreBreakdown(
        house_score=final_score,
        house_grade=grade,
        formula_version=FORMULA_VERSION,
        pillar_breakdown={
            "E": float(e_score),
            "S": float(s_score),
            "G": float(g_score),
            "DisclosureQuality": disclosure_quality_score,
        },
        disclosure_confidence=disclosure_conf,
        controversy_penalty=controversy_penalty,
        data_gap_penalty=data_gap_penalty,
        materiality_adjustment=materiality_adjustment,
        trend_bonus=trend_bonus,
        house_explanation=explanation,
    )
