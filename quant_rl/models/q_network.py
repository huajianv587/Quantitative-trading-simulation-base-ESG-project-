from __future__ import annotations

import torch
from torch import nn

from quant_rl.models.common import mlp


class QNetwork(nn.Module):
    def __init__(self, state_dim: int, action_dim: int, hidden_dim: int = 128) -> None:
        super().__init__()
        self.net = mlp([state_dim, hidden_dim, hidden_dim, action_dim], activation=nn.ReLU)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class DuelingQNetwork(nn.Module):
    def __init__(self, state_dim: int, action_dim: int, hidden_dim: int = 128) -> None:
        super().__init__()
        self.backbone = mlp([state_dim, hidden_dim, hidden_dim], activation=nn.ReLU, output_activation=nn.ReLU)
        self.value_head = nn.Linear(hidden_dim, 1)
        self.adv_head = nn.Linear(hidden_dim, action_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        h = self.backbone(x)
        value = self.value_head(h)
        adv = self.adv_head(h)
        return value + adv - adv.mean(dim=-1, keepdim=True)


class TwinContinuousQNetwork(nn.Module):
    def __init__(self, state_dim: int, action_dim: int, hidden_dim: int = 256) -> None:
        super().__init__()
        self.q1 = mlp([state_dim + action_dim, hidden_dim, hidden_dim, 1], activation=nn.ReLU)
        self.q2 = mlp([state_dim + action_dim, hidden_dim, hidden_dim, 1], activation=nn.ReLU)

    def forward(self, state: torch.Tensor, action: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        x = torch.cat([state, action], dim=-1)
        return self.q1(x).squeeze(-1), self.q2(x).squeeze(-1)
