from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import torch
from torch import optim

from quant_rl.agents.base import BaseAgent
from quant_rl.models.actor_critic import DiscreteActorCritic, GaussianActorCritic
from quant_rl.models.common import default_device


@dataclass(slots=True)
class PPOConfig:
    state_dim: int
    action_dim: int
    continuous: bool = False
    gamma: float = 0.99
    lam: float = 0.95
    clip_eps: float = 0.2
    lr: float = 3e-4
    entropy_coef: float = 0.01
    critic_coef: float = 0.5
    epochs: int = 4
    grad_clip: float = 0.5
    hidden_dim: int = 64


class PPOAgent(BaseAgent):
    algorithm = "ppo"

    def __init__(self, config: PPOConfig) -> None:
        self.config = config
        self.device = default_device()
        if config.continuous:
            self.model = GaussianActorCritic(
                state_dim=config.state_dim,
                action_dim=config.action_dim,
                hidden_dim=config.hidden_dim,
            ).to(self.device)
        else:
            self.model = DiscreteActorCritic(
                state_dim=config.state_dim,
                action_dim=config.action_dim,
                hidden_dim=config.hidden_dim,
            ).to(self.device)
        self.optimizer = optim.Adam(self.model.parameters(), lr=config.lr)

    def act(self, state, deterministic: bool = False):
        state_t = torch.as_tensor(state, dtype=torch.float32, device=self.device).unsqueeze(0)
        with torch.no_grad():
            action, log_prob, value = self.model.get_action(state_t, deterministic=deterministic)
        if self.config.continuous:
            action_np = action.squeeze(0).cpu().numpy().astype(np.float32)
            if action_np.size == 1:
                action_np = float(action_np.squeeze())
            return action_np, float(log_prob.item()), float(value.item())
        return int(action.item()), float(log_prob.item()), float(value.item())

    def compute_gae(self, rewards, values, dones, next_value):
        advantages = []
        gae = 0.0
        for r, v, d in zip(reversed(rewards), reversed(values), reversed(dones)):
            delta = r + self.config.gamma * next_value * (1 - d) - v
            gae = delta + self.config.gamma * self.config.lam * (1 - d) * gae
            advantages.insert(0, gae)
            next_value = v
        returns = [a + v for a, v in zip(advantages, values)]
        return np.array(advantages, dtype=np.float32), np.array(returns, dtype=np.float32)

    def update(self, states, actions, old_log_probs, advantages, returns):
        states_t = torch.as_tensor(states, dtype=torch.float32, device=self.device)
        if self.config.continuous:
            actions_t = torch.as_tensor(actions, dtype=torch.float32, device=self.device).reshape(-1, self.config.action_dim)
        else:
            actions_t = torch.as_tensor(actions, dtype=torch.long, device=self.device)
        old_log_probs_t = torch.as_tensor(old_log_probs, dtype=torch.float32, device=self.device)
        advantages_t = torch.as_tensor(advantages, dtype=torch.float32, device=self.device)
        returns_t = torch.as_tensor(returns, dtype=torch.float32, device=self.device)

        advantages_t = (advantages_t - advantages_t.mean()) / (advantages_t.std() + 1e-8)
        metrics = {}
        for _ in range(self.config.epochs):
            if self.config.continuous:
                mean, log_std, values = self.model(states_t)
                std = log_std.exp()
                dist = torch.distributions.Normal(mean, std)
                pre_tanh = torch.atanh(actions_t.clamp(-0.999, 0.999))
                new_log_probs = dist.log_prob(pre_tanh).sum(dim=-1)
                new_log_probs -= torch.log(1 - actions_t.pow(2) + 1e-6).sum(dim=-1)
                entropy = dist.entropy().sum(dim=-1).mean()
            else:
                logits, values = self.model(states_t)
                dist = torch.distributions.Categorical(logits=logits)
                new_log_probs = dist.log_prob(actions_t)
                entropy = dist.entropy().mean()

            ratio = (new_log_probs - old_log_probs_t).exp()
            surr1 = ratio * advantages_t
            surr2 = ratio.clamp(1 - self.config.clip_eps, 1 + self.config.clip_eps) * advantages_t
            actor_loss = -torch.min(surr1, surr2).mean()
            critic_loss = 0.5 * (returns_t - values).pow(2).mean()
            loss = actor_loss + self.config.critic_coef * critic_loss - self.config.entropy_coef * entropy

            self.optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), self.config.grad_clip)
            self.optimizer.step()

            metrics = {
                "loss": float(loss.item()),
                "actor_loss": float(actor_loss.item()),
                "critic_loss": float(critic_loss.item()),
                "entropy": float(entropy.item()),
            }
        return metrics

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        torch.save({"config": asdict(self.config), "state_dict": self.model.state_dict()}, path)

    @classmethod
    def load(cls, path: str | Path, **kwargs):
        checkpoint = torch.load(path, map_location=default_device())
        config = PPOConfig(**checkpoint["config"])
        agent = cls(config)
        agent.model.load_state_dict(checkpoint["state_dict"])
        return agent

    def describe(self):
        return {"algorithm": self.algorithm, "config": asdict(self.config)}
