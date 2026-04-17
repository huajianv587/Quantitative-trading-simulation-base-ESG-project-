from __future__ import annotations

import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from quant_rl.service.quant_service import QuantRLService

if __name__ == '__main__':
    service = QuantRLService()
    print(service.train('dqn', 'storage/quant/demo/market.csv', action_type='discrete', episodes=2, total_steps=20))
