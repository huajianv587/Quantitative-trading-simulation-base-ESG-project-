from __future__ import annotations

import torch
from torch import nn

from quant_rl.models.common import mlp


class QEnsemble(nn.Module):
    def __init__(self, state_dim: int, action_dim: int = 1, hidden_dim: int = 128, n_members: int = 5) -> None:
        super().__init__()
        self.members = nn.ModuleList([mlp([state_dim + action_dim, hidden_dim, hidden_dim, 1], activation=nn.ReLU) for _ in range(n_members)])

    def forward(self, state: torch.Tensor, action: torch.Tensor) -> torch.Tensor:
        x = torch.cat([state, action], dim=-1)
        vals = [m(x).squeeze(-1) for m in self.members]
        return torch.stack(vals, dim=0)

    def mean_and_std(self, state: torch.Tensor, action: torch.Tensor):
        out = self.forward(state, action)
        return out.mean(dim=0), out.std(dim=0)
