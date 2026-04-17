from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import torch
import torch.nn.functional as F

from quant_rl.infrastructure.types import RunInfo


@dataclass(slots=True)
class OfflineCQLConfig:
    gradient_steps: int = 1000
    batch_size: int = 64
    conservative_alpha: float = 0.5


class OfflineDQNTrainer:
    def __init__(self, agent, transitions, run_id: str, checkpoint_path: str, repository) -> None:
        self.agent = agent
        self.transitions = transitions
        self.run_id = run_id
        self.checkpoint_path = checkpoint_path
        self.repository = repository
        for tr in transitions:
            self.agent.remember(tr.state, tr.action, tr.reward, tr.next_state, tr.done)

    def train(self, cfg: OfflineCQLConfig | None = None) -> dict:
        cfg = cfg or OfflineCQLConfig()
        losses = []
        for _ in range(cfg.gradient_steps):
            if len(self.agent.buffer) < max(cfg.batch_size, self.agent.config.start_learning):
                continue
            batch = self.agent.buffer.sample(cfg.batch_size)
            s = torch.as_tensor(batch.state, dtype=torch.float32, device=self.agent.device)
            a = torch.as_tensor(batch.action, dtype=torch.long, device=self.agent.device)
            r = torch.as_tensor(batch.reward, dtype=torch.float32, device=self.agent.device)
            s_ = torch.as_tensor(batch.next_state, dtype=torch.float32, device=self.agent.device)
            done = torch.as_tensor(batch.done, dtype=torch.float32, device=self.agent.device)

            q_all = self.agent.q_net(s)
            q_val = q_all.gather(1, a.unsqueeze(1)).squeeze(1)
            with torch.no_grad():
                next_q = self.agent.tgt_net(s_).max(dim=1).values
                td_target = r + self.agent.config.gamma * next_q * (1 - done)

            bellman_loss = F.smooth_l1_loss(q_val, td_target)
            conservative_penalty = torch.logsumexp(q_all, dim=1).mean() - q_val.mean()
            loss = bellman_loss + cfg.conservative_alpha * conservative_penalty

            self.agent.optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(self.agent.q_net.parameters(), self.agent.config.grad_clip)
            self.agent.optimizer.step()
            self.agent.global_step += 1
            if self.agent.global_step % self.agent.config.target_sync == 0:
                self.agent.tgt_net.load_state_dict(self.agent.q_net.state_dict())
            losses.append(float(loss.item()))

        self.agent.save(self.checkpoint_path)
        summary = {
            "gradient_steps": cfg.gradient_steps,
            "avg_loss": float(np.mean(losses)) if losses else 0.0,
            "checkpoint_path": self.checkpoint_path,
        }
        self.repository.save(
            RunInfo(
                run_id=self.run_id,
                algorithm="cql",
                phase="phase_3_offline",
                status="trained",
                metrics=summary,
                artifacts={"checkpoint_path": self.checkpoint_path},
            )
        )
        return summary
