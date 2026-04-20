from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from gateway.db.supabase_client import latest_table_row, list_table_rows, save_table_row, update_table_row
from gateway.quant.storage import QuantStorageGateway
from gateway.trading.models import (
    DailyReviewReport,
    DebateReport,
    PriceAlertRecord,
    RiskApproval,
    TradingJobRun,
    WatchlistItem,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TradingStore:
    DEFAULT_WATCHLIST = ("AAPL", "NVDA", "TSLA", "SPY")

    def __init__(self, get_client: Callable[[], Any] | None = None) -> None:
        self._get_client = get_client
        self.storage = QuantStorageGateway(get_client=get_client)

    def list_watchlist(self, *, enabled_only: bool = True) -> list[dict[str, Any]]:
        rows = list_table_rows(
            "watchlist",
            limit=50,
            order_by="added_date",
            desc=False,
            filters={"enabled": True} if enabled_only else None,
        )
        if rows:
            return rows
        seeded = [
            self.save_watchlist_item(
                WatchlistItem(
                    watchlist_id=str(uuid.uuid4()),
                    symbol=symbol,
                    added_date=utc_now(),
                    esg_score=None,
                    last_sentiment=None,
                    enabled=True,
                    note="default_watchlist_seed",
                )
            )
            for symbol in self.DEFAULT_WATCHLIST
        ]
        return seeded

    def save_watchlist_item(self, item: WatchlistItem) -> dict[str, Any]:
        payload = item.model_dump()
        payload["storage"] = self.storage.persist_record("watchlist", item.watchlist_id, payload)
        save_table_row("watchlist", payload)
        return payload

    def add_watchlist_symbol(
        self,
        *,
        symbol: str,
        esg_score: float | None = None,
        last_sentiment: float | None = None,
        note: str = "",
        enabled: bool = True,
    ) -> dict[str, Any]:
        normalized = str(symbol or "").upper().strip()
        existing = list_table_rows("watchlist", limit=20, filters={"symbol": normalized})
        if existing:
            row = dict(existing[0])
            row.update(
                {
                    "enabled": enabled,
                    "esg_score": esg_score if esg_score is not None else row.get("esg_score"),
                    "last_sentiment": last_sentiment if last_sentiment is not None else row.get("last_sentiment"),
                    "note": note or row.get("note", ""),
                    "updated_at": utc_now(),
                }
            )
            update_table_row("watchlist", row, match={"watchlist_id": row["watchlist_id"]})
            return row
        item = WatchlistItem(
            watchlist_id=str(uuid.uuid4()),
            symbol=normalized,
            added_date=utc_now(),
            esg_score=esg_score,
            last_sentiment=last_sentiment,
            enabled=enabled,
            note=note,
        )
        return self.save_watchlist_item(item)

    def save_price_alert(self, alert: PriceAlertRecord) -> dict[str, Any]:
        payload = alert.model_dump()
        payload["storage"] = self.storage.persist_record("price_alerts", alert.alert_id, payload)
        save_table_row("price_alerts", payload)
        return payload

    def list_alerts(self, *, limit: int = 50) -> list[dict[str, Any]]:
        return list_table_rows("price_alerts", limit=limit, order_by="timestamp", desc=True)

    def alerts_today(self, *, limit: int = 50) -> list[dict[str, Any]]:
        today = datetime.now(timezone.utc).date().isoformat()
        rows = self.list_alerts(limit=limit * 2)
        return [row for row in rows if str(row.get("timestamp", "")).startswith(today)][:limit]

    def save_debate_run(self, report: DebateReport) -> dict[str, Any]:
        payload = report.model_dump()
        payload["storage"] = self.storage.persist_record("debate_runs", report.debate_id, payload)
        save_table_row("debate_runs", payload)
        return payload

    def list_debate_runs(self, *, limit: int = 20, symbol: str | None = None) -> list[dict[str, Any]]:
        filters = {"symbol": str(symbol).upper()} if symbol else None
        return list_table_rows("debate_runs", limit=limit, order_by="generated_at", desc=True, filters=filters)

    def save_risk_approval(self, approval: RiskApproval) -> dict[str, Any]:
        payload = approval.model_dump()
        payload["storage"] = self.storage.persist_record("risk_approvals", approval.approval_id, payload)
        save_table_row("risk_approvals", payload)
        return payload

    def list_risk_approvals(self, *, limit: int = 20, symbol: str | None = None) -> list[dict[str, Any]]:
        filters = {"symbol": str(symbol).upper()} if symbol else None
        return list_table_rows("risk_approvals", limit=limit, order_by="generated_at", desc=True, filters=filters)

    def save_daily_review(self, review: DailyReviewReport) -> dict[str, Any]:
        payload = review.model_dump()
        payload["storage"] = self.storage.persist_record("daily_reviews", review.review_id, payload)
        save_table_row("daily_reviews", payload)
        return payload

    def latest_daily_review(self) -> dict[str, Any] | None:
        return latest_table_row("daily_reviews", order_by="generated_at")

    def save_job_run(self, run: TradingJobRun) -> dict[str, Any]:
        payload = run.model_dump()
        payload["storage"] = self.storage.persist_record("scheduler_job_runs", run.run_id, payload)
        save_table_row("scheduler_job_runs", payload)
        return payload

    def list_job_runs(self, *, limit: int = 20, job_name: str | None = None) -> list[dict[str, Any]]:
        filters = {"job_name": job_name} if job_name else None
        return list_table_rows("scheduler_job_runs", limit=limit, order_by="started_at", desc=True, filters=filters)
