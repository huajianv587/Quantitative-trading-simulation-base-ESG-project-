from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

from gateway.scheduler.data_sources import DataSourceManager


def _parse_pairs(raw_items: list[str]) -> list[tuple[str, str | None]]:
    pairs: list[tuple[str, str | None]] = []
    for raw in raw_items:
        item = raw.strip()
        if not item:
            continue
        if ":" in item:
            company, ticker = item.split(":", 1)
            pairs.append((company.strip(), ticker.strip() or None))
        else:
            pairs.append((item, None))
    return pairs


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync real market / ESG data from configured providers.")
    parser.add_argument(
        "--companies",
        nargs="+",
        default=["Tesla:TSLA", "Apple:AAPL", "Microsoft:MSFT"],
        help="Company list, optionally in Company:TICKER format.",
    )
    parser.add_argument("--persist", action="store_true", help="Persist snapshots to configured storage.")
    parser.add_argument("--force-refresh", action="store_true", help="Bypass cached data where possible.")
    parser.add_argument("--output", type=str, default="", help="Optional JSON output file path.")
    args = parser.parse_args()

    manager = DataSourceManager()
    status = manager.source_status()
    payload: dict[str, object] = {
        "configured_sources": status,
        "results": [],
    }

    pairs = _parse_pairs(args.companies)
    if not pairs:
        raise SystemExit("No companies provided.")

    for company, ticker in pairs:
        if args.persist:
            success = manager.sync_company_snapshot(company, ticker=ticker, force_refresh=args.force_refresh)
            payload["results"].append({
                "company": company,
                "ticker": ticker,
                "persisted": success,
            })
            continue

        data = manager.fetch_company_data(company, ticker=ticker)
        payload["results"].append({
            "company": data.company_name,
            "ticker": data.ticker,
            "industry": data.industry,
            "market_cap": data.market_cap,
            "employees": data.employees,
            "data_sources": data.data_sources,
            "news_count": len(data.recent_news),
            "financial_keys": sorted(data.financial.keys()),
            "environmental_keys": sorted(key for key, value in data.environmental.items() if value not in (None, [], {})),
            "social_keys": sorted(key for key, value in data.social.items() if value not in (None, [], {})),
            "governance_keys": sorted(key for key, value in data.governance.items() if value not in (None, [], {})),
            "external_rating_keys": sorted(key for key, value in data.external_ratings.items() if value not in (None, [], {})),
        })

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
