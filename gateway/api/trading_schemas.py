from __future__ import annotations

from pydantic import BaseModel, Field


class TradingWatchlistAddRequest(BaseModel):
    symbol: str = "AAPL"
    esg_score: float | None = None
    last_sentiment: float | None = None
    note: str = ""
    enabled: bool = True


class TradingSentimentRunRequest(BaseModel):
    universe: list[str] = Field(default_factory=list)
    providers: list[str] = Field(default_factory=list)
    quota_guard: bool = True


class TradingDebateRunRequest(BaseModel):
    symbol: str = "AAPL"
    universe: list[str] = Field(default_factory=list)
    query: str = "Run a bull vs bear trading debate"
    mode: str = "mixed"
    providers: list[str] = Field(default_factory=list)
    quota_guard: bool = True
    rebuttal_rounds: int = 2


class TradingRiskEvaluateRequest(BaseModel):
    symbol: str = "AAPL"
    debate_payload: dict | None = None
    signal_ttl_minutes: int = 180


class TradingCycleRunRequest(BaseModel):
    symbol: str = "AAPL"
    universe: list[str] = Field(default_factory=list)
    query: str = "Run a full trading cycle"
    mode: str = "mixed"
    providers: list[str] = Field(default_factory=list)
    quota_guard: bool = True
    auto_submit: bool = True


class TradingJobRunRequest(BaseModel):
    scheduled_for: str | None = None


class PaperRewardCandidateRunRequest(BaseModel):
    universe: list[str] = Field(default_factory=list)
    max_candidates: int = 5
    per_order_notional: float | None = None
    benchmark: str = "SPY"
    allow_duplicates: bool = False
    submit_orders: bool | None = None


class PaperRewardSettleRequest(BaseModel):
    candidate_id: str | None = None
    force_refresh: bool = False
    limit: int = 200


class AutopilotPolicyUpdateRequest(BaseModel):
    execution_mode: str = "paper"
    execution_permission: str = "auto_submit"
    auto_submit_enabled: bool = False
    paper_auto_submit_enabled: bool = False
    armed: bool = False
    daily_budget_cap: float = 10000.0
    per_trade_cap: float = 2500.0
    max_open_positions: int = 5
    max_symbol_weight: float = 0.2
    allowed_universe: list[str] = Field(default_factory=list)
    allowed_strategies: list[str] = Field(default_factory=list)
    require_human_review_above: float = 7500.0
    drawdown_limit: float = 0.06
    daily_loss_limit: float = 1500.0
    signal_ttl: int = 180
    kill_switch: bool = False
    protections: list[str] = Field(default_factory=list)


class AutopilotArmRequest(BaseModel):
    armed: bool = True


class AutopilotDisarmRequest(BaseModel):
    armed: bool = False


class StrategyToggleRequest(BaseModel):
    status: str = "active"


class StrategyAllocationRequest(BaseModel):
    capital_allocation: float = 0.0
    max_symbols: int = 10
    status: str = "active"
