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
    parser = argparse.ArgumentParser(description="Build an RL dataset for a predefined recipe")
    parser.add_argument("--recipe-key", required=True)
    parser.add_argument("--dataset-name", default=None)
    parser.add_argument("--limit", type=int, default=240)
    parser.add_argument("--force-refresh", action="store_true")
    parser.add_argument("--symbols", default="")
    args = parser.parse_args()

    service = QuantRLService()
    symbols = [item.strip().upper() for item in args.symbols.split(",") if item.strip()]
    result = service.build_recipe_dataset(
        args.recipe_key,
        dataset_name=args.dataset_name,
        limit=args.limit,
        force_refresh=args.force_refresh,
        symbols=symbols or None,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
