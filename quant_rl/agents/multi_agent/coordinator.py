from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class WeightedSubAgent:
    name: str
    agent: object
    weight: float = 1.0


class MultiAgentCoordinator:
    def __init__(self, sub_agents: list[WeightedSubAgent], continuous: bool = False) -> None:
        self.sub_agents = sub_agents
        self.continuous = continuous

    def act(self, state, deterministic: bool = True):
        decisions = []
        for item in self.sub_agents:
            action = item.agent.act(state, deterministic=deterministic)
            if isinstance(action, tuple):
                action = action[0]
            decisions.append((item.weight, action))
        if self.continuous:
            total_weight = sum(w for w, _ in decisions) + 1e-8
            return sum(w * float(a) for w, a in decisions) / total_weight

        votes: dict[int, float] = {}
        for weight, action in decisions:
            votes[int(action)] = votes.get(int(action), 0.0) + weight
        return max(votes.items(), key=lambda x: x[1])[0]
