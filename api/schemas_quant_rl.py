from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class QuantRLDatasetBuildRequest(BaseModel):
    symbols: list[str] = Field(default_factory=list)
    dataset_name: str | None = None
    limit: int = 240
    force_refresh: bool = False
    include_esg: bool = True
    start_date: str | None = None
    end_date: str | None = None


class QuantRLRecipeBuildRequest(BaseModel):
    recipe_key: str
    dataset_name: str | None = None
    limit: int = 240
    force_refresh: bool = False
    symbols: list[str] = Field(default_factory=list)
    start_date: str | None = None
    end_date: str | None = None


class QuantRLSearchRequest(BaseModel):
    recipe_key: str
    dataset_path: str | None = None
    trials: int = 5
    quick_steps: int = 120
    action_type: Literal["discrete", "continuous"] | None = None
    seed: int = 42


class QuantRLDemoDatasetRequest(BaseModel):
    target_path: str = "storage/quant/demo/market.csv"
    seed: int = 42
    length: int = 1500


class QuantRLTrainRequest(BaseModel):
    algorithm: Literal["dqn", "ppo", "sac", "cql", "iql", "decision_transformer", "world_model", "hybrid_frontier"]
    dataset_path: str = Field(default="storage/quant/demo/market.csv")
    action_type: Literal["discrete", "continuous"] = "discrete"
    episodes: int = 50
    total_steps: int = 500
    use_demo_if_missing: bool = True
    experiment_group: str | None = None
    seed: int | None = None
    notes: str | None = None
    trainer_hparams: dict[str, Any] = Field(default_factory=dict)


class QuantRLBacktestRequest(BaseModel):
    algorithm: Literal["buy_hold", "rule_based", "random", "dqn", "ppo", "sac", "iql", "world_model", "hybrid_frontier"]
    dataset_path: str = Field(default="storage/quant/demo/market.csv")
    checkpoint_path: str | None = None
    action_type: Literal["discrete", "continuous"] = "discrete"
    experiment_group: str | None = None
    seed: int | None = None
    notes: str | None = None


class QuantRLPromoteRequest(BaseModel):
    run_id: str
    strategy_id: str = "rl_timing_overlay"
    required_data_tier: Literal["l1", "l2"] = "l2"


class QuantRLResponse(BaseModel):
    run_id: str
    algorithm: str
    phase: str | None = None
    checkpoint_path: str | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)
    artifacts: dict[str, Any] = Field(default_factory=dict)
    config: dict[str, Any] = Field(default_factory=dict)


class QuantRLBacktestResponse(BaseModel):
    run_id: str
    metrics: dict[str, Any] = Field(default_factory=dict)
    artifacts: dict[str, Any] = Field(default_factory=dict)
    config: dict[str, Any] = Field(default_factory=dict)


class QuantRLPromoteResponse(BaseModel):
    generated_at: str
    run_id: str
    strategy_id: str
    dataset_id: str | None = None
    protection_status: str = "review"
    required_data_tier: str = "l2"
    eligibility_status: str = "review"
    blocking_reasons: list[str] = Field(default_factory=list)
    latest_backtest_report: str | None = None
    market_depth_status: dict[str, Any] = Field(default_factory=dict)
    promotion_status: str = "research_only"
