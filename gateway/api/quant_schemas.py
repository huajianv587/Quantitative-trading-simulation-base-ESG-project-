from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class QuantResearchRequest(BaseModel):
    universe: list[str] = Field(default_factory=list)
    benchmark: str = "SPY"
    research_question: str = "Run the default ESG quant research pipeline"
    capital_base: float = 1_000_000
    horizon_days: int = 20


class QuantPortfolioRequest(BaseModel):
    universe: list[str] = Field(default_factory=list)
    benchmark: str = "SPY"
    capital_base: float = 1_000_000
    research_question: str = ""
    preset_name: str | None = None
    objective: str | None = None
    max_position_weight: float | None = None
    max_sector_concentration: float | None = None
    esg_floor: float | None = None


class QuantP1StackRequest(BaseModel):
    universe: list[str] = Field(default_factory=list)
    benchmark: str = "SPY"
    capital_base: float = 1_000_000
    research_question: str = "Run the P1 alpha + risk stack"


class QuantP2DecisionRequest(BaseModel):
    universe: list[str] = Field(default_factory=list)
    benchmark: str = "SPY"
    capital_base: float = 1_000_000
    research_question: str = "Run the P2 graph + strategy selector stack"


class QuantBacktestRequest(BaseModel):
    strategy_name: str = "ESG Multi-Factor Long-Only"
    universe: list[str] = Field(default_factory=list)
    benchmark: str = "SPY"
    capital_base: float = 1_000_000
    lookback_days: int = 126
    market_data_provider: str | None = None
    force_refresh: bool = False


class QuantBacktestSweepRequest(BaseModel):
    strategy_name: str = "ESG Multi-Factor Long-Only"
    universe: list[str] = Field(default_factory=list)
    benchmark: str = "SPY"
    capital_base: float = 1_000_000
    lookback_days: int = 126
    market_data_provider: str | None = None
    force_refresh: bool = False
    parameter_grid: dict[str, list[Any]] = Field(default_factory=dict)
    top_k: int = 5


class QuantExecutionRequest(BaseModel):
    universe: list[str] = Field(default_factory=list)
    benchmark: str = "SPY"
    capital_base: float = 1_000_000
    broker: str = "alpaca"
    mode: str = "paper"
    submit_orders: bool = False
    max_orders: int = 2
    per_order_notional: float | None = None
    order_type: str = "market"
    time_in_force: str = "day"
    extended_hours: bool = False
    allow_duplicates: bool = False
    live_confirmed: bool = False
    operator_confirmation: str | None = None
    strategy_id: str | None = None


class QuantWorkflowRunRequest(BaseModel):
    universe: list[str] = Field(default_factory=list)
    benchmark: str = "SPY"
    capital_base: float = 1_000_000
    strategy_mode: str = "hybrid_p1_p2_rl"
    rl_algorithm: str = "sac"
    rl_action_type: str = "continuous"
    rl_dataset_path: str | None = None
    rl_checkpoint_path: str | None = None
    submit_orders: bool = True
    mode: str = "paper"
    broker: str = "alpaca"
    max_orders: int = 2
    per_order_notional: float | None = 1.0
    allow_synthetic_execution: bool = False
    force_refresh: bool = False


class QuantPaperPerformanceSnapshotRequest(BaseModel):
    workflow_id: str | None = None
    execution_id: str | None = None
    benchmark: str = "SPY"
    broker: str = "alpaca"
    mode: str = "paper"
    force_refresh: bool = False


class QuantPaperPerformanceBackfillRequest(BaseModel):
    days: int = 120
    benchmark: str = "SPY"
    broker: str = "alpaca"
    mode: str = "paper"
    force_refresh: bool = False


class QuantDailyDigestSendRequest(BaseModel):
    phase: str = "postclose"
    session_date: str | None = None
    recipients: list[str] = Field(default_factory=list)
    channels: list[str] = Field(default_factory=list)


class QuantWeeklyDigestSendRequest(BaseModel):
    session_date: str | None = None
    window_days: int = 7
    recipients: list[str] = Field(default_factory=list)
    channels: list[str] = Field(default_factory=list)


class QuantAlpacaPaperReconcileRequest(BaseModel):
    session_date: str | None = None


class QuantStorageBackupRequest(BaseModel):
    session_date: str | None = None


class QuantPaperOutcomesSettleRequest(BaseModel):
    outcome_id: str | None = None
    force_refresh: bool = False
    limit: int = 200


class QuantPromotionEvaluateRequest(BaseModel):
    window_days: int = 90
    persist: bool = True


class QuantShadowRetrainRequest(BaseModel):
    model_key: str = "rl_checkpoint"
    force: bool = False


class QuantOrderActionRequest(BaseModel):
    broker: str = "alpaca"
    execution_id: str
    per_order_notional: float | None = None
    order_type: str = "market"
    time_in_force: str = "day"
    extended_hours: bool = False


class QuantKillSwitchRequest(BaseModel):
    enabled: bool
    reason: str = ""


class QuantValidationRequest(BaseModel):
    strategy_name: str = "ESG Multi-Factor Long-Only"
    universe: list[str] = Field(default_factory=list)
    benchmark: str = "SPY"
    capital_base: float = 1_000_000
    in_sample_days: int = 252
    out_of_sample_days: int = 63
    walk_forward_windows: int = 3
    slippage_bps: float | None = None
    impact_cost_bps: float | None = None


