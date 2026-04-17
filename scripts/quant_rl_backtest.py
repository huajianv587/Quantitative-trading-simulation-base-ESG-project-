from __future__ import annotations

import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


import argparse, json
from quant_rl.service.quant_service import QuantRLService


def main() -> None:
    p=argparse.ArgumentParser(description='Backtest quant RL policy')
    p.add_argument('--algorithm', default='rule_based')
    p.add_argument('--dataset-path', default='storage/quant/demo/market.csv')
    p.add_argument('--checkpoint-path', default=None)
    p.add_argument('--action-type', default='continuous')
    p.add_argument('--experiment-group', default=None)
    p.add_argument('--seed', type=int, default=None)
    p.add_argument('--notes', default=None)
    args=p.parse_args()
    service=QuantRLService()
    result=service.backtest(
        args.algorithm,
        args.dataset_path,
        args.checkpoint_path,
        args.action_type,
        experiment_group=args.experiment_group,
        seed=args.seed,
        notes=args.notes,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))

if __name__ == '__main__':
    main()
