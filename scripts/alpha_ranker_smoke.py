from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from gateway.quant.service import QuantSystemService


def main() -> int:
    service = QuantSystemService()
    payload = service.run_research_pipeline(
        universe_symbols=["AAPL", "MSFT", "TSLA", "NEE", "PG"],
        research_question="Smoke-test alpha ranker inference path.",
        benchmark="SPY",
        capital_base=500000,
    )
    summary = {
        "alpha_ranker": service.alpha_ranker.status(),
        "top_signals": payload["signals"][:5],
        "portfolio_positions": payload["portfolio"]["positions"][:3],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
