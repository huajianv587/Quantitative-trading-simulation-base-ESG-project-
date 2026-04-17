from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import torch
import torch.nn.functional as F
from torch import nn, optim

from quant_rl.models.common import default_device, mlp


@dataclass(slots=True)
class IQLConfig:
    state_dim: int
    action_dim: int = 1
    gamma: float = 0.99
    tau: float = 0.7
    beta: float = 3.0
    actor_lr: float = 3e-4
    critic_lr: float = 3e-4
    value_lr: float = 3e-4
    hidden_dim: int = 64
    grad_clip: float = 10.0


class _ContinuousQ(nn.Module):
    def __init__(self, state_dim: int, action_dim: int, hidden_dim: int) -> None:
        super().__init__()
        self.net = mlp([state_dim + action_dim, hidden_dim, hidden_dim, 1], activation=nn.ReLU)

    def forward(self, state: torch.Tensor, action: torch.Tensor) -> torch.Tensor:
        return self.net(torch.cat([state, action], dim=-1)).squeeze(-1)


class _Value(nn.Module):
    def __init__(self, state_dim: int, hidden_dim: int) -> None:
        super().__init__()
        self.net = mlp([state_dim, hidden_dim, hidden_dim, 1], activation=nn.ReLU)

    def forward(self, state: torch.Tensor) -> torch.Tensor:
        return self.net(state).squeeze(-1)


class _GaussianActor(nn.Module):
    def __init__(self, state_dim: int, action_dim: int, hidden_dim: int) -> None:
        super().__init__()
        self.backbone = mlp([state_dim, hidden_dim, hidden_dim], activation=nn.ReLU, output_activation=nn.ReLU)
        self.mean = nn.Linear(hidden_dim, action_dim)
        self.log_std = nn.Linear(hidden_dim, action_dim)

    def forward(self, state: torch.Tensor):
        h = self.backbone(state)
        return self.mean(h), self.log_std(h).clamp(-5, 2)

    def log_prob_of(self, state: torch.Tensor, action: torch.Tensor) -> torch.Tensor:
        mean, log_std = self.forward(state)
        dist = torch.distributions.Normal(mean, log_std.exp())
        clipped = action.clamp(-0.999, 0.999)
        z = torch.atanh(clipped)
        log_prob = dist.log_prob(z).sum(dim=-1)
        log_prob -= torch.log(1 - clipped.pow(2) + 1e-6).sum(dim=-1)
        return log_prob


class IQLLearner:
    def __init__(self, config: IQLConfig) -> None:
        self.config = config
        self.device = default_device()
        self.q1 = _ContinuousQ(config.state_dim, config.action_dim, config.hidden_dim).to(self.device)
        self.q2 = _ContinuousQ(config.state_dim, config.action_dim, config.hidden_dim).to(self.device)
        self.v = _Value(config.state_dim, config.hidden_dim).to(self.device)
        self.actor = _GaussianActor(config.state_dim, config.action_dim, config.hidden_dim).to(self.device)
        self.q_opt = optim.Adam(list(self.q1.parameters()) + list(self.q2.parameters()), lr=config.critic_lr)
        self.v_opt = optim.Adam(self.v.parameters(), lr=config.value_lr)
        self.actor_opt = optim.Adam(self.actor.parameters(), lr=config.actor_lr)

    @staticmethod
    def _expectile_loss(diff: torch.Tensor, expectile: float) -> torch.Tensor:
        weight = torch.where(diff > 0, expectile, 1 - expectile)
        return (weight * diff.pow(2)).mean()

    def act(self, state: np.ndarray, deterministic: bool = True):
        s = torch.as_tensor(state, dtype=torch.float32, device=self.device).unsqueeze(0)
        with torch.no_grad():
            mean, _ = self.actor(s)
            a = torch.tanh(mean)
        out = a.squeeze(0).cpu().numpy().astype(np.float32)
        return float(out.squeeze()) if out.size == 1 else out

    def update(self, batch):
        cfg = self.config
        s = torch.as_tensor(batch.state, dtype=torch.float32, device=self.device)
        a = torch.as_tensor(batch.action, dtype=torch.float32, device=self.device).reshape(-1, cfg.action_dim)
        r = torch.as_tensor(batch.reward, dtype=torch.float32, device=self.device)
        s2 = torch.as_tensor(batch.next_state, dtype=torch.float32, device=self.device)
        d = torch.as_tensor(batch.done, dtype=torch.float32, device=self.device)
        with torch.no_grad():
            q_target = r + cfg.gamma * (1 - d) * self.v(s2)
        q1 = self.q1(s, a)
        q2 = self.q2(s, a)
        q_loss = F.mse_loss(q1, q_target) + F.mse_loss(q2, q_target)
        self.q_opt.zero_grad(); q_loss.backward(); torch.nn.utils.clip_grad_norm_(list(self.q1.parameters())+list(self.q2.parameters()), cfg.grad_clip); self.q_opt.step()
        with torch.no_grad():
            q = torch.min(self.q1(s, a), self.q2(s, a))
        v = self.v(s)
        v_loss = self._expectile_loss(q - v, cfg.tau)
        self.v_opt.zero_grad(); v_loss.backward(); torch.nn.utils.clip_grad_norm_(self.v.parameters(), cfg.grad_clip); self.v_opt.step()
        with torch.no_grad():
            adv = q - self.v(s)
            weights = torch.exp(cfg.beta * adv).clamp(max=20.0)
        log_prob = self.actor.log_prob_of(s, a)
        actor_loss = -(weights * log_prob).mean()
        self.actor_opt.zero_grad(); actor_loss.backward(); torch.nn.utils.clip_grad_norm_(self.actor.parameters(), cfg.grad_clip); self.actor_opt.step()
        return {"q_loss": float(q_loss.item()), "v_loss": float(v_loss.item()), "actor_loss": float(actor_loss.item())}
