from __future__ import annotations

import numpy as np


def weighted_importance_sampling(
    rewards: np.ndarray,
    behavior_probs: np.ndarray,
    target_probs: np.ndarray,
) -> float:
    behavior_probs = np.clip(behavior_probs, 1e-8, 1.0)
    target_probs = np.clip(target_probs, 1e-8, 1.0)
    ratios = target_probs / behavior_probs
    weights = ratios / (ratios.sum() + 1e-8)
    return float(np.sum(weights * rewards))


def direct_method(q_values: np.ndarray) -> float:
    return float(np.mean(q_values))
