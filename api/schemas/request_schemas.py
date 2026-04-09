
from pydantic import BaseModel, Field


class ResearchRequest(BaseModel):
    universe: list[str] = Field(default_factory=list)
    benchmark: str = "SPY"
    research_question: str = "Run the default ESG quant research pipeline"
    capital_base: float = 1_000_000
    horizon_days: int = 20


class BacktestRequest(BaseModel):
    strategy_name: str = "ESG Multi-Factor Long-Only"
    universe: list[str] = Field(default_factory=list)
    benchmark: str = "SPY"
    capital_base: float = 1_000_000
    lookback_days: int = 126
