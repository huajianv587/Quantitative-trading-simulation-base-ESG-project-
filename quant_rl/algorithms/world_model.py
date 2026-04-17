from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import torch
import torch.nn.functional as F
from torch import nn, optim

from quant_rl.models.common import default_device, mlp


@dataclass(slots=True)
class WorldModelConfig:
    state_dim: int
    action_dim: int = 1
    latent_dim: int = 32
    hidden_dim: int = 64
    horizon: int = 6
    cem_iters: int = 3
    cem_candidates: int = 64
    cem_topk: int = 8
    lr: float = 3e-4


class LatentWorldModel(nn.Module):
    def __init__(self, config: WorldModelConfig) -> None:
        super().__init__()
        self.config = config
        self.encoder = mlp([config.state_dim, config.hidden_dim, config.latent_dim], activation=nn.ReLU)
        self.transition = mlp([config.latent_dim + config.action_dim, config.hidden_dim, config.latent_dim], activation=nn.ReLU)
        self.reward_head = mlp([config.latent_dim + config.action_dim, config.hidden_dim, 1], activation=nn.ReLU)
        self.value_head = mlp([config.latent_dim, config.hidden_dim, 1], activation=nn.ReLU)

    def latent(self, state: torch.Tensor) -> torch.Tensor:
        return self.encoder(state)

    def step_latent(self, latent: torch.Tensor, action: torch.Tensor):
        x = torch.cat([latent, action], dim=-1)
        return self.transition(x), self.reward_head(x).squeeze(-1)

    def value(self, latent: torch.Tensor) -> torch.Tensor:
        return self.value_head(latent).squeeze(-1)


class WorldModelResearchAgent:
    def __init__(self, config: WorldModelConfig) -> None:
        self.config = config
        self.device = default_device()
        self.model = LatentWorldModel(config).to(self.device)
        self.optimizer = optim.Adam(self.model.parameters(), lr=config.lr)

    def update(self, batch):
        c = self.config
        s = torch.as_tensor(batch.state, dtype=torch.float32, device=self.device)
        a = torch.as_tensor(batch.action, dtype=torch.float32, device=self.device).reshape(-1, c.action_dim)
        r = torch.as_tensor(batch.reward, dtype=torch.float32, device=self.device)
        s2 = torch.as_tensor(batch.next_state, dtype=torch.float32, device=self.device)
        z = self.model.latent(s)
        z2 = self.model.latent(s2).detach()
        pred_z2, pred_r = self.model.step_latent(z, a)
        dyn_loss = F.mse_loss(pred_z2, z2)
        reward_loss = F.mse_loss(pred_r, r)
        value_loss = F.mse_loss(self.model.value(z), r)
        loss = dyn_loss + reward_loss + 0.1 * value_loss
        self.optimizer.zero_grad(); loss.backward(); torch.nn.utils.clip_grad_norm_(self.model.parameters(), 5.0); self.optimizer.step()
        return {"loss": float(loss.item()), "dyn_loss": float(dyn_loss.item()), "reward_loss": float(reward_loss.item())}

    def act(self, state: np.ndarray):
        c = self.config
        s = torch.as_tensor(state, dtype=torch.float32, device=self.device).unsqueeze(0)
        with torch.no_grad():
            z0 = self.model.latent(s)
            mean = torch.zeros(c.horizon, c.action_dim, device=self.device)
            std = torch.ones(c.horizon, c.action_dim, device=self.device)
            for _ in range(c.cem_iters):
                acts = torch.normal(mean.expand(c.cem_candidates, -1, -1), std.expand(c.cem_candidates, -1, -1)).clamp(-1, 1)
                returns = self._evaluate(z0, acts)
                idx = returns.topk(c.cem_topk).indices
                elite = acts[idx]
                mean = elite.mean(dim=0)
                std = elite.std(dim=0).clamp_min(1e-3)
            a = mean[0].clamp(-1, 1).cpu().numpy().astype(np.float32)
        return float(a.squeeze()) if a.size == 1 else a

    def _evaluate(self, z0, acts):
        z = z0.repeat(acts.size(0), 1)
        ret = torch.zeros(acts.size(0), device=self.device)
        disc = 1.0
        for t in range(acts.size(1)):
            z, r = self.model.step_latent(z, acts[:, t, :])
            ret += disc * r
            disc *= 0.99
        ret += disc * self.model.value(z)
        return ret
