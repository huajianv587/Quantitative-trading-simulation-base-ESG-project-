from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import torch

from quant_rl.agents.ppo_agent import PPOAgent, PPOConfig


@dataclass(slots=True)
class RiskAwarePPOConfig(PPOConfig):
    cost_budget: float = 0.02
    lagrangian_lr: float = 1e-2


class RiskAwarePPOAgent(PPOAgent):
    def __init__(self, config: RiskAwarePPOConfig) -> None:
        super().__init__(config)
        self.risk_config = config
        self.log_lambda = torch.tensor(0.0, device=self.device, requires_grad=True)
        self.lambda_opt = torch.optim.Adam([self.log_lambda], lr=config.lagrangian_lr)

    @property
    def lagrangian(self) -> torch.Tensor:
        return self.log_lambda.exp()

    def update_with_cost(self, states, actions, old_log_probs, advantages, returns, costs):
        costs = np.asarray(costs, dtype=np.float32)
        cost_adv = (costs - costs.mean()) / (costs.std() + 1e-8)
        combined = np.asarray(advantages, dtype=np.float32) - float(self.lagrangian.detach().cpu().item()) * cost_adv
        metrics = super().update(states, actions, old_log_probs, combined, returns)
        violation = torch.as_tensor(float(costs.mean() - self.risk_config.cost_budget), dtype=torch.float32, device=self.device)
        loss = -(self.log_lambda * violation.detach())
        self.lambda_opt.zero_grad(); loss.backward(); self.lambda_opt.step()
        metrics.update({"lagrangian": float(self.lagrangian.item()), "cost_mean": float(costs.mean())})
        return metrics
