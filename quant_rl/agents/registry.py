from __future__ import annotations

from quant_rl.agents.dqn_agent import DQNAgent, DQNConfig
from quant_rl.agents.ppo_agent import PPOAgent, PPOConfig
from quant_rl.agents.random_agent import RandomAgent
from quant_rl.agents.rule_based_agent import RuleBasedMomentumAgent
from quant_rl.agents.sac_agent import SACAgent, SACConfig


def build_agent(algorithm: str, state_dim: int, action_dim: int, continuous: bool = False):
    algorithm = algorithm.lower()
    if algorithm == "dqn":
        return DQNAgent(DQNConfig(state_dim=state_dim, action_dim=action_dim))
    if algorithm == "ppo":
        return PPOAgent(PPOConfig(state_dim=state_dim, action_dim=action_dim, continuous=continuous))
    if algorithm == "sac":
        return SACAgent(SACConfig(state_dim=state_dim, action_dim=action_dim))
    if algorithm == "random":
        raise ValueError("Random agent needs env.action_space; instantiate directly.")
    if algorithm == "rule_based":
        return RuleBasedMomentumAgent(continuous=continuous)
    raise ValueError(f"Unsupported algorithm: {algorithm}")


def available_agents() -> list[dict]:
    return [
        {"algorithm": "dqn", "phase": "phase_1", "action_type": "discrete"},
        {"algorithm": "ppo", "phase": "phase_2", "action_type": "discrete_or_continuous"},
        {"algorithm": "sac", "phase": "phase_2", "action_type": "continuous"},
        {"algorithm": "cql", "phase": "phase_3", "action_type": "discrete_offline"},
        {"algorithm": "rule_based", "phase": "baseline", "action_type": "discrete_or_continuous"},
        {"algorithm": "random", "phase": "baseline", "action_type": "discrete_or_continuous"},
    ]
