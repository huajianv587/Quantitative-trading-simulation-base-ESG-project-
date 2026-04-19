from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


InfoType = Literal[
    "news",
    "filing",
    "esg_report",
    "earnings_call",
    "market_signal",
    "macro",
    "risk_event",
    "rag_evidence",
    "model_signal",
    "connector_status",
]


class InformationItem(BaseModel):
    item_id: str
    item_type: InfoType
    provider: str
    source: str
    title: str
    summary: str
    symbol: str
    company_name: str
    url: str | None = None
    published_at: str | None = None
    observed_at: str
    event_date: str | None = None
    checksum: str
    content_hash: str
    license_note: str = "internal research use"
    freshness_score: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    quality_score: float = Field(ge=0.0, le=1.0)
    dedup_id: str
    leakage_guard: Literal["as_of_safe", "future_dated_warning", "missing_timestamp_warning"]
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvidenceBundle(BaseModel):
    bundle_id: str
    generated_at: str
    decision_time: str
    universe: list[str] = Field(default_factory=list)
    query: str = ""
    items: list[InformationItem] = Field(default_factory=list)
    connector_status: dict[str, Any] = Field(default_factory=dict)
    quality_summary: dict[str, Any] = Field(default_factory=dict)
    lineage: list[str] = Field(default_factory=list)


class StructuredEvent(BaseModel):
    event_id: str
    item_id: str
    symbol: str
    company_name: str
    event_type: str
    esg_axis: Literal["E", "S", "G", "MIXED", "NONE"]
    sentiment: float = Field(ge=-1.0, le=1.0)
    controversy_severity: float = Field(ge=0.0, le=1.0)
    impact_direction: Literal["positive", "neutral", "negative"]
    impact_strength: float = Field(ge=0.0, le=1.0)
    evidence_strength: float = Field(ge=0.0, le=1.0)
    novelty_score: float = Field(ge=0.0, le=1.0)
    decay_half_life_days: int = Field(ge=1)
    observed_at: str
    leakage_guard: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class FactorCandidate(BaseModel):
    factor_id: str
    name: str
    family: str
    description: str
    horizon_days: int
    universe: list[str] = Field(default_factory=list)
    exposures: dict[str, float] = Field(default_factory=dict)
    source_item_ids: list[str] = Field(default_factory=list)
    leakage_audit: dict[str, Any] = Field(default_factory=dict)
    lineage: list[str] = Field(default_factory=list)


class FactorCard(BaseModel):
    factor_id: str
    name: str
    family: str
    definition: str
    status: Literal["promoted", "research_only", "low_confidence", "rejected"]
    universe: list[str] = Field(default_factory=list)
    horizon_days: int
    missing_rate: float = Field(ge=0.0, le=1.0)
    ic: float
    rank_ic: float
    turnover_estimate: float = Field(ge=0.0)
    transaction_cost_sensitivity: str
    stability_score: float = Field(ge=0.0, le=1.0)
    sample_count: int
    gate_results: dict[str, Any] = Field(default_factory=dict)
    failure_modes: list[str] = Field(default_factory=list)
    lineage: list[str] = Field(default_factory=list)


class SimulationScenario(BaseModel):
    symbol: str = "AAPL"
    universe: list[str] = Field(default_factory=list)
    horizon_days: int = Field(default=20, ge=1, le=252)
    shock_bps: float = 0.0
    transaction_cost_bps: float = 8.0
    slippage_bps: float = 5.0
    paths: int = Field(default=256, ge=32, le=5000)
    seed: int = 42
    scenario_name: str = "base_case"
    event_assumption: str = ""
    regime: str = "neutral"
    event_id: str | None = None
    evidence_run_id: str | None = None


class SimulationResult(BaseModel):
    simulation_id: str
    generated_at: str
    scenario: SimulationScenario
    expected_return: float
    median_return: float
    probability_of_loss: float
    max_drawdown_p95: float
    value_at_risk_95: float
    expected_shortfall_95: float
    path_summary: dict[str, float] = Field(default_factory=dict)
    factor_attribution: dict[str, float] = Field(default_factory=dict)
    historical_analogs: list[dict[str, Any]] = Field(default_factory=list)
    lineage: list[str] = Field(default_factory=list)


class DecisionReport(BaseModel):
    decision_id: str
    generated_at: str
    decision_time: str
    symbol: str
    company_name: str
    action: Literal["long", "neutral", "short"]
    position_weight_range: dict[str, float]
    confidence: float = Field(ge=0.0, le=1.0)
    confidence_interval: dict[str, float]
    expected_return: float
    main_evidence: list[InformationItem] = Field(default_factory=list)
    counter_evidence: list[InformationItem] = Field(default_factory=list)
    risk_triggers: list[str] = Field(default_factory=list)
    factor_attribution: dict[str, float] = Field(default_factory=dict)
    factor_cards: list[FactorCard] = Field(default_factory=list)
    simulation: SimulationResult | None = None
    verifier_checks: dict[str, Any] = Field(default_factory=dict)
    data_versions: dict[str, Any] = Field(default_factory=dict)
    model_versions: dict[str, Any] = Field(default_factory=dict)
    audit_trail: list[str] = Field(default_factory=list)


class OutcomeRecord(BaseModel):
    outcome_id: str
    decision_id: str | None = None
    symbol: str
    recorded_at: str
    decision_time: str | None = None
    horizon_days: int
    predicted_return: float | None = None
    realized_return: float
    benchmark_return: float = 0.0
    excess_return: float
    direction_hit: bool | None = None
    brier_component: float | None = None
    regret: float | None = None
    drawdown_breach: bool = False
    notes: str = ""
    lineage: list[str] = Field(default_factory=list)
