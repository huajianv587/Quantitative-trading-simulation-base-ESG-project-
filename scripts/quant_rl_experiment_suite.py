from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quant_rl.reporting.experiment_recorder import EXPERIMENT_GROUPS
from quant_rl.service.quant_service import QuantRLService


def _resolve_groups(raw: str) -> list[str]:
    if raw.strip().lower() == "all":
        return list(EXPERIMENT_GROUPS.keys())
    return [item.strip() for item in raw.split(",") if item.strip()]


def _action_type_for_algorithm(algorithm: str) -> str:
    return "discrete" if algorithm in {"buy_hold", "rule_based", "random", "dqn", "cql"} else "continuous"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the paper-style RL experiment suite")
    parser.add_argument("--dataset-path", default="storage/quant/demo/market.csv")
    parser.add_argument("--groups", default="B1_buyhold,B2_macd,B3_sac_noesg,B4_sac_esg,OURS_full")
    parser.add_argument("--episodes", type=int, default=30)
    parser.add_argument("--total-steps", type=int, default=120)
    args = parser.parse_args()

    service = QuantRLService()
    summary = {"dataset_path": args.dataset_path, "groups": [], "ok": True}

    for group_key in _resolve_groups(args.groups):
        group_cfg = EXPERIMENT_GROUPS[group_key]
        algorithm = str(group_cfg["algorithm"])
        seeds = group_cfg["seeds"] or [None]
        group_result = {"group": group_key, "algorithm": algorithm, "runs": []}

        for seed in seeds:
            action_type = _action_type_for_algorithm(algorithm)
            notes = f"protocol_group={group_key}; seed={seed}"

            if algorithm in {"buy_hold", "rule_based"}:
                backtest = service.backtest(
                    algorithm,
                    args.dataset_path,
                    action_type=action_type,
                    experiment_group=group_key,
                    seed=seed,
                    notes=notes,
                )
                group_result["runs"].append({"seed": seed, "train": None, "backtest": backtest})
                continue

            train = service.train(
                algorithm,
                args.dataset_path,
                action_type=action_type,
                episodes=args.episodes,
                total_steps=args.total_steps,
                experiment_group=group_key,
                seed=seed,
                notes=notes,
            )
            backtest = service.backtest(
                algorithm,
                args.dataset_path,
                checkpoint_path=train.get("checkpoint_path"),
                action_type=action_type,
                experiment_group=group_key,
                seed=seed,
                notes=notes,
            )
            group_result["runs"].append({"seed": seed, "train": train, "backtest": backtest})

        summary["groups"].append(group_result)

    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
