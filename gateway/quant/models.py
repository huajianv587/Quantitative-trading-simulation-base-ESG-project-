from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ArchitectureLayerStatus(BaseModel):
    key: str
    label: str
    priority: str
    ready: bool
    detail: str


class UniverseMember(BaseModel):
    symbol: str
    company_name: str
    sector: str
    industry: str
    region: str = "US"
    benchmark_weight: float = 0.0


class FactorScore(BaseModel):
    name: str
    value: float
    contribution: float
    description: str


class ProjectionScenario(BaseModel):
    label: str
    expected_return: float
    confidence: float | None = None
    band_source: str | None = None


class ResearchSignal(BaseModel):
    symbol: str
    company_name: str
    sector: str
    thesis: str
    action: Literal["long", "neutral", "short"]
    confidence: float
    expected_return: float
    risk_score: float
    overall_score: float
    e_score: float
    s_score: float
    g_score: float
    alpha_model_score: float | None = None
    alpha_model_name: str | None = None
    alpha_rank: int | None = None
    predicted_return_1d: float | None = None
    predicted_return_5d: float | None = None
    sequence_return_1d: float | None = None
    sequence_return_5d: float | None = None
    sequence_volatility_10d: float | None = None
    sequence_drawdown_20d: float | None = None
    predicted_volatility_10d: float | None = None
    predicted_drawdown_20d: float | None = None
    sequence_model_version: str | None = None
    regime_label: str | None = None
    regime_probability: float | None = None
    p1_calibrated_probability: float | None = None
    p1_confidence_calibrated: float | None = None
    fundamental_score: float | None = None
    news_sentiment_score: float | None = None
    p1_stack_score: float | None = None
    p1_model_version: str | None = None
    graph_cluster: str | None = None
    graph_neighbors: list[str] = Field(default_factory=list)
    graph_centrality: float | None = None
    graph_contagion_risk: float | None = None
    graph_diversification_score: float | None = None
    graph_engine: str | None = None
    graph_model_version: str | None = None
    selector_strategy: str | None = None
    selector_priority_score: float | None = None
    bandit_strategy: str | None = None
    bandit_confidence: float | None = None
    bandit_size_multiplier: float | None = None
    bandit_execution_style: str | None = None
    bandit_execution_delay_seconds: int | None = None
    alpha_engine: str | None = None
    decision_score: float | None = None
    decision_confidence: float | None = None
    signal_source: str = "heuristic"
    factor_scores: list[FactorScore] = Field(default_factory=list)
    catalysts: list[str] = Field(default_factory=list)
    data_lineage: list[str] = Field(default_factory=list)
    market_data_source: str | None = None
    prediction_mode: Literal["model", "unavailable"] | None = None
    projection_basis_return: float | None = None
    projection_scenarios: dict[str, ProjectionScenario] = Field(default_factory=dict)
    house_score: float | None = None
    house_grade: str | None = None
    formula_version: str | None = None
    pillar_breakdown: dict[str, float] = Field(default_factory=dict)
    disclosure_confidence: float | None = None
    controversy_penalty: float | None = None
    data_gap_penalty: float | None = None
    materiality_adjustment: float | None = None
    trend_bonus: float | None = None
    house_explanation: str | None = None
    house_score_v2: float | None = None
    materiality_weights: dict[str, float] = Field(default_factory=dict)
    evidence_count: int | None = None
    effective_date: str | None = None
    staleness_days: int | None = None
    score_delta: float | None = None


class PortfolioPosition(BaseModel):
    symbol: str
    company_name: str
    weight: float
    expected_return: float
    risk_budget: float
    score: float
    side: Literal["long", "short"]
    thesis: str
    strategy_bucket: str | None = None
    decision_score: float | None = None
    regime_posture: str | None = None
    size_multiplier: float | None = None
    execution_tactic: str | None = None
    execution_delay_seconds: int | None = None
    expected_fill_probability: float | None = None
    estimated_slippage_bps: float | None = None
    estimated_impact_bps: float | None = None
    alpha_engine: str | None = None


class PortfolioSummary(BaseModel):
    strategy_name: str
    benchmark: str
    capital_base: float
    gross_exposure: float
    net_exposure: float
    turnover_estimate: float
    expected_alpha: float
    positions: list[PortfolioPosition] = Field(default_factory=list)
    constraints: dict[str, float | str] = Field(default_factory=dict)


class BacktestPoint(BaseModel):
    date: str
    portfolio_nav: float
    benchmark_nav: float
    drawdown: float
    gross_exposure: float


class RiskAlert(BaseModel):
    level: Literal["low", "medium", "high"]
    title: str
    description: str
    recommendation: str


class BacktestMetrics(BaseModel):
    cumulative_return: float
    annualized_return: float
    annualized_volatility: float
    sharpe: float
    sortino: float
    max_drawdown: float
    hit_rate: float
    cvar_95: float
    beta: float
    information_ratio: float


