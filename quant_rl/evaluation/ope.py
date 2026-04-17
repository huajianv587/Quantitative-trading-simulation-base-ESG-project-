from __future__ import annotations

import numpy as np


def weighted_importance_sampling(rewards, target_probs, behavior_probs, gamma: float = 0.99) -> float:
    rewards = np.asarray(rewards, dtype=np.float64)
    target_probs = np.asarray(target_probs, dtype=np.float64)
    behavior_probs = np.asarray(behavior_probs, dtype=np.float64)
    ratios = np.clip(target_probs / np.clip(behavior_probs, 1e-8, None), 0.0, 50.0)
    weights = np.cumprod(ratios)
    discounts = gamma ** np.arange(len(rewards))
    if weights.sum() <= 1e-12:
        return 0.0
    return float(np.sum(weights * discounts * rewards) / np.sum(weights))


def doubly_robust(rewards, q_values, v_values, target_probs, behavior_probs, gamma: float = 0.99) -> float:
    rewards = np.asarray(rewards, dtype=np.float64)
    q_values = np.asarray(q_values, dtype=np.float64)
    v_values = np.asarray(v_values, dtype=np.float64)
    target_probs = np.asarray(target_probs, dtype=np.float64)
    behavior_probs = np.asarray(behavior_probs, dtype=np.float64)
    w = np.clip(target_probs / np.clip(behavior_probs, 1e-8, None), 0.0, 50.0)
    cum_w = np.cumprod(w)
    estimate = v_values[0] if len(v_values) else 0.0
    for t in range(len(rewards)):
        estimate += (gamma ** t) * cum_w[t] * (rewards[t] + gamma * (v_values[t + 1] if t + 1 < len(v_values) else 0.0) - q_values[t])
    return float(estimate)
