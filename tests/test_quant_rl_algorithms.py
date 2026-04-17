import numpy as np

from quant_rl.algorithms.iql import IQLConfig, IQLLearner
from quant_rl.algorithms.decision_transformer import DecisionTransformerConfig, DecisionTransformerTrainer
from quant_rl.algorithms.world_model import WorldModelConfig, WorldModelResearchAgent
from quant_rl.training.common import TransitionBatch


def test_iql_update_smoke():
    learner = IQLLearner(IQLConfig(state_dim=8, action_dim=1, hidden_dim=32))
    batch = TransitionBatch(state=np.random.randn(16,8).astype('float32'), action=np.random.uniform(-1,1,(16,1)).astype('float32'), reward=np.random.randn(16).astype('float32'), next_state=np.random.randn(16,8).astype('float32'), done=np.zeros(16,dtype='float32'))
    assert 'q_loss' in learner.update(batch)


def test_dt_update_smoke():
    trainer = DecisionTransformerTrainer(DecisionTransformerConfig(state_dim=8, action_dim=1, seq_len=4, hidden_dim=32, n_layers=1))
    states=np.random.randn(2,4,8).astype('float32'); actions=np.random.uniform(-1,1,(2,4,1)).astype('float32'); rtg=np.random.randn(2,4).astype('float32'); ts=np.tile(np.arange(4),(2,1)).astype('int64')
    assert 'loss' in trainer.update(states, actions, rtg, ts)


def test_world_model_update_smoke():
    agent = WorldModelResearchAgent(WorldModelConfig(state_dim=8, action_dim=1, hidden_dim=32, latent_dim=16))
    batch = TransitionBatch(state=np.random.randn(16,8).astype('float32'), action=np.random.uniform(-1,1,(16,1)).astype('float32'), reward=np.random.randn(16).astype('float32'), next_state=np.random.randn(16,8).astype('float32'), done=np.zeros(16,dtype='float32'))
    assert 'loss' in agent.update(batch)