class QuantIntelligenceScanRequest(BaseModel):
    universe: list[str] = Field(default_factory=list)
    query: str = "Build an as-of evidence bundle for the quant intelligence cockpit"
    decision_time: str | None = None
    live_connectors: bool = False
    limit: int = 20
    mode: str = "local"
    providers: list[str] = Field(default_factory=list)
    quota_guard: bool = True
    persist: bool = True


class QuantFactorDiscoveryRequest(BaseModel):
    universe: list[str] = Field(default_factory=list)
    query: str = "Discover evidence-linked quant factors"
    horizon_days: int = 20
    decision_time: str | None = None
    evidence_run_id: str | None = None
    as_of_time: str | None = None
    mode: str = "local"
    providers: list[str] = Field(default_factory=list)
    quota_guard: bool = True
    required_data_tier: str = "l1"


class QuantDatasetBuildRequest(BaseModel):
    universe: list[str] = Field(default_factory=list)
    query: str = "Build a reusable as-of dataset manifest for US equities research"
    as_of_time: str | None = None
    decision_time: str | None = None
    mode: str = "local"
    providers: list[str] = Field(default_factory=list)
    quota_guard: bool = True
    frequency: str = "daily"
    include_intraday: bool = True
    required_data_tier: str = "l1"
    persist: bool = True


class QuantResearchQualityRequest(BaseModel):
    universe: list[str] = Field(default_factory=list)
    query: str = "Run research protection checks"
    decision_time: str | None = None
    as_of_time: str | None = None
    evidence_run_id: str | None = None
    mode: str = "local"
    providers: list[str] = Field(default_factory=list)
    quota_guard: bool = True
    frequency: str = "daily"
    formulas: list[str] = Field(default_factory=list)
    labels: list[dict[str, Any]] = Field(default_factory=list)
    timestamps: list[str] = Field(default_factory=list)
    current_constituents_only: bool = False
    required_data_tier: str = "l1"
    persist: bool = True


class QuantDecisionExplainRequest(BaseModel):
    symbol: str = "AAPL"
    universe: list[str] = Field(default_factory=list)
    query: str = "Explain the current multi-expert quant decision"
    horizon_days: int = 20
    include_simulation: bool = True
    evidence_run_id: str | None = None
    mode: str = "local"
    providers: list[str] = Field(default_factory=list)
    quota_guard: bool = True


class QuantSimulationScenarioRequest(BaseModel):
    symbol: str = "AAPL"
    universe: list[str] = Field(default_factory=list)
    horizon_days: int = 20
    shock_bps: float = 0.0
    transaction_cost_bps: float = 8.0
    slippage_bps: float = 5.0
    paths: int = 256
    seed: int = 42
    scenario_name: str = "base_case"
    event_assumption: str = ""
    regime: str = "neutral"
    event_id: str | None = None
    evidence_run_id: str | None = None
    required_data_tier: str = "l1"


class QuantMarketDepthReplayRequest(BaseModel):
    symbol: str = "AAPL"
    limit: int = 20
    timestamps: list[str] = Field(default_factory=list)
    required_data_tier: str = "l1"
    persist: bool = True


class QuantOutcomeEvaluateRequest(BaseModel):
    symbol: str = "AAPL"
    decision_id: str | None = None
    horizon_days: int = 20
    realized_return: float | None = None
    benchmark_return: float = 0.0
    drawdown: float | None = None
    notes: str = ""


class ModelReleaseRequest(BaseModel):
    actor: str = "operator"
    model_key: str
    version: str
    action: str = "promote"
    notes: str = ""
    canary_percent: float | None = None


class ProviderStatus(BaseModel):
    available: bool = False
    provider: str = "unavailable"
    selected_provider: str = "auto"
    cache_hit: bool | None = None
    lookback_limit: int | None = None
    error: str | None = None


class FallbackPreview(BaseModel):
    symbol: str = ""
    source: str = "unavailable"
    source_chain: list[str] = Field(default_factory=list)
    last_snapshot: dict[str, Any] | None = None
    reason: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)


class ActionableWarning(BaseModel):
    code: str
    message: str
    severity: str = "warning"
    next_actions: list[str] = Field(default_factory=list)


class ResearchContextQuote(BaseModel):
    symbol: str
    company_name: str = ""
    price: float | None = None
    change_pct: float | None = None
    source: str = "unavailable"
    provider_status: ProviderStatus = Field(default_factory=ProviderStatus)
    warning: str | None = None


class ResearchContextFeedItem(BaseModel):
    item_id: str
    item_type: str
    symbol: str = ""
    title: str
    summary: str = ""
    source: str = ""
    provider: str = ""
    published_at: str | None = None
    freshness_score: float | None = None
    confidence: float | None = None
    quality_score: float | None = None
    sentiment: str = "neutral"
    url: str | None = None


class ResearchContextResponse(BaseModel):
    generated_at: str
    symbol: str
    provider: str = "auto"
    quote_strip: list[ResearchContextQuote] = Field(default_factory=list)
    momentum_leaders: list[dict[str, Any]] = Field(default_factory=list)
    feed: list[ResearchContextFeedItem] = Field(default_factory=list)
    provider_status: ProviderStatus = Field(default_factory=ProviderStatus)
    source_chain: list[str] = Field(default_factory=list)
    freshness: dict[str, Any] = Field(default_factory=dict)
    degraded: bool = False
    fallback_preview: FallbackPreview = Field(default_factory=FallbackPreview)
    warning: ActionableWarning | None = None
    next_actions: list[str] = Field(default_factory=list)
