from __future__ import annotations

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


class ModelReleaseRequest(BaseModel):
    actor: str = "operator"
    model_key: str
    version: str
    action: str = "promote"
    notes: str = ""
    canary_percent: float | None = None
