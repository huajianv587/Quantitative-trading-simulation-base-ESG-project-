from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quant_rl.service.quant_service import QuantRLService, RECIPE_PRESETS


def main() -> None:
    parser = argparse.ArgumentParser(description="Backtest a trained recipe checkpoint")
    parser.add_argument("--recipe-key", required=True)
    parser.add_argument("--dataset-path", required=True)
    parser.add_argument("--checkpoint-path", required=True)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    service = QuantRLService()
    recipe = RECIPE_PRESETS[args.recipe_key]
    action_type = "discrete" if recipe["algorithm"] in {"dqn", "cql"} else "continuous"
    result = service.backtest(
        recipe["algorithm"],
        args.dataset_path,
        checkpoint_path=args.checkpoint_path,
        action_type=action_type,
        experiment_group=None,
        seed=args.seed,
        notes=f"backtest_recipe={args.recipe_key}",
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
