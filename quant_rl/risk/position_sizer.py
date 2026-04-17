from __future__ import annotations

import math


def vol_target_position(
    signal: float,
    realized_vol: float,
    target_vol: float = 0.15,
    clip_abs_position: float = 1.0,
) -> float:
    scaled = signal * target_vol / max(realized_vol, 1e-4)
    return max(-clip_abs_position, min(clip_abs_position, scaled))


def kelly_fraction(edge: float, variance: float, clip_fraction: float = 1.0) -> float:
    if variance <= 0:
        return 0.0
    raw = edge / variance
    return max(-clip_fraction, min(clip_fraction, raw))
