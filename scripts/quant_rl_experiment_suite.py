from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quant_rl.infrastructure.settings import get_settings
from quant_rl.reporting.experiment_recorder import EXPERIMENT_GROUPS
from quant_rl.service.quant_service import QuantRLService


def _resolve_groups(raw: str) -> list[str]:
    if raw.strip().lower() == "all":
        return list(EXPERIMENT_GROUPS.keys())
    return [item.strip() for item in raw.split(",") if item.strip()]


def _action_type_for_algorithm(algorithm: str) -> str:
    return "discrete" if algorithm in {"buy_hold", "rule_based", "random", "dqn", "cql"} else "continuous"


def _namespace_root(namespace: str) -> Path:
    return ROOT / "storage" / "quant" / "rl-experiments" / namespace


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the paper-style RL experiment suite")
    parser.add_argument("--dataset-path", default="storage/quant/demo/market.csv")
    parser.add_argument("--groups", default="B1_buyhold,B2_macd,B3_sac_noesg,B4_sac_esg,OURS_full")
    parser.add_argument("--episodes", type=int, default=30)
    parser.add_argument("--total-steps", type=int, default=120)
    parser.add_argument("--run-namespace", default="smoke", choices=["smoke", "dev", "paper-run"])
    parser.add_argument("--sample", default="full_2022_2025", choices=["full_2022_2025", "post_esg_effective"])
    parser.add_argument("--formula-mode", default=None, choices=[None, "v2", "v2_1"], help="Formula isolation for ESG datasets.")
    parser.add_argument("--output-summary", default=None)
    args = parser.parse_args()

    namespace_root = _namespace_root(args.run_namespace)
    if args.formula_mode:
        namespace_root = namespace_root / f"formula_{args.formula_mode}"
    os.environ["QUANT_RL_EXPERIMENT_ROOT"] = str(namespace_root)
    get_settings.cache_clear()
    service = QuantRLService()
    summary = {
        "run_namespace": args.run_namespace,
        "sample": args.sample,
        "formula_mode": args.formula_mode,
        "dataset_path": args.dataset_path,
        "groups": [],
        "ok": True,
    }

    for group_key in _resolve_groups(args.groups):
        group_cfg = EXPERIMENT_GROUPS[group_key]
        algorithm = str(group_cfg["algorithm"])
        seeds = group_cfg["seeds"] or [None]
        group_result = {"group": group_key, "algorithm": algorithm, "runs": []}

        for seed in seeds:
            action_type = _action_type_for_algorithm(algorithm)
            notes = f"namespace={args.run_namespace}; sample={args.sample}; protocol_group={group_key}; seed={seed}"

            if algorithm in {"buy_hold", "rule_based"}:
                backtest = service.backtest(
                    algorithm,
                    args.dataset_path,
                    action_type=action_type,
                    experiment_group=group_key,
                    seed=seed,
                    notes=notes,
                    formula_mode=args.formula_mode,
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
                formula_mode=args.formula_mode,
            )
            backtest = service.backtest(
                algorithm,
                args.dataset_path,
                checkpoint_path=train.get("checkpoint_path"),
                action_type=action_type,
                experiment_group=group_key,
                seed=seed,
                notes=notes,
                formula_mode=args.formula_mode,
            )
            group_result["runs"].append({"seed": seed, "train": train, "backtest": backtest})

        summary["groups"].append(group_result)

    output_path = Path(args.output_summary) if args.output_summary else namespace_root / "summary" / f"experiment_suite_{args.sample}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    summary["output_path"] = str(output_path)
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
