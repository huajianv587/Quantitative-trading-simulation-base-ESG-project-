from __future__ import annotations

import torch
from torch import nn

from quant_rl.models.common import mlp


class DiscreteActorCritic(nn.Module):
    def __init__(self, state_dim: int, action_dim: int, hidden_dim: int = 64) -> None:
        super().__init__()
        self.shared = mlp([state_dim, hidden_dim, hidden_dim], activation=nn.Tanh, output_activation=nn.Tanh)
        self.actor = nn.Linear(hidden_dim, action_dim)
        self.critic = nn.Linear(hidden_dim, 1)

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        feat = self.shared(x)
        return self.actor(feat), self.critic(feat).squeeze(-1)

    def get_action(self, state: torch.Tensor, deterministic: bool = False):
        logits, value = self.forward(state)
        dist = torch.distributions.Categorical(logits=logits)
        if deterministic:
            action = torch.argmax(logits, dim=-1)
        else:
            action = dist.sample()
        log_prob = dist.log_prob(action)
        return action, log_prob, value


class GaussianActorCritic(nn.Module):
    def __init__(self, state_dim: int, action_dim: int = 1, hidden_dim: int = 64) -> None:
        super().__init__()
        self.shared = mlp([state_dim, hidden_dim, hidden_dim], activation=nn.Tanh, output_activation=nn.Tanh)
        self.actor_mean = nn.Linear(hidden_dim, action_dim)
        self.actor_log_std = nn.Parameter(torch.zeros(action_dim))
        self.critic = nn.Linear(hidden_dim, 1)

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        feat = self.shared(x)
        mean = self.actor_mean(feat)
        log_std = self.actor_log_std.expand_as(mean).clamp(-5, 2)
        value = self.critic(feat).squeeze(-1)
        return mean, log_std, value

    def get_action(self, state: torch.Tensor, deterministic: bool = False):
        mean, log_std, value = self.forward(state)
        std = log_std.exp()
        dist = torch.distributions.Normal(mean, std)
        pre_tanh = mean if deterministic else dist.rsample()
        action = torch.tanh(pre_tanh)
        log_prob = dist.log_prob(pre_tanh).sum(dim=-1)
        log_prob -= torch.log(1 - action.pow(2) + 1e-6).sum(dim=-1)
        return action, log_prob, value
