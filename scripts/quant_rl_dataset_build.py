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
    parser = argparse.ArgumentParser(description="Build RL datasets from the current quant market-data stack")
    parser.add_argument("--symbols", default="NVDA,MSFT,AAPL,NEE")
    parser.add_argument("--dataset-name", default=None)
    parser.add_argument("--limit", type=int, default=240)
    parser.add_argument("--force-refresh", action="store_true")
    parser.add_argument("--no-esg", action="store_true")
    args = parser.parse_args()

    service = QuantRLService()
    symbols = [item.strip().upper() for item in args.symbols.split(",") if item.strip()]
    result = service.build_market_dataset(
        symbols,
        dataset_name=args.dataset_name,
        limit=args.limit,
        force_refresh=args.force_refresh,
        include_esg=not args.no_esg,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
