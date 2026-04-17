from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from quant_rl.infrastructure.types import RunInfo


@dataclass(slots=True)
class DQNTrainConfig:
    episodes: int = 30
    max_steps_per_episode: int = 2000
    eval_every: int = 10


class DQNTrainer:
    def __init__(self, agent, env, run_id: str, checkpoint_path: str, artifact_store, repository) -> None:
        self.agent = agent
        self.env = env
        self.run_id = run_id
        self.checkpoint_path = checkpoint_path
        self.artifact_store = artifact_store
        self.repository = repository

    def train(self, cfg: DQNTrainConfig | None = None) -> dict:
        cfg = cfg or DQNTrainConfig()
        episode_rewards: list[float] = []
        latest_metrics = {}
        for episode in range(cfg.episodes):
            state, _ = self.env.reset()
            total_reward = 0.0
            for _ in range(cfg.max_steps_per_episode):
                action = self.agent.act(state, deterministic=False)
                next_state, reward, terminated, truncated, _ = self.env.step(action)
                done = terminated or truncated
                self.agent.remember(state, action, reward, next_state, done)
                latest_metrics = self.agent.update()
                total_reward += reward
                state = next_state
                if done:
                    break
            episode_rewards.append(total_reward)

        self.agent.save(self.checkpoint_path)
        summary = {
            "episodes": cfg.episodes,
            "avg_reward": float(np.mean(episode_rewards)) if episode_rewards else 0.0,
            "last_reward": float(episode_rewards[-1]) if episode_rewards else 0.0,
            "training_metrics": latest_metrics,
            "checkpoint_path": self.checkpoint_path,
        }
        self.repository.save(
            RunInfo(
                run_id=self.run_id,
                algorithm=self.agent.algorithm,
                phase="phase_1_dqn",
                status="trained",
                metrics=summary,
                artifacts={"checkpoint_path": self.checkpoint_path},
            )
        )
        return summary
