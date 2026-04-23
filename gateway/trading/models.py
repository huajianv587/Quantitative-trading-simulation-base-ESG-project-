from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


TradingAction = Literal["long", "neutral", "short", "block"]
RiskVerdict = Literal["approve", "reduce", "reject", "halt"]
JobStatus = Literal["queued", "running", "completed", "failed", "skipped"]


class SentimentSymbolScore(BaseModel):
    symbol: str
    polarity: float = Field(ge=-1.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    article_count: int = 0
    freshness_score: float = Field(ge=0.0, le=1.0, default=0.0)
    source_mix: dict[str, int] = Field(default_factory=dict)
    headline_samples: list[str] = Field(default_factory=list)
    feature_value: float = Field(
        ge=0.0,
        le=100.0,
        default=50.0,
        description="0-100 score compatible with current news_sentiment_score style features.",
    )


class SentimentSnapshot(BaseModel):
    snapshot_id: str
    generated_at: str
    universe: list[str] = Field(default_factory=list)
    headline_count: int = 0
    overall_polarity: float = Field(ge=-1.0, le=1.0, default=0.0)
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    source_mix: dict[str, int] = Field(default_factory=dict)
    freshness_score: float = Field(ge=0.0, le=1.0, default=0.0)
    symbol_scores: list[SentimentSymbolScore] = Field(default_factory=list)
    lineage: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DebateTurn(BaseModel):
    round_number: int = Field(ge=1)
    bull_point: str
    bear_point: str
    evidence_focus: list[str] = Field(default_factory=list)
    confidence_shift: float = 0.0


class DebateReport(BaseModel):
    debate_id: str
    generated_at: str
    symbol: str
    universe: list[str] = Field(default_factory=list)
    bull_thesis: str
    bear_thesis: str
    turns: list[DebateTurn] = Field(default_factory=list)
    conflict_points: list[str] = Field(default_factory=list)
    consensus_points: list[str] = Field(default_factory=list)
    judge_verdict: TradingAction
    judge_confidence: float = Field(ge=0.0, le=1.0)
    dispute_score: float = Field(ge=0.0, le=1.0)
    recommended_action: TradingAction
    confidence_shift: float = 0.0
    requires_human_review: bool = False
    evidence_run_id: str | None = None
    factor_count: int = 0
    sentiment_snapshot_id: str | None = None
    sentiment_overview: dict[str, Any] = Field(default_factory=dict)
    expected_edge: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)
    lineage: list[str] = Field(default_factory=list)


class RiskApproval(BaseModel):
    approval_id: str
    generated_at: str
    symbol: str
    debate_id: str | None = None
    requested_action: TradingAction
    approved_action: TradingAction
    verdict: RiskVerdict
    kelly_fraction: float = Field(ge=0.0, le=1.0, default=0.0)
    recommended_weight: float = Field(ge=0.0, le=1.0, default=0.0)
    recommended_notional: float = Field(ge=0.0, default=0.0)
    max_position_weight: float = Field(ge=0.0, le=1.0, default=0.0)
    drawdown_estimate: float = Field(ge=0.0, le=1.0, default=0.0)
    signal_ttl_minutes: int = Field(ge=0, default=0)
    duplicate_order_detected: bool = False
    market_open: bool | None = None
    hard_blocks: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    rationale: list[str] = Field(default_factory=list)
    account_snapshot: dict[str, Any] = Field(default_factory=dict)
    positions_snapshot: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    lineage: list[str] = Field(default_factory=list)


class WatchlistItem(BaseModel):
    watchlist_id: str
    symbol: str
    added_date: str
    esg_score: float | None = None
    last_sentiment: float | None = None
    enabled: bool = True
    note: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class PriceAlertRecord(BaseModel):
    alert_id: str
    timestamp: str
    symbol: str
    trigger_type: Literal["price_move", "volume_spike", "manual_scan"]
    trigger_value: float
    threshold: float
    agent_analysis: str
    debate_id: str | None = None
    risk_decision: str | None = None
    execution_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DailyReviewReport(BaseModel):
    review_id: str
    review_date: str
    generated_at: str
    pnl: float = 0.0
    trades_count: int = 0
    esg_signals: list[str] = Field(default_factory=list)
    approved_decisions: int = 0
    blocked_decisions: int = 0
    report_text: str
    strategy_effectiveness: dict[str, Any] = Field(default_factory=dict)
    next_day_risk_flags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    lineage: list[str] = Field(default_factory=list)


class TradingJobRun(BaseModel):
    run_id: str
    job_name: str
    scheduled_for: str
    started_at: str
    completed_at: str | None = None
    status: JobStatus
    auto_submit_triggered: bool = False
    market_day: bool = True
    error: str = ""
    result_ref: dict[str, Any] = Field(default_factory=dict)


class TradingDecisionBundle(BaseModel):
    bundle_id: str
    symbol: str
    universe: list[str] = Field(default_factory=list)
    evidence_run_id: str | None = None
    sentiment: SentimentSnapshot
    debate: DebateReport
    risk: RiskApproval
    execution: "ExecutionResult | dict[str, Any]" = Field(default_factory=dict)
    alerts: list[PriceAlertRecord] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TradingMonitorStatus(BaseModel):
    running: bool = False
    mode: str = "paper"
    stream_mode: Literal["websocket", "polling", "idle"] = "idle"
    watchlist: list[str] = Field(default_factory=list)
    trigger_count: int = 0
    last_event_at: str | None = None
    last_trigger: dict[str, Any] | None = None
    warnings: list[str] = Field(default_factory=list)
    connection: dict[str, Any] = Field(default_factory=dict)


