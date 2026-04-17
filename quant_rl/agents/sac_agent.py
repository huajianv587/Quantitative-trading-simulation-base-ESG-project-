from __future__ import annotations

import copy
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from torch import optim

from quant_rl.agents.base import BaseAgent
from quant_rl.models.common import default_device
from quant_rl.models.q_network import TwinContinuousQNetwork
from quant_rl.models.sac import GaussianPolicy
from quant_rl.training.common import ReplayBuffer


@dataclass(slots=True)
class SACConfig:
    state_dim: int
    action_dim: int = 1
    gamma: float = 0.99
    tau: float = 0.005
    actor_lr: float = 3e-4
    critic_lr: float = 3e-4
    alpha_lr: float = 3e-4
    batch_size: int = 128
    buffer_cap: int = 100_000
    start_learning: int = 1000
    hidden_dim: int = 256
    target_entropy: float = -1.0


class SACAgent(BaseAgent):
    algorithm = "sac"

    def __init__(self, config: SACConfig) -> None:
        self.config = config
        self.device = default_device()
        self.actor = GaussianPolicy(
            state_dim=config.state_dim, action_dim=config.action_dim, hidden_dim=config.hidden_dim
        ).to(self.device)
        self.critic = TwinContinuousQNetwork(
            state_dim=config.state_dim, action_dim=config.action_dim, hidden_dim=config.hidden_dim
        ).to(self.device)
        self.critic_target = copy.deepcopy(self.critic).to(self.device)
        self.actor_opt = optim.Adam(self.actor.parameters(), lr=config.actor_lr)
        self.critic_opt = optim.Adam(self.critic.parameters(), lr=config.critic_lr)
        self.log_alpha = torch.tensor(np.log(0.2), device=self.device, requires_grad=True)
        self.alpha_opt = optim.Adam([self.log_alpha], lr=config.alpha_lr)
        self.buffer = ReplayBuffer(config.buffer_cap)

    @property
    def alpha(self) -> torch.Tensor:
        return self.log_alpha.exp()

    def act(self, state, deterministic: bool = False):
        state_t = torch.as_tensor(state, dtype=torch.float32, device=self.device).unsqueeze(0)
        with torch.no_grad():
            action, _, mean_action = self.actor.sample(state_t)
        out = mean_action if deterministic else action
        value = out.squeeze(0).cpu().numpy().astype(np.float32)
        if value.size == 1:
            return float(value.squeeze())
        return value

    def remember(self, state, action, reward, next_state, done) -> None:
        self.buffer.push(
            state,
            np.array([action], dtype=np.float32) if np.isscalar(action) else np.array(action, dtype=np.float32),
            reward,
            next_state,
            float(done),
        )

    def update(self):
        c = self.config
        if len(self.buffer) < max(c.batch_size, c.start_learning):
            return {"loss": None}
        batch = self.buffer.sample(c.batch_size)
        s = torch.as_tensor(batch.state, dtype=torch.float32, device=self.device)
        a = torch.as_tensor(batch.action, dtype=torch.float32, device=self.device).reshape(-1, c.action_dim)
        r = torch.as_tensor(batch.reward, dtype=torch.float32, device=self.device)
        s_ = torch.as_tensor(batch.next_state, dtype=torch.float32, device=self.device)
        done = torch.as_tensor(batch.done, dtype=torch.float32, device=self.device)

        with torch.no_grad():
            next_action, next_log_prob, _ = self.actor.sample(s_)
            q1_t, q2_t = self.critic_target(s_, next_action)
            target_q = torch.min(q1_t, q2_t) - self.alpha.detach() * next_log_prob
            td_target = r + c.gamma * (1 - done) * target_q

        q1, q2 = self.critic(s, a)
        critic_loss = F.mse_loss(q1, td_target) + F.mse_loss(q2, td_target)
        self.critic_opt.zero_grad()
        critic_loss.backward()
        self.critic_opt.step()

        new_action, log_prob, _ = self.actor.sample(s)
        q1_pi, q2_pi = self.critic(s, new_action)
        actor_loss = (self.alpha.detach() * log_prob - torch.min(q1_pi, q2_pi)).mean()
        self.actor_opt.zero_grad()
        actor_loss.backward()
        self.actor_opt.step()

        alpha_loss = -(self.log_alpha * (log_prob + c.target_entropy).detach()).mean()
        self.alpha_opt.zero_grad()
        alpha_loss.backward()
        self.alpha_opt.step()

        self._soft_update(self.critic, self.critic_target, c.tau)
        return {
            "critic_loss": float(critic_loss.item()),
            "actor_loss": float(actor_loss.item()),
            "alpha": float(self.alpha.item()),
        }

    @staticmethod
    def _soft_update(source, target, tau: float) -> None:
        for src_param, tgt_param in zip(source.parameters(), target.parameters()):
            tgt_param.data.copy_(tau * src_param.data + (1 - tau) * tgt_param.data)

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        torch.save(
            {
                "config": asdict(self.config),
                "actor": self.actor.state_dict(),
                "critic": self.critic.state_dict(),
                "critic_target": self.critic_target.state_dict(),
                "log_alpha": float(self.log_alpha.detach().cpu().item()),
            },
            path,
        )

    @classmethod
    def load(cls, path: str | Path, **kwargs):
        checkpoint = torch.load(path, map_location=default_device())
        config = SACConfig(**checkpoint["config"])
        agent = cls(config)
        agent.actor.load_state_dict(checkpoint["actor"])
        agent.critic.load_state_dict(checkpoint["critic"])
        agent.critic_target.load_state_dict(checkpoint["critic_target"])
        stored_alpha = float(checkpoint.get("log_alpha", np.log(0.2)))
        restored_log_alpha = float(np.log(max(stored_alpha, 1e-8))) if stored_alpha > 0 else stored_alpha
        agent.log_alpha.data.fill_(restored_log_alpha)
        return agent

    def describe(self):
        return {"algorithm": self.algorithm, "config": asdict(self.config)}
