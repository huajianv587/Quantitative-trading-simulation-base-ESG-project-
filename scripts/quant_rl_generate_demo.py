from __future__ import annotations

import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from quant_rl.analysis.features import add_technical_features
from quant_rl.data.loaders import generate_synthetic_ohlcv


def main() -> None:
    target = Path('storage/quant/demo/market.csv')
    target.parent.mkdir(parents=True, exist_ok=True)
    add_technical_features(generate_synthetic_ohlcv()).to_csv(target, index=False)
    print(f'generated: {target}')

if __name__ == '__main__':
    main()
