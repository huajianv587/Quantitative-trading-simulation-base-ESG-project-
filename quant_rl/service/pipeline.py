from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class PipelineStage:
    name: str
    goal: str
    artifact: str


FRONTIER_PIPELINE = [
    PipelineStage("phase_00_foundation", "feature pipeline, reward, env, risk shield", "validated dataset + env smoke test"),
    PipelineStage("phase_01_discrete_dqn", "buy/sell/hold baseline", "baseline checkpoint + report"),
    PipelineStage("phase_02_continuous_control", "continuous position sizing with SAC/PPO", "continuous checkpoint"),
    PipelineStage("phase_03_offline_rl", "CQL/IQL offline pretrain", "offline policy + OPE metrics"),
    PipelineStage("phase_04_sequence_policy", "Decision Transformer sequence policy", "sequence checkpoint"),
    PipelineStage("phase_05_world_model_research", "world-model planning lane", "latent model + planner artifacts"),
    PipelineStage("phase_06_hybrid_frontier", "offline→online hybrid stack", "paper-trade candidate policy"),
    PipelineStage("phase_07_deployment", "paper/live guarded rollout", "deployment manifest + guardrail report"),
]
