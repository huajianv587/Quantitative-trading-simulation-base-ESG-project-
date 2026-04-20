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
    execution: dict[str, Any] = Field(default_factory=dict)
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
