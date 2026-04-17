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
    parser = argparse.ArgumentParser(description="Run a full training job for a recipe using best params")
    parser.add_argument("--recipe-key", required=True)
    parser.add_argument("--dataset-path", required=True)
    parser.add_argument("--total-steps", type=int, default=500)
    parser.add_argument("--episodes", type=int, default=50)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--params-json", default="{}")
    args = parser.parse_args()

    service = QuantRLService()
    recipe = RECIPE_PRESETS[args.recipe_key]
    action_type = "discrete" if recipe["algorithm"] in {"dqn", "cql"} else "continuous"
    trainer_hparams = json.loads(args.params_json or "{}")
    result = service.train(
        recipe["algorithm"],
        args.dataset_path,
        action_type=action_type,
        episodes=args.episodes,
        total_steps=args.total_steps,
        use_demo_if_missing=False,
        experiment_group=None,
        seed=args.seed,
        notes=f"full_train_recipe={args.recipe_key}",
        trainer_hparams=trainer_hparams,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
