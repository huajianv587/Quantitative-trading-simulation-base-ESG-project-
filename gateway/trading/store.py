from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from gateway.db.supabase_client import latest_table_row, list_table_rows, save_table_row, update_table_row
from gateway.quant.storage import QuantStorageGateway
from gateway.trading.models import (
    AutopilotPolicy,
    DailyReviewReport,
    DebateReport,
    ExecutionPathStatus,
    FusionReferenceManifest,
    OrderApprovalLedger,
    PaperRewardCandidate,
    PriceAlertRecord,
    RiskApproval,
    StrategyAllocation,
    StrategyTemplate,
    TradingJobRun,
    WatchlistItem,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TradingStore:
    DEFAULT_WATCHLIST = ("AAPL", "NVDA", "TSLA", "SPY")
    DEFAULT_AUTOPILOT_PROTECTIONS = (
        "judge_gate",
        "risk_gate",
        "daily_budget",
        "kill_switch",
        "duplicate_order_guard",
        "stale_signal_guard",
        "drawdown_guard",
        "notifier_guard",
    )
    DEFAULT_STRATEGIES = (
        {
            "strategy_id": "esg_multifactor_long_only",
            "display_name": "ESG Multi-Factor Long Only",
            "risk_profile": "balanced",
            "capital_allocation": 0.34,
            "required_frequency": "daily",
            "required_data_tier": "l1",
            "factor_dependencies": ["quality", "value", "momentum", "esg_delta"],
            "allowed_symbols": ["AAPL", "MSFT", "NVDA", "NEE", "TSLA"],
            "description": "Core long-only basket using ESG-enhanced factor ranking and gated execution slots.",
        },
        {
            "strategy_id": "event_driven_overlay",
            "display_name": "Event-Driven Overlay",
            "risk_profile": "aggressive",
            "capital_allocation": 0.14,
            "required_frequency": "intraday",
            "required_data_tier": "l2",
            "factor_dependencies": ["event_pressure", "evidence_strength", "news_sentiment_score"],
            "allowed_symbols": ["AAPL", "NVDA", "TSLA", "SPY"],
            "description": "Opportunistic event and evidence overlay with tighter risk gating.",
        },
        {
            "strategy_id": "regime_rotation",
            "display_name": "Regime Rotation",
            "risk_profile": "balanced",
            "capital_allocation": 0.2,
            "required_frequency": "daily",
            "required_data_tier": "l1",
            "factor_dependencies": ["macro_regime", "regime_fit", "volatility"],
            "allowed_symbols": ["SPY", "QQQ", "XLE", "XLK", "XLV"],
            "description": "Allocate by macro regime and sector risk appetite.",
        },
        {
            "strategy_id": "rl_timing_overlay",
            "display_name": "RL Timing Overlay",
            "risk_profile": "balanced",
            "capital_allocation": 0.18,
            "required_frequency": "intraday",
            "required_data_tier": "l2",
            "factor_dependencies": ["rl_policy", "drawdown_guard", "execution_confidence"],
            "allowed_symbols": ["AAPL", "NVDA", "TSLA", "SPY"],
            "description": "RL timing policy layered on top of factor conviction and runtime execution guardrails.",
        },
        {
            "strategy_id": "sentiment_overlay",
            "display_name": "Sentiment Overlay",
            "risk_profile": "conservative",
            "capital_allocation": 0.14,
            "required_frequency": "hybrid",
            "required_data_tier": "l1",
            "factor_dependencies": ["news_sentiment_score", "headline_freshness", "evidence_strength"],
            "allowed_symbols": ["AAPL", "MSFT", "NVDA", "GOOGL", "TSLA"],
            "description": "Free-tier sentiment signal blended into the execution queue.",
        },
    )

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

    def get_autopilot_policy(self) -> dict[str, Any]:
        latest = latest_table_row("autopilot_policies", order_by="generated_at")
        if latest:
            return latest
        seeded = AutopilotPolicy(
            policy_id="autopilot-default",
            generated_at=utc_now(),
            execution_mode="paper",
            execution_permission="auto_submit",
            auto_submit_enabled=False,
            paper_auto_submit_enabled=False,
            armed=False,
            daily_budget_cap=10_000.0,
            per_trade_cap=2_500.0,
            max_open_positions=5,
            max_symbol_weight=0.2,
            allowed_universe=list(self.DEFAULT_WATCHLIST),
            allowed_strategies=[item["strategy_id"] for item in self.DEFAULT_STRATEGIES[:3]],
            require_human_review_above=7_500.0,
            drawdown_limit=0.06,
            daily_loss_limit=1_500.0,
            signal_ttl=180,
            kill_switch=False,
            protections=list(self.DEFAULT_AUTOPILOT_PROTECTIONS),
            warnings=[],
            metadata={"mode": "multi_mode_control_plane"},
        )
        return self.save_autopilot_policy(seeded)

    def save_autopilot_policy(self, policy: AutopilotPolicy) -> dict[str, Any]:
        payload = policy.model_dump()
        payload["storage"] = self.storage.persist_record("autopilot_policies", policy.policy_id, payload)
        existing = latest_table_row("autopilot_policies", order_by="generated_at")
        if existing and existing.get("policy_id") == policy.policy_id:
            update_table_row("autopilot_policies", payload, match={"policy_id": policy.policy_id})
        else:
            save_table_row("autopilot_policies", payload)
        return payload

    def list_strategies(self) -> list[dict[str, Any]]:
        rows = list_table_rows("strategy_registry", limit=50, order_by="updated_at", desc=False)
        if rows:
            return rows
        seeded = []
        now = utc_now()
        for raw in self.DEFAULT_STRATEGIES:
            strategy = StrategyTemplate(
                strategy_id=raw["strategy_id"],
                display_name=raw["display_name"],
                status="active",
                factor_dependencies=list(raw["factor_dependencies"]),
                required_frequency=raw.get("required_frequency", "daily"),
                required_data_tier=raw.get("required_data_tier", "l1"),
                risk_profile=raw["risk_profile"],
                capital_allocation=raw["capital_allocation"],
                allowed_symbols=list(raw["allowed_symbols"]),
                paper_ready=True,
                requires_debate=True,
                requires_risk_approval=True,
                description=raw["description"],
                lineage=["qlib_factor_pipeline", "finrl_policy_overlay", "execution_registry"],
                metadata={"origin": "seed"},
                updated_at=now,
            )
            seeded.append(self.save_strategy(strategy))
        return seeded

    def save_strategy(self, strategy: StrategyTemplate) -> dict[str, Any]:
        payload = strategy.model_dump()
        payload["storage"] = self.storage.persist_record("strategy_registry", strategy.strategy_id, payload)
        existing = list_table_rows("strategy_registry", limit=1, filters={"strategy_id": strategy.strategy_id})
        if existing:
            update_table_row("strategy_registry", payload, match={"strategy_id": strategy.strategy_id})
        else:
            save_table_row("strategy_registry", payload)
        return payload

    def save_strategy_allocation(self, allocation: StrategyAllocation) -> dict[str, Any]:
        payload = allocation.model_dump()
        payload["storage"] = self.storage.persist_record("strategy_allocations", allocation.allocation_id, payload)
        existing = list_table_rows("strategy_allocations", limit=1, filters={"strategy_id": allocation.strategy_id})
        if existing:
            update_table_row("strategy_allocations", payload, match={"strategy_id": allocation.strategy_id})
        else:
            save_table_row("strategy_allocations", payload)
        return payload

    def list_strategy_allocations(self) -> list[dict[str, Any]]:
        return list_table_rows("strategy_allocations", limit=50, order_by="updated_at", desc=False)

    def save_execution_path_status(self, status: ExecutionPathStatus) -> dict[str, Any]:
        payload = status.model_dump()
        payload["storage"] = self.storage.persist_record("execution_path_status", "current", payload)
        existing = latest_table_row("execution_path_status", order_by="generated_at")
        if existing:
            update_table_row("execution_path_status", payload, match={"generated_at": existing.get("generated_at")})
        else:
            save_table_row("execution_path_status", payload)
        return payload

    def latest_execution_path_status(self) -> dict[str, Any] | None:
        return latest_table_row("execution_path_status", order_by="generated_at")

    def save_order_approval_ledger(self, ledger: OrderApprovalLedger) -> dict[str, Any]:
        payload = ledger.model_dump()
        payload["storage"] = self.storage.persist_record("order_approval_ledgers", ledger.ledger_id, payload)
        save_table_row("order_approval_ledgers", payload)
        return payload

    def list_order_approval_ledgers(self, *, limit: int = 20, symbol: str | None = None) -> list[dict[str, Any]]:
        filters = {"symbol": str(symbol).upper()} if symbol else None
        return list_table_rows("order_approval_ledgers", limit=limit, order_by="generated_at", desc=True, filters=filters)

    def save_paper_reward_candidate(self, candidate: PaperRewardCandidate) -> dict[str, Any]:
        payload = candidate.model_dump(mode="json")
        payload["storage"] = self.storage.persist_record("paper_reward_candidates", candidate.candidate_id, payload)
        updated = update_table_row("paper_reward_candidates", payload, match={"candidate_id": candidate.candidate_id})
        if not updated:
            save_table_row("paper_reward_candidates", payload)
        return payload

    def get_paper_reward_candidate(self, candidate_id: str) -> dict[str, Any] | None:
        local = self.storage.load_record("paper_reward_candidates", candidate_id)
        if local:
            return local
        rows = list_table_rows(
            "paper_reward_candidates",
            limit=1,
            order_by="created_at",
            desc=True,
            filters={"candidate_id": candidate_id},
        )
        return rows[0] if rows else None

    def list_paper_reward_candidates(
        self,
        *,
        limit: int = 200,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        rows = self.storage.list_records("paper_reward_candidates")
        if not rows:
            rows = list_table_rows("paper_reward_candidates", limit=limit, order_by="created_at", desc=True)
        if status:
            rows = [row for row in rows if str(row.get("status") or "") == status]
        rows.sort(key=lambda item: str(item.get("created_at") or item.get("generated_at") or ""), reverse=True)
        return rows[: max(1, int(limit))]

    def save_paper_reward_bandit_state(self, payload: dict[str, Any]) -> dict[str, Any]:
        payload = dict(payload or {})
        payload["state_id"] = "state"
        payload["storage"] = self.storage.persist_record("paper_reward_bandit", "state", payload)
        updated = update_table_row("paper_reward_bandit", payload, match={"state_id": "state"})
        if not updated:
            save_table_row("paper_reward_bandit", payload)
        return payload

    def get_paper_reward_bandit_state(self) -> dict[str, Any] | None:
        local = self.storage.load_record("paper_reward_bandit", "state")
        if local:
            return local
        rows = list_table_rows("paper_reward_bandit", limit=1, order_by="updated_at", desc=True, filters={"state_id": "state"})
        return rows[0] if rows else None

    def get_fusion_manifest(self) -> dict[str, Any]:
        latest = latest_table_row("fusion_reference_manifest", order_by="generated_at")
        if latest:
            return latest
        manifest = FusionReferenceManifest(
            manifest_id="fusion-reference-default",
            generated_at=utc_now(),
            items=[
                {"source_project": "Lean", "capability": "order lifecycle and approval ledger", "target_surface": "Trading Ops / execution runtime", "status": "implemented", "notes": "Execution chain tracks intent -> approval -> submit."},
                {"source_project": "Qlib", "capability": "factor pipeline manifest", "target_surface": "Factor Lab / Strategy Registry", "status": "implemented", "notes": "Registry templates now declare factor dependencies and allocations."},
                {"source_project": "FinRL", "capability": "RL strategy template overlay", "target_surface": "Strategy Registry / Decision Cockpit", "status": "staged", "notes": "RL timing overlay is registered as a runtime-ready strategy with a visible control-plane contract."},
                {"source_project": "vectorbt", "capability": "parameter sweep and scenario matrix", "target_surface": "Backtest", "status": "staged", "notes": "Backtest now exposes a sweep summary without adding an external runtime dependency."},
                {"source_project": "freqtrade", "capability": "bot protections and notifier controls", "target_surface": "Trading Ops / Autopilot Policy", "status": "staged", "notes": "Protections, notifier mode, and lifecycle status are visible from the execution control plane."},
            ],
            lineage=["fusion_reference_manifest", "high_star_capability_migration", "execution_control_plane"],
        )
        return self.save_fusion_manifest(manifest)

    def save_fusion_manifest(self, manifest: FusionReferenceManifest) -> dict[str, Any]:
        payload = manifest.model_dump()
        payload["storage"] = self.storage.persist_record("fusion_reference_manifest", manifest.manifest_id, payload)
        existing = latest_table_row("fusion_reference_manifest", order_by="generated_at")
        if existing and existing.get("manifest_id") == manifest.manifest_id:
            update_table_row("fusion_reference_manifest", payload, match={"manifest_id": manifest.manifest_id})
        else:
            save_table_row("fusion_reference_manifest", payload)
        return payload
