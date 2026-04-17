from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from quant_rl.infrastructure.types import RunInfo
from quant_rl.training.common import RolloutBuffer


@dataclass(slots=True)
class PPOTrainConfig:
    total_steps: int = 4096
    horizon: int = 256


class PPOTrainer:
    def __init__(self, agent, env, run_id: str, checkpoint_path: str, artifact_store, repository) -> None:
        self.agent = agent
        self.env = env
        self.run_id = run_id
        self.checkpoint_path = checkpoint_path
        self.artifact_store = artifact_store
        self.repository = repository

    def train(self, cfg: PPOTrainConfig | None = None) -> dict:
        cfg = cfg or PPOTrainConfig()
        state, _ = self.env.reset()
        rollout = RolloutBuffer()
        completed_rewards = []
        episode_reward = 0.0
        update_metrics = {}

        for step in range(cfg.total_steps):
            action, log_prob, value = self.agent.act(state, deterministic=False)
            next_state, reward, terminated, truncated, _ = self.env.step(action)
            done = terminated or truncated
            rollout.add(state, action, log_prob, reward, value, done)
            episode_reward += reward
            state = next_state

            if done:
                completed_rewards.append(episode_reward)
                episode_reward = 0.0
                state, _ = self.env.reset()

            if len(rollout) >= cfg.horizon:
                _, _, next_value = self.agent.act(state, deterministic=True)
                advantages, returns = self.agent.compute_gae(
                    rollout.rewards,
                    rollout.values,
                    rollout.dones,
                    next_value,
                )
                update_metrics = self.agent.update(
                    states=np.array(rollout.states, dtype=np.float32),
                    actions=np.array(rollout.actions),
                    old_log_probs=np.array(rollout.log_probs, dtype=np.float32),
                    advantages=advantages,
                    returns=returns,
                )
                rollout.clear()

        self.agent.save(self.checkpoint_path)
        summary = {
            "total_steps": cfg.total_steps,
            "avg_episode_reward": float(np.mean(completed_rewards)) if completed_rewards else 0.0,
            "episodes_finished": len(completed_rewards),
            "training_metrics": update_metrics,
            "checkpoint_path": self.checkpoint_path,
        }
        self.repository.save(
            RunInfo(
                run_id=self.run_id,
                algorithm=self.agent.algorithm,
                phase="phase_2_ppo",
                status="trained",
                metrics=summary,
                artifacts={"checkpoint_path": self.checkpoint_path},
            )
        )
        return summary
