from __future__ import annotations

from typing import Literal

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
    factor_scores: list[FactorScore] = Field(default_factory=list)
    catalysts: list[str] = Field(default_factory=list)
    data_lineage: list[str] = Field(default_factory=list)


class PortfolioPosition(BaseModel):
    symbol: str
    company_name: str
    weight: float
    expected_return: float
    risk_budget: float
    score: float
    side: Literal["long", "short"]
    thesis: str


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
