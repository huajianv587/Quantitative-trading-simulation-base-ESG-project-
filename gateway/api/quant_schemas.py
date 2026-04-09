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
    mode: str = "paper"
    submit_orders: bool = False
    max_orders: int = 2
    per_order_notional: float | None = None
    order_type: str = "market"
    time_in_force: str = "day"
    extended_hours: bool = False
