from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from quant_rl.infrastructure.types import RunInfo


@dataclass(slots=True)
class SACTrainConfig:
    total_steps: int = 5000
    warmup_steps: int = 1000


class SACTrainer:
    def __init__(self, agent, env, run_id: str, checkpoint_path: str, artifact_store, repository) -> None:
        self.agent = agent
        self.env = env
        self.run_id = run_id
        self.checkpoint_path = checkpoint_path
        self.artifact_store = artifact_store
        self.repository = repository

    def train(self, cfg: SACTrainConfig | None = None) -> dict:
        cfg = cfg or SACTrainConfig()
        state, _ = self.env.reset()
        completed_rewards = []
        episode_reward = 0.0
        latest_metrics = {}
        for step in range(cfg.total_steps):
            deterministic = step < cfg.warmup_steps
            action = self.agent.act(state, deterministic=False if not deterministic else False)
            next_state, reward, terminated, truncated, _ = self.env.step(action)
            done = terminated or truncated
            self.agent.remember(state, action, reward, next_state, done)
            latest_metrics = self.agent.update()
            episode_reward += reward
            state = next_state
            if done:
                completed_rewards.append(episode_reward)
                episode_reward = 0.0
                state, _ = self.env.reset()

        self.agent.save(self.checkpoint_path)
        summary = {
            "total_steps": cfg.total_steps,
            "avg_episode_reward": float(np.mean(completed_rewards)) if completed_rewards else 0.0,
            "episodes_finished": len(completed_rewards),
            "training_metrics": latest_metrics,
            "checkpoint_path": self.checkpoint_path,
        }
        self.repository.save(
            RunInfo(
                run_id=self.run_id,
                algorithm=self.agent.algorithm,
                phase="phase_2_sac",
                status="trained",
                metrics=summary,
                artifacts={"checkpoint_path": self.checkpoint_path},
            )
        )
        return summary
