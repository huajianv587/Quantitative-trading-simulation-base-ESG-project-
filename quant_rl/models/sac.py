from __future__ import annotations

import torch
from torch import nn

from quant_rl.models.common import mlp


class GaussianPolicy(nn.Module):
    def __init__(self, state_dim: int, action_dim: int = 1, hidden_dim: int = 256) -> None:
        super().__init__()
        self.backbone = mlp([state_dim, hidden_dim, hidden_dim], activation=nn.ReLU, output_activation=nn.ReLU)
        self.mean_layer = nn.Linear(hidden_dim, action_dim)
        self.log_std_layer = nn.Linear(hidden_dim, action_dim)

    def forward(self, state: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        feat = self.backbone(state)
        mean = self.mean_layer(feat)
        log_std = self.log_std_layer(feat).clamp(-5, 2)
        return mean, log_std

    def sample(self, state: torch.Tensor):
        mean, log_std = self.forward(state)
        std = log_std.exp()
        dist = torch.distributions.Normal(mean, std)
        z = dist.rsample()
        action = torch.tanh(z)
        log_prob = dist.log_prob(z).sum(dim=-1)
        log_prob -= torch.log(1 - action.pow(2) + 1e-6).sum(dim=-1)
        mean_action = torch.tanh(mean)
        return action, log_prob, mean_action
