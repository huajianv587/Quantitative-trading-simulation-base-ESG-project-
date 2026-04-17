from __future__ import annotations

import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


import argparse, json
from quant_rl.service.quant_service import QuantRLService


def main() -> None:
    p=argparse.ArgumentParser(description='Train quant RL policy')
    p.add_argument('--algorithm', default='hybrid_frontier')
    p.add_argument('--dataset-path', default='storage/quant/demo/market.csv')
    p.add_argument('--action-type', default='continuous')
    p.add_argument('--episodes', type=int, default=30)
    p.add_argument('--total-steps', type=int, default=100)
    p.add_argument('--experiment-group', default=None)
    p.add_argument('--seed', type=int, default=None)
    p.add_argument('--notes', default=None)
    p.add_argument('--no-demo', action='store_true')
    args=p.parse_args()
    service=QuantRLService()
    result=service.train(
        args.algorithm,
        args.dataset_path,
        args.action_type,
        args.episodes,
        args.total_steps,
        not args.no_demo,
        experiment_group=args.experiment_group,
        seed=args.seed,
        notes=args.notes,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))

if __name__ == '__main__':
    main()
