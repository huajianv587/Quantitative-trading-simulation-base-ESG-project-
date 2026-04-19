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

from gateway.connectors.free_live import FreeLiveConnectorRegistry


def _providers(raw: str, all_configured: bool, registry: FreeLiveConnectorRegistry) -> list[str] | None:
    if raw:
        return [item.strip() for item in raw.split(",") if item.strip()]
    if all_configured:
        return registry.provider_ids(configured_only=True)
    return None


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    parser = argparse.ArgumentParser(description="Free-tier live connector doctor.")
    parser.add_argument("--providers", default="", help="Comma-separated provider IDs.")
    parser.add_argument("--all-configured", action="store_true", help="Test only configured providers.")
    parser.add_argument("--free-tier", action="store_true", help="Annotate the report as free-tier guarded.")
    parser.add_argument("--symbol", default="AAPL")
    parser.add_argument("--dry-run", action="store_true", help="Do not call external providers.")
    parser.add_argument("--no-quota-guard", action="store_true", help="Disable quota reservation for live calls.")
    parser.add_argument("--write-report", default="")
    args = parser.parse_args()

    registry = FreeLiveConnectorRegistry()
    providers = _providers(args.providers, args.all_configured, registry)
    report = {
        "free_tier": bool(args.free_tier),
        "registry": registry.registry(),
        "health": registry.health(providers=providers, live=False),
        "quota": registry.quota_status(providers=providers),
        "sample": registry.test(
            providers=providers,
            symbol=args.symbol,
            dry_run=bool(args.dry_run),
            quota_guard=not args.no_quota_guard,
        ),
    }

    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.write_report:
        path = Path(args.write_report)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    print(text)

    failed = report["sample"]["summary"].get("failed_count", 0)
    return 1 if failed and not args.dry_run else 0


if __name__ == "__main__":
    raise SystemExit(main())
