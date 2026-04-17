from __future__ import annotations

from quant_rl.algorithms.decision_transformer import DecisionTransformerConfig, DecisionTransformerTrainer
from quant_rl.algorithms.iql import IQLConfig, IQLLearner
from quant_rl.algorithms.world_model import WorldModelConfig, WorldModelResearchAgent

RESEARCH_BUILDERS = {
    "iql": lambda state_dim, action_dim: IQLLearner(IQLConfig(state_dim=state_dim, action_dim=action_dim, hidden_dim=64)),
    "decision_transformer": lambda state_dim, action_dim: DecisionTransformerTrainer(DecisionTransformerConfig(state_dim=state_dim, action_dim=action_dim, hidden_dim=64)),
    "world_model": lambda state_dim, action_dim: WorldModelResearchAgent(WorldModelConfig(state_dim=state_dim, action_dim=action_dim, hidden_dim=64, latent_dim=32)),
}
