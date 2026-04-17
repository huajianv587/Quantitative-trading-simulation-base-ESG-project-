from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quant_rl.service.quant_service import QuantRLService


def main() -> None:
    parser = argparse.ArgumentParser(description="Quick-search RL hyperparameters for a recipe")
    parser.add_argument("--recipe-key", required=True)
    parser.add_argument("--dataset-path", default=None)
    parser.add_argument("--trials", type=int, default=5)
    parser.add_argument("--quick-steps", type=int, default=120)
    parser.add_argument("--action-type", default=None)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    service = QuantRLService()
    result = service.search_recipe(
        args.recipe_key,
        dataset_path=args.dataset_path,
        trials=args.trials,
        quick_steps=args.quick_steps,
        action_type=args.action_type,
        seed=args.seed,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
