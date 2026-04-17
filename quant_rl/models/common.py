from __future__ import annotations

from typing import Iterable

import torch
from torch import nn


def mlp(sizes: Iterable[int], activation=nn.ReLU, output_activation=nn.Identity) -> nn.Sequential:
    sizes = list(sizes)
    layers = []
    for i in range(len(sizes) - 1):
        act = activation if i < len(sizes) - 2 else output_activation
        layers += [nn.Linear(sizes[i], sizes[i + 1]), act()]
    return nn.Sequential(*layers)


def default_device() -> torch.device:
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")
