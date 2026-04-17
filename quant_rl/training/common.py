from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass
from typing import Any

import numpy as np
import torch


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


@dataclass(slots=True)
class TransitionBatch:
    state: np.ndarray
    action: np.ndarray
    reward: np.ndarray
    next_state: np.ndarray
    done: np.ndarray


class ReplayBuffer:
    def __init__(self, capacity: int) -> None:
        self.buffer = deque(maxlen=capacity)

    def push(self, state, action, reward, next_state, done) -> None:
        self.buffer.append((state, action, reward, next_state, done))

    def sample(self, batch_size: int) -> TransitionBatch:
        batch = random.sample(self.buffer, batch_size)
        state, action, reward, next_state, done = zip(*batch)
        return TransitionBatch(
            state=np.array(state, dtype=np.float32),
            action=np.array(action, dtype=np.float32),
            reward=np.array(reward, dtype=np.float32),
            next_state=np.array(next_state, dtype=np.float32),
            done=np.array(done, dtype=np.float32),
        )

    def __len__(self) -> int:
        return len(self.buffer)


class RolloutBuffer:
    def __init__(self) -> None:
        self.clear()

    def clear(self) -> None:
        self.states: list[np.ndarray] = []
        self.actions: list[np.ndarray | int | float] = []
        self.log_probs: list[float] = []
        self.rewards: list[float] = []
        self.values: list[float] = []
        self.dones: list[float] = []

    def add(self, state, action, log_prob, reward, value, done) -> None:
        self.states.append(np.array(state, dtype=np.float32))
        self.actions.append(action)
        self.log_probs.append(float(log_prob))
        self.rewards.append(float(reward))
        self.values.append(float(value))
        self.dones.append(float(done))

    def __len__(self) -> int:
        return len(self.states)
