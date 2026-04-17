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
from quant_rl.models.q_network import DuelingQNetwork, QNetwork
from quant_rl.training.common import ReplayBuffer


@dataclass(slots=True)
class DQNConfig:
    state_dim: int
    action_dim: int
    gamma: float = 0.99
    lr: float = 1e-3
    batch_size: int = 64
    buffer_cap: int = 50_000
    target_sync: int = 100
    eps_start: float = 1.0
    eps_end: float = 0.01
    eps_decay: int = 10_000
    start_learning: int = 1000
    grad_clip: float = 10.0
    hidden_dim: int = 128
    dueling: bool = True
    double_q: bool = True


class DQNAgent(BaseAgent):
    algorithm = "dqn"

    def __init__(self, config: DQNConfig) -> None:
        self.config = config
        self.device = default_device()
        q_cls = DuelingQNetwork if config.dueling else QNetwork
        self.q_net = q_cls(config.state_dim, config.action_dim, hidden_dim=config.hidden_dim).to(self.device)
        self.tgt_net = copy.deepcopy(self.q_net).to(self.device)
        self.tgt_net.eval()
        self.optimizer = optim.Adam(self.q_net.parameters(), lr=config.lr)
        self.buffer = ReplayBuffer(config.buffer_cap)
        self.global_step = 0

    def epsilon(self) -> float:
        c = self.config
        return max(c.eps_end, c.eps_start - (c.eps_start - c.eps_end) * self.global_step / c.eps_decay)

    def act(self, state, deterministic: bool = False):
        if (not deterministic) and np.random.rand() < self.epsilon():
            return int(np.random.randint(0, self.config.action_dim))
        with torch.no_grad():
            s = torch.as_tensor(state, dtype=torch.float32, device=self.device).unsqueeze(0)
            return int(self.q_net(s).argmax(dim=1).item())

    def remember(self, state, action, reward, next_state, done) -> None:
        self.buffer.push(state, action, reward, next_state, float(done))

    def update(self):
        c = self.config
        if len(self.buffer) < max(c.batch_size, c.start_learning):
            self.global_step += 1
            return {"loss": None}
        batch = self.buffer.sample(c.batch_size)
        s = torch.as_tensor(batch.state, dtype=torch.float32, device=self.device)
        a = torch.as_tensor(batch.action, dtype=torch.long, device=self.device)
        r = torch.as_tensor(batch.reward, dtype=torch.float32, device=self.device)
        s_ = torch.as_tensor(batch.next_state, dtype=torch.float32, device=self.device)
        done = torch.as_tensor(batch.done, dtype=torch.float32, device=self.device)

        q_val = self.q_net(s).gather(1, a.unsqueeze(1)).squeeze(1)
        with torch.no_grad():
            if c.double_q:
                next_actions = self.q_net(s_).argmax(dim=1)
                next_q = self.tgt_net(s_).gather(1, next_actions.unsqueeze(1)).squeeze(1)
            else:
                next_q = self.tgt_net(s_).max(dim=1).values
            td_target = r + c.gamma * next_q * (1 - done)

        loss = F.smooth_l1_loss(q_val, td_target)
        self.optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(self.q_net.parameters(), c.grad_clip)
        self.optimizer.step()

        self.global_step += 1
        if self.global_step % c.target_sync == 0:
            self.tgt_net.load_state_dict(self.q_net.state_dict())
        return {"loss": float(loss.item()), "epsilon": self.epsilon()}

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        torch.save(
            {
                "config": asdict(self.config),
                "state_dict": self.q_net.state_dict(),
                "target_state_dict": self.tgt_net.state_dict(),
                "global_step": self.global_step,
            },
            path,
        )

    @classmethod
    def load(cls, path: str | Path, **kwargs):
        checkpoint = torch.load(path, map_location=default_device())
        config = DQNConfig(**checkpoint["config"])
        agent = cls(config)
        agent.q_net.load_state_dict(checkpoint["state_dict"])
        agent.tgt_net.load_state_dict(checkpoint["target_state_dict"])
        agent.global_step = checkpoint.get("global_step", 0)
        return agent

    def describe(self):
        return {"algorithm": self.algorithm, "config": asdict(self.config)}