class StrategyAllocation(BaseModel):
    allocation_id: str
    strategy_id: str
    capital_allocation: float = Field(ge=0.0, le=1.0, default=0.0)
    max_symbols: int = Field(ge=1, default=10)
    status: Literal["active", "paused"] = "active"
    updated_at: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class StrategyTemplate(BaseModel):
    strategy_id: str
    display_name: str
    status: Literal["active", "paused", "draft"] = "active"
    factor_dependencies: list[str] = Field(default_factory=list)
    risk_profile: Literal["conservative", "balanced", "aggressive"] = "balanced"
    capital_allocation: float = Field(ge=0.0, le=1.0, default=0.0)
    allowed_symbols: list[str] = Field(default_factory=list)
    paper_ready: bool = True
    requires_debate: bool = True
    requires_risk_approval: bool = True
    description: str = ""
    lineage: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    updated_at: str


class AutopilotPolicy(BaseModel):
    policy_id: str
    generated_at: str
    execution_mode: Literal["paper", "live"] = "paper"
    requested_mode: Literal["paper", "live"] = "paper"
    effective_mode: Literal["paper", "live"] = "paper"
    paper_ready: bool = True
    live_ready: bool = False
    live_available: bool = False
    block_reason: str | None = None
    next_actions: list[str] = Field(default_factory=list)
    execution_permission: Literal["research", "auto_submit", "manual_review", "paper_auto_submit"] = "auto_submit"
    auto_submit_enabled: bool = False
    paper_auto_submit_enabled: bool = False
    armed: bool = False
    daily_budget_cap: float = Field(ge=0.0, default=0.0)
    per_trade_cap: float = Field(ge=0.0, default=0.0)
    max_open_positions: int = Field(ge=0, default=0)
    max_symbol_weight: float = Field(ge=0.0, le=1.0, default=0.0)
    allowed_universe: list[str] = Field(default_factory=list)
    allowed_strategies: list[str] = Field(default_factory=list)
    require_human_review_above: float = Field(ge=0.0, default=0.0)
    drawdown_limit: float = Field(ge=0.0, le=1.0, default=0.0)
    daily_loss_limit: float = Field(ge=0.0, default=0.0)
    signal_ttl: int = Field(ge=0, default=0)
    kill_switch: bool = False
    protections: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExecutionPathStatus(BaseModel):
    generated_at: str
    mode: str = "paper"
    requested_mode: str = "paper"
    effective_mode: str = "paper"
    paper_ready: bool = True
    live_ready: bool = False
    live_available: bool = False
    block_reason: str | None = None
    next_actions: list[str] = Field(default_factory=list)
    armed: bool = False
    daily_budget_cap: float = Field(ge=0.0, default=0.0)
    budget_remaining: float = Field(ge=0.0, default=0.0)
    judge_passed: bool = False
    risk_passed: bool = False
    kill_switch: bool = False
    current_stage: str = "idle"
    stages: list[dict[str, Any]] = Field(default_factory=list)
    lineage: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ExecutionIntent(BaseModel):
    intent_id: str
    created_at: str
    symbol: str
    requested_action: TradingAction
    approved_action: TradingAction | None = None
    execution_mode: str = "paper"
    strategy_slots: list[str] = Field(default_factory=list)
    factor_dependencies: list[str] = Field(default_factory=list)
    recommended_weight: float = Field(ge=0.0, le=1.0, default=0.0)
    recommended_notional: float = Field(ge=0.0, default=0.0)
    signal_ttl_minutes: int = Field(ge=0, default=0)
    paper_only: bool | None = None
    guards: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExecutionResult(BaseModel):
    execution_id: str
    generated_at: str
    symbol: str
    status: Literal["review_only", "blocked", "guarded", "submitted", "submit_failed"] = "review_only"
    venue: str = "alpaca"
    execution_mode: str = "paper"
    submitted: bool = False
    auto_submit: bool = False
    requested_action: TradingAction
    approved_action: TradingAction | None = None
    verdict: RiskVerdict = "halt"
    order_payload: dict[str, Any] = Field(default_factory=dict)
    receipt: dict[str, Any] | None = None
    warnings: list[str] = Field(default_factory=list)
    policy_gate_warnings: list[str] = Field(default_factory=list)
    next_action: str = ""
    trigger_event: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class FactorPipelineStage(BaseModel):
    stage: str
    status: Literal["ready", "pending", "review", "guarded"] = "pending"
    detail: str
    factors: list[str] = Field(default_factory=list)


class FactorPipelineManifest(BaseModel):
    manifest_id: str
    generated_at: str
    symbol: str | None = None
    strategy_slots: list[str] = Field(default_factory=list)
    factor_dependencies: list[str] = Field(default_factory=list)
    stages: list[FactorPipelineStage] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    next_action: str = ""
    lineage: list[str] = Field(default_factory=list)


class OrderApprovalLedger(BaseModel):
    ledger_id: str
    generated_at: str
    symbol: str
    execution_intent: ExecutionIntent | dict[str, Any] = Field(default_factory=dict)
    execution_result: ExecutionResult | dict[str, Any] | None = None
    debate_id: str | None = None
    approval_id: str | None = None
    verdict: Literal["armed", "submitted", "blocked", "review_only", "submit_failed"] = "blocked"
    submitted: bool = False
    receipt: dict[str, Any] | None = None
    warnings: list[str] = Field(default_factory=list)
    lineage: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class FusionReferenceItem(BaseModel):
    source_project: str
    capability: str
    target_surface: str
    status: Literal["implemented", "staged", "planned"] = "planned"
    notes: str = ""


class FusionReferenceManifest(BaseModel):
    manifest_id: str
    generated_at: str
    items: list[FusionReferenceItem] = Field(default_factory=list)
    lineage: list[str] = Field(default_factory=list)