class BacktestResult(BaseModel):
    backtest_id: str
    strategy_name: str
    benchmark: str
    period_start: str
    period_end: str
    metrics: BacktestMetrics
    positions: list[PortfolioPosition] = Field(default_factory=list)
    timeline: list[BacktestPoint] = Field(default_factory=list)
    risk_alerts: list[RiskAlert] = Field(default_factory=list)
    experiment_tags: list[str] = Field(default_factory=list)
    data_source: str = "synthetic fallback"
    data_source_chain: list[str] = Field(default_factory=list)
    used_synthetic_fallback: bool = True
    market_data_warnings: list[str] = Field(default_factory=list)


class ExecutionOrder(BaseModel):
    symbol: str
    side: Literal["buy", "sell"]
    quantity: int
    target_weight: float
    limit_price: float
    venue: str
    rationale: str
    order_type: str = "market"
    time_in_force: str = "day"
    notional: float | None = None
    status: str = "planned"
    broker_order_id: str | None = None
    client_order_id: str | None = None
    submitted_at: str | None = None
    filled_qty: str | None = None
    filled_avg_price: str | None = None
    expected_fill_probability: float | None = None
    estimated_slippage_bps: float | None = None
    estimated_impact_bps: float | None = None
    execution_tactic: str | None = None
    execution_delay_seconds: int | None = None
    canary_bucket: str | None = None


class ExecutionPlan(BaseModel):
    execution_id: str
    broker: str
    mode: Literal["paper", "live"]
    ready: bool
    estimated_slippage_bps: float
    compliance_checks: list[str] = Field(default_factory=list)
    orders: list[ExecutionOrder] = Field(default_factory=list)
    submitted: bool = False
    broker_status: str = "planned"
    warnings: list[str] = Field(default_factory=list)
    account_snapshot: dict[str, str | bool | None] = Field(default_factory=dict)
    broker_connection: dict[str, str | bool | None] = Field(default_factory=dict)


class BrokerDescriptor(BaseModel):
    broker_id: str
    label: str
    channel: str
    configured: bool
    live_supported: bool
    paper_supported: bool
    capabilities: list[str] = Field(default_factory=list)
    auth_hints: list[str] = Field(default_factory=list)
    metadata: dict[str, str | bool | None] = Field(default_factory=dict)


class OrderLifecycleEvent(BaseModel):
    event_id: str
    order_id: str
    execution_id: str
    broker_id: str
    state: str
    message: str
    created_at: str
    payload: dict[str, Any] = Field(default_factory=dict)


class OrderLifecycleRecord(BaseModel):
    order_id: str
    execution_id: str
    broker_id: str
    symbol: str
    current_state: str
    retry_count: int = 0
    cancel_requested: bool = False
    submitted_payload: dict[str, Any] = Field(default_factory=dict)
    last_broker_snapshot: dict[str, Any] = Field(default_factory=dict)
    events: list[OrderLifecycleEvent] = Field(default_factory=list)


class ExecutionJournal(BaseModel):
    execution_id: str
    broker_id: str
    mode: str
    current_state: str
    created_at: str
    updated_at: str
    allowed_actions: list[str] = Field(default_factory=list)
    risk_summary: list[str] = Field(default_factory=list)
    records: list[OrderLifecycleRecord] = Field(default_factory=list)
    metrics: dict[str, str | float | bool | None] = Field(default_factory=dict)


class ValidationWindow(BaseModel):
    label: str
    start: str
    end: str
    sharpe: float
    cumulative_return: float
    turnover_cost_drag: float
    max_drawdown: float
    bucket: str | None = None
    fill_probability: float | None = None
    expected_slippage_bps: float | None = None
    calibrated_confidence: float | None = None


class AlphaValidationReport(BaseModel):
    validation_id: str
    strategy_name: str
    benchmark: str
    generated_at: str
    universe: list[str] = Field(default_factory=list)
    in_sample_sharpe: float
    out_of_sample_sharpe: float
    out_of_sample_cumulative_return: float
    overfit_score: float
    robustness_score: float
    turnover_cost_drag_bps: float
    slippage_bps: float
    impact_cost_bps: float
    fill_probability: float = 0.0
    walk_forward_windows: list[ValidationWindow] = Field(default_factory=list)
    stratified_walk_forward: list[dict[str, Any]] = Field(default_factory=list)
    calibration: dict[str, Any] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class ExperimentRun(BaseModel):
    experiment_id: str
    name: str
    created_at: str
    objective: str
    benchmark: str
    metrics: dict[str, float | str]
    tags: list[str] = Field(default_factory=list)
    artifact_uri: str | None = None


class TrainingPlan(BaseModel):
    target_environment: str
    adapter_strategy: str
    dataset_sources: list[str]
    artifact_store: str
    remote_ready: bool
    notes: list[str]
