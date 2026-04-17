from __future__ import annotations

from dataclasses import dataclass

import torch
import torch.nn.functional as F
from torch import nn, optim

from quant_rl.models.common import default_device


@dataclass(slots=True)
class DecisionTransformerConfig:
    state_dim: int
    action_dim: int
    seq_len: int = 16
    hidden_dim: int = 64
    n_heads: int = 4
    n_layers: int = 1
    dropout: float = 0.1
    lr: float = 3e-4
    discrete: bool = False


class DecisionTransformer(nn.Module):
    def __init__(self, config: DecisionTransformerConfig) -> None:
        super().__init__()
        h = config.hidden_dim
        self.config = config
        self.timestep_emb = nn.Embedding(4096, h)
        self.return_emb = nn.Linear(1, h)
        self.state_emb = nn.Linear(config.state_dim, h)
        self.action_emb = nn.Linear(config.action_dim, h)
        enc = nn.TransformerEncoderLayer(d_model=h, nhead=config.n_heads, dim_feedforward=4*h, dropout=config.dropout, batch_first=True)
        self.transformer = nn.TransformerEncoder(enc, num_layers=config.n_layers)
        self.action_head = nn.Linear(h, config.action_dim)

    def forward(self, states, actions, returns_to_go, timesteps):
        B, T, _ = states.shape
        t = self.timestep_emb(timesteps)
        rtg = self.return_emb(returns_to_go.unsqueeze(-1)) + t
        st = self.state_emb(states) + t
        act = self.action_emb(actions) + t
        x = torch.stack([rtg, st, act], dim=2).reshape(B, 3*T, -1)
        h = self.transformer(x).reshape(B, T, 3, -1)
        return self.action_head(h[:, :, 1, :])


class DecisionTransformerTrainer:
    def __init__(self, config: DecisionTransformerConfig) -> None:
        self.config = config
        self.device = default_device()
        self.model = DecisionTransformer(config).to(self.device)
        self.optimizer = optim.Adam(self.model.parameters(), lr=config.lr)

    def update(self, states, actions, returns_to_go, timesteps):
        s = torch.as_tensor(states, dtype=torch.float32, device=self.device)
        a = torch.as_tensor(actions, dtype=torch.float32, device=self.device)
        rtg = torch.as_tensor(returns_to_go, dtype=torch.float32, device=self.device)
        ts = torch.as_tensor(timesteps, dtype=torch.long, device=self.device)
        pred = self.model(s, a, rtg, ts)
        loss = F.mse_loss(pred, a)
        self.optimizer.zero_grad(); loss.backward(); torch.nn.utils.clip_grad_norm_(self.model.parameters(), 1.0); self.optimizer.step()
        return {"loss": float(loss.item())}
