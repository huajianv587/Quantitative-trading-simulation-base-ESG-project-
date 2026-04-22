from __future__ import annotations

import asyncio
import uuid
from datetime import date, datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from gateway.connectors.free_live import FreeLiveConnectorRegistry
from gateway.config import settings
from gateway.quant.intelligence import QuantIntelligenceService
from gateway.quant.intelligence_models import FactorCard, InformationItem
from gateway.quant.service import QuantSystemService
from gateway.trading.models import (
    AutopilotPolicy,
    DailyReviewReport,
    DebateReport,
    DebateTurn,
    ExecutionIntent,
    ExecutionPathStatus,
    ExecutionResult,
    FactorPipelineManifest,
    FactorPipelineStage,
    FusionReferenceManifest,
    OrderApprovalLedger,
    PriceAlertRecord,
    RiskApproval,
    SentimentSnapshot,
    StrategyAllocation,
    StrategyTemplate,
    TradingAction,
    TradingDecisionBundle,
    TradingJobRun,
)
from gateway.trading.monitor import AlpacaMarketMonitor
from gateway.trading.scheduler import TradingScheduler
from gateway.trading.sentiment import SentimentAgent
from gateway.trading.store import TradingStore
from gateway.utils.logger import get_logger

logger = get_logger(__name__)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _normalize_execution_mode(value: Any) -> str:
    normalized = str(value or "paper").strip().lower()
    return "live" if normalized == "live" else "paper"


def _normalize_execution_permission(value: Any) -> str:
    normalized = str(value or "auto_submit").strip().lower()
    if normalized == "paper_auto_submit":
        return "auto_submit"
    if normalized in {"research", "manual_review", "auto_submit"}:
        return normalized
    return "manual_review"


class TradingAgentService:
    DEFAULT_WATCHLIST = ["AAPL", "NVDA", "TSLA", "SPY"]

    def __init__(self, quant_system: QuantSystemService, get_client: Any | None = None) -> None:
        self.quant_system = quant_system
        self.intelligence = QuantIntelligenceService(quant_system)
        self.connectors = FreeLiveConnectorRegistry()
        self.store = TradingStore(get_client=get_client)
        self.sentiment_agent = SentimentAgent(self.connectors)
        self.monitor = AlpacaMarketMonitor(
            on_trigger=self._handle_monitor_trigger,
            watchlist_supplier=self._active_watchlist_symbols,
        )
        self.scheduler = TradingScheduler(self.run_scheduled_job)
        self._started = False

    async def startup(self) -> None:
        if self._started:
            return
        self.scheduler.start()
        self._started = True

    async def shutdown(self) -> None:
        await self.monitor.stop()
        await self.scheduler.shutdown()
        self._started = False

    def schedule_status(self) -> dict[str, Any]:
        payload = self.scheduler.status()
        payload["recent_runs"] = self.store.list_job_runs(limit=10)
        return payload

    def monitor_status(self) -> dict[str, Any]:
        return self.monitor.status().model_dump(mode="json")

    @staticmethod
    def _policy_auto_submit_enabled(policy: dict[str, Any]) -> bool:
        return bool(policy.get("auto_submit_enabled") or policy.get("paper_auto_submit_enabled"))

    def _normalize_autopilot_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(payload or {})
        execution_mode = _normalize_execution_mode(normalized.get("execution_mode") or normalized.get("mode"))
        execution_permission = _normalize_execution_permission(normalized.get("execution_permission"))
        auto_submit_enabled = bool(
            normalized.get("auto_submit_enabled")
            if "auto_submit_enabled" in normalized
            else normalized.get("paper_auto_submit_enabled")
        )
        normalized["execution_mode"] = execution_mode
        normalized["execution_permission"] = execution_permission
        normalized["auto_submit_enabled"] = auto_submit_enabled
        normalized["paper_auto_submit_enabled"] = auto_submit_enabled
        metadata = dict(normalized.get("metadata") or {})
        metadata.setdefault("mode", execution_mode)
        normalized["metadata"] = metadata
        return normalized

    def debate_runs(self, *, symbol: str | None = None, limit: int = 20) -> dict[str, Any]:
        rows = self.store.list_debate_runs(limit=limit, symbol=symbol)
        return {
            "generated_at": utc_now(),
            "count": len(rows),
            "debates": rows,
        }

    def risk_board(self, *, symbol: str | None = None, limit: int = 20) -> dict[str, Any]:
        approvals = self.store.list_risk_approvals(limit=limit, symbol=symbol)
        latest = approvals[0] if approvals else None
        controls = self.quant_system.get_execution_controls()
        alerts = self.store.alerts_today(limit=20)
        return {
            "generated_at": utc_now(),
            "controls": controls,
            "approvals": approvals,
            "latest_approval": latest,
            "alerts": alerts,
            "kill_switch_enabled": bool(controls.get("kill_switch_enabled")),
            "lineage": [
                "judge_agent",
                "risk_manager_agent",
                "broker account and position checks",
                "execution auto-submit gate",
            ],
        }

    def trading_ops_snapshot(self) -> dict[str, Any]:
        return {
            "generated_at": utc_now(),
            "schedule": self.schedule_status(),
            "monitor": self.monitor_status(),
            "watchlist": self.list_watchlist(),
            "today_alerts": self.alerts_today(),
            "latest_review": self.latest_review(),
            "debates": self.debate_runs(limit=10),
            "risk": self.risk_board(limit=10),
            "autopilot_policy": self.get_autopilot_policy(),
            "strategies": self.list_strategies(),
            "execution_path": self.execution_path_status(),
            "factor_pipeline": self.factor_pipeline_manifest(),
            "fusion_manifest": self.fusion_reference_manifest(),
            "notifier": {
                "telegram_configured": bool(
                    getattr(settings, "TELEGRAM_BOT_TOKEN", "") and getattr(settings, "TELEGRAM_CHAT_ID", "")
                ),
                "mode": "shadow_notify",
            },
        }

    def get_autopilot_policy(self) -> dict[str, Any]:
        return self._normalize_autopilot_payload(self.store.get_autopilot_policy())

    def save_autopilot_policy(self, payload: dict[str, Any]) -> dict[str, Any]:
        current = self.get_autopilot_policy()
        merged = self._normalize_autopilot_payload({**current, **payload})
        policy = AutopilotPolicy.model_validate(
            {
                **merged,
                "policy_id": current.get("policy_id") or "autopilot-default",
                "generated_at": utc_now(),
                "warnings": self._autopilot_warnings(merged),
                "metadata": {
                    **dict(current.get("metadata") or {}),
                    "mode": merged.get("execution_mode", "paper"),
                    "saved_via": "api",
                },
            }
        )
        return self.store.save_autopilot_policy(policy)

    def arm_autopilot(self, *, armed: bool) -> dict[str, Any]:
        current = self.get_autopilot_policy()
        current["armed"] = bool(armed)
        current["generated_at"] = utc_now()
        current["warnings"] = self._autopilot_warnings(current)
        saved = self.store.save_autopilot_policy(AutopilotPolicy.model_validate(self._normalize_autopilot_payload(current)))
        path = self._build_execution_path_status(
            policy=saved,
            current_stage="armed" if armed else "disarmed",
            judge_passed=False,
            risk_passed=False,
        )
        self.store.save_execution_path_status(path)
        return saved

    def list_strategies(self) -> dict[str, Any]:
        rows = self.store.list_strategies()
        allocations = {row["strategy_id"]: row for row in self.store.list_strategy_allocations()}
        enriched = []
        for row in rows:
            item = dict(row)
            allocation = allocations.get(item["strategy_id"])
            item["allocation"] = allocation
            enriched.append(item)
        return {
            "generated_at": utc_now(),
            "count": len(enriched),
            "strategies": enriched,
        }

    def toggle_strategy(self, *, strategy_id: str, status: str) -> dict[str, Any]:
        rows = self.store.list_strategies()
        current = next((row for row in rows if row.get("strategy_id") == strategy_id), None)
        if not current:
            raise ValueError(f"Unknown strategy: {strategy_id}")
        updated = StrategyTemplate.model_validate(
            {
                **current,
                "status": status,
                "updated_at": utc_now(),
            }
        )
        saved = self.store.save_strategy(updated)
        return {"generated_at": utc_now(), "strategy": saved}

    def allocate_strategy(self, *, strategy_id: str, capital_allocation: float, max_symbols: int, status: str) -> dict[str, Any]:
        allocation = StrategyAllocation(
            allocation_id=f"alloc-{strategy_id}",
            strategy_id=strategy_id,
            capital_allocation=capital_allocation,
            max_symbols=max_symbols,
            status=status if status in {"active", "paused"} else "active",
            updated_at=utc_now(),
            metadata={"source": "api"},
        )
        saved = self.store.save_strategy_allocation(allocation)
        return {"generated_at": utc_now(), "allocation": saved}

    def execution_path_status(self) -> dict[str, Any]:
        latest = self.store.latest_execution_path_status()
        if latest:
            return latest
        seeded = self._build_execution_path_status(
            policy=self.store.get_autopilot_policy(),
            current_stage="idle",
            judge_passed=False,
            risk_passed=False,
        )
        return self.store.save_execution_path_status(seeded)

    def dashboard_state(self, *, provider: str = "auto") -> dict[str, Any]:
        signal = None
        try:
            signal = self.quant_system.build_dashboard_chart(provider=provider)
        except Exception:
            signal = {}
        chart = signal if isinstance(signal, dict) else {}
        source = chart.get("source")
        provider_status = chart.get("provider_status") or {}
        degraded_from = chart.get("degraded_from")
        provider_chain = chart.get("data_source_chain") or chart.get("provider_chain") or []
        candles = chart.get("candles") or []
        symbol = chart.get("symbol") or (self._active_watchlist_symbols()[0] if self._active_watchlist_symbols() else None)
        phase = "ready" if candles and source not in {"unknown", "loading", None, ""} else "degraded"
        reason = chart.get("warning") or chart.get("detail") or chart.get("market_data_warnings") or []
        if isinstance(reason, str):
            reason = [reason]
        if not reason:
            if provider_status.get("available") and not candles:
                reason = ["provider_connected_but_no_payload"]
            elif degraded_from:
                reason = [f"provider_degraded_from_{degraded_from}"]
            else:
                reason = ["chart_data_unavailable"]
        fallback_preview = {
            "symbol": symbol,
            "source": source or "unknown",
            "source_chain": provider_chain or ["alpaca", "twelvedata", "yfinance", "cache", "synthetic"],
            "last_snapshot": candles[-1] if candles else None,
            "reason": reason or ["chart_data_unavailable"],
            "next_actions": ["refresh_dashboard", "switch_symbol", "open_market_radar", "open_backtest"],
        }
        return {
            "generated_at": utc_now(),
            "phase": phase,
            "ready": phase == "ready",
            "symbol": symbol,
            "source": source or "unknown",
            "selected_provider": provider,
            "source_chain": provider_chain or ["alpaca", "twelvedata", "yfinance", "cache", "synthetic"],
            "provider_status": provider_status,
            "degraded_from": degraded_from,
            "fallback_preview": fallback_preview,
        }

    def fusion_reference_manifest(self) -> dict[str, Any]:
        manifest = dict(self.store.get_fusion_manifest())
        manifest["execution_intent_contract"] = self._sample_execution_intent().model_dump(mode="json")
        manifest["execution_result_contract"] = self._sample_execution_result().model_dump(mode="json")
        manifest["factor_pipeline_manifest"] = self.factor_pipeline_manifest()
        return manifest

    def factor_pipeline_manifest(
        self,
        *,
        symbol: str | None = None,
        strategy_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        strategy_snapshot = self.list_strategies()
        strategy_rows = strategy_snapshot.get("strategies", [])
        strategy_lookup = {row.get("strategy_id"): row for row in strategy_rows}
        selected_rows = []
        if strategy_ids:
            selected_rows = [strategy_lookup[strategy_id] for strategy_id in strategy_ids if strategy_id in strategy_lookup]
        if not selected_rows:
            selected_rows = [
                row for row in strategy_rows
                if str(row.get("status") or "").lower() == "active"
                and (not row.get("allocation") or str((row.get("allocation") or {}).get("status") or "active").lower() == "active")
            ]
        factor_dependencies = list(dict.fromkeys(
            dependency
            for row in selected_rows
            for dependency in row.get("factor_dependencies") or []
            if str(dependency or "").strip()
        ))
        warnings: list[str] = []
        if not selected_rows:
            warnings.append("no_strategy_slot")
        if not factor_dependencies:
            warnings.append("no_factor_dependencies")
        stages = [
            FactorPipelineStage(
                stage="feature_build",
                status="ready",
                detail="Build as-of-safe feature inputs from free-tier evidence and market data connectors.",
                factors=factor_dependencies[:6],
            ),
            FactorPipelineStage(
                stage="factor_gate",
                status="ready" if factor_dependencies else "pending",
                detail="Promote only gated factors with clear lineage, IC evidence, and leakage checks.",
                factors=factor_dependencies[:6],
            ),
            FactorPipelineStage(
                stage="strategy_slot",
                status="ready" if selected_rows else "guarded",
                detail="Route promoted factors into active strategy slots before execution.",
                factors=[row.get("strategy_id") for row in selected_rows if row.get("strategy_id")],
            ),
        ]
        next_action = (
            "Choose an active strategy slot or expand the factor allowlist before execution."
            if warnings
            else "Compare factor-gate output with strategy allocations, then move to Debate and Risk."
        )
        manifest = FactorPipelineManifest(
            manifest_id="factor-pipeline-current",
            generated_at=utc_now(),
            symbol=(symbol or (self._active_watchlist_symbols()[0] if self._active_watchlist_symbols() else None)),
            strategy_slots=[row.get("strategy_id") for row in selected_rows if row.get("strategy_id")],
            factor_dependencies=factor_dependencies,
            stages=stages,
            warnings=warnings,
            next_action=next_action,
            lineage=["qlib_factor_pipeline", "factor_gate", "strategy_slot", "execution_control_plane"],
        )
        return manifest.model_dump(mode="json")

    def list_watchlist(self) -> dict[str, Any]:
        rows = self.store.list_watchlist(enabled_only=True)
        return {
            "generated_at": utc_now(),
            "watchlist": rows,
            "count": len(rows),
            "mode": "auto_submit",
        }

    def add_watchlist_symbol(
        self,
        *,
        symbol: str,
        esg_score: float | None = None,
        last_sentiment: float | None = None,
        note: str = "",
        enabled: bool = True,
    ) -> dict[str, Any]:
        row = self.store.add_watchlist_symbol(
            symbol=symbol,
            esg_score=esg_score,
            last_sentiment=last_sentiment,
            note=note,
            enabled=enabled,
        )
        return {
            "generated_at": utc_now(),
            "watchlist_item": row,
            "watchlist": self.store.list_watchlist(enabled_only=True),
        }

    def latest_review(self) -> dict[str, Any]:
        latest = self.store.latest_daily_review()
        return {
            "generated_at": utc_now(),
            "degraded": latest is None,
            "review": latest,
        }

    def alerts_today(self) -> dict[str, Any]:
        rows = self.store.alerts_today(limit=50)
        return {
            "generated_at": utc_now(),
            "alert_count": len(rows),
            "alerts": rows,
        }

    def run_sentiment(
        self,
        *,
        universe: list[str] | None = None,
        providers: list[str] | None = None,
        quota_guard: bool = True,
    ) -> dict[str, Any]:
        symbols = universe or self._active_watchlist_symbols()
        snapshot = self.sentiment_agent.run(
            universe=symbols,
            providers=providers,
            quota_guard=quota_guard,
        )
        payload = snapshot.model_dump(mode="json")
        payload["storage"] = self.store.storage.persist_record("trading_sentiment", snapshot.snapshot_id, payload)
        return payload

    def run_debate(
        self,
        *,
        symbol: str,
        universe: list[str] | None = None,
        query: str = "",
        mode: str = "mixed",
        providers: list[str] | None = None,
        quota_guard: bool = True,
        rebuttal_rounds: int = 2,
    ) -> dict[str, Any]:
        bundle = self._prepare_inputs(
            symbol=symbol,
            universe=universe,
            query=query,
            mode=mode,
            providers=providers,
            quota_guard=quota_guard,
        )
        debate = self._build_debate_report(
            symbol=symbol,
            universe=bundle["universe"],
            evidence_items=bundle["evidence"].get("items", []),
            factor_cards=bundle["factors"].get("factor_cards", []),
            sentiment_snapshot=SentimentSnapshot.model_validate(bundle["sentiment"]),
            signal=bundle["signal"],
            rebuttal_rounds=rebuttal_rounds,
            evidence_run_id=bundle["evidence"].get("bundle_id"),
        )
        payload = self.store.save_debate_run(debate)
        payload["evidence_run_id"] = bundle["evidence"].get("bundle_id")
        return payload

    def evaluate_risk(
        self,
        *,
        symbol: str,
        debate_payload: dict[str, Any] | None = None,
        signal_ttl_minutes: int = 180,
    ) -> dict[str, Any]:
        debate_source = debate_payload
        if debate_source is None:
            latest = self.store.list_debate_runs(limit=1, symbol=symbol)
            debate_source = latest[0] if latest else None
        if not debate_source:
            raise ValueError(f"No debate run available for {symbol}")
        debate = DebateReport.model_validate(debate_source)
        approval = self._build_risk_approval(symbol=symbol, debate=debate, signal_ttl_minutes=signal_ttl_minutes)
        return self.store.save_risk_approval(approval)

    async def start_intraday_monitor(self) -> dict[str, Any]:
        status = await self.monitor.start()
        return status.model_dump(mode="json")

    async def stop_intraday_monitor(self) -> dict[str, Any]:
        status = await self.monitor.stop()
        return status.model_dump(mode="json")

    async def run_scheduled_job(self, job_name: str, scheduled_for: str | None) -> dict[str, Any]:
        run = TradingJobRun(
            run_id=f"job-{job_name}-{uuid.uuid4().hex[:10]}",
            job_name=job_name,
            scheduled_for=scheduled_for or utc_now(),
            started_at=utc_now(),
            status="running",
        )
        if not self._is_market_day():
            run.status = "skipped"
            run.market_day = False
            run.completed_at = utc_now()
            run.result_ref = {"reason": "not_us_market_day"}
            return self.store.save_job_run(run)

        try:
            if job_name == "premarket_agent":
                result = self.run_premarket_agent()
            elif job_name == "midday_summary_agent":
                result = self.run_midday_summary_agent()
            elif job_name == "review_agent":
                result = self.run_review_agent()
            elif job_name == "intraday_monitor_start":
                result = await self.start_intraday_monitor()
            elif job_name == "intraday_monitor_stop":
                result = await self.stop_intraday_monitor()
            else:
                raise ValueError(f"Unknown trading job: {job_name}")
            run.status = "completed"
            run.completed_at = utc_now()
            run.auto_submit_triggered = bool(result.get("auto_submit_triggered") or result.get("submitted"))
            run.result_ref = {
                "result_kind": job_name,
                "record_id": result.get("review", {}).get("review_id")
                or result.get("briefing_id")
                or result.get("monitor_run_id")
                or result.get("run_id"),
            }
        except Exception as exc:
            logger.warning(f"[TradingScheduler] {job_name} failed: {exc}")
            run.status = "failed"
            run.completed_at = utc_now()
            run.error = str(exc)
        return self.store.save_job_run(run)

    def run_premarket_agent(self) -> dict[str, Any]:
        watchlist = self._active_watchlist_symbols()
        sentiment = self.run_sentiment(universe=watchlist, providers=["marketaux", "thenewsapi"])
        evidence = self.intelligence.scan(
            universe_symbols=watchlist,
            query="premarket esg and market briefing",
            mode="mixed",
            live_connectors=True,
            providers=["local_esg", "sec_edgar", "marketaux", "alpaca_market"],
            quota_guard=True,
            limit=min(len(watchlist), 8),
            persist=False,
        )
        futures = self._overnight_context()
        items = evidence.get("items", [])
        esg_focus = [
            {
                "symbol": item.get("symbol"),
                "title": item.get("title"),
                "provider": item.get("provider"),
            }
            for item in items
            if str(item.get("item_type")) in {"esg_report", "rag_evidence", "news", "filing"}
        ][:8]
        market_mood = "risk_on" if sentiment.get("overall_polarity", 0.0) > 0.12 else "risk_off" if sentiment.get("overall_polarity", 0.0) < -0.12 else "neutral"
        briefing = {
            "briefing_id": f"premarket-{uuid.uuid4().hex[:12]}",
            "generated_at": utc_now(),
            "watchlist": watchlist,
            "market_mood": market_mood,
            "key_levels": futures,
            "sentiment": sentiment,
            "esg_signals": esg_focus,
            "lineage": [
                "alpaca/yfinance overnight context",
                "esg quant kb enrichment",
                "free-first sentiment snapshot",
            ],
        }
        briefing["storage"] = self.store.storage.persist_record("trading_premarket", briefing["briefing_id"], briefing)
        return briefing

    def run_midday_summary_agent(self) -> dict[str, Any]:
        execution_mode = _normalize_execution_mode(self.get_autopilot_policy().get("execution_mode"))
        account_payload = self.quant_system.get_execution_account(broker="alpaca", mode=execution_mode)
        positions_payload = self.quant_system.list_execution_positions(broker="alpaca", mode=execution_mode)
        positions = positions_payload.get("positions", [])
        account = account_payload.get("account", {})
        equity = float(account.get("equity") or 0.0)
        last_equity = float(account.get("last_equity") or 0.0)
        drawdown = max(0.0, (last_equity - equity) / last_equity) if last_equity else 0.0
        pnl = equity - last_equity if last_equity else 0.0
        summary = {
            "summary_id": f"midday-{uuid.uuid4().hex[:12]}",
            "generated_at": utc_now(),
            "positions": positions,
            "winning_positions": [row for row in positions if float(row.get("unrealized_plpc") or 0.0) > 0],
            "losing_positions": [row for row in positions if float(row.get("unrealized_plpc") or 0.0) <= 0],
            "risk_status": "halt" if drawdown >= 0.06 else "watch" if drawdown >= 0.03 else "controlled",
            "pnl": round(pnl, 2),
            "drawdown": round(drawdown, 6),
            "lineage": [
                f"alpaca {execution_mode} account",
                "position pnl and drawdown rollup",
                "midday risk checkpoint",
            ],
        }
        summary["storage"] = self.store.storage.persist_record("trading_midday", summary["summary_id"], summary)
        return summary

    def run_review_agent(self) -> dict[str, Any]:
        execution_mode = _normalize_execution_mode(self.get_autopilot_policy().get("execution_mode"))
        account_payload = self.quant_system.get_execution_account(broker="alpaca", mode=execution_mode)
        orders_payload = self.quant_system.list_execution_orders(broker="alpaca", status="all", limit=50, mode=execution_mode)
        alerts = self.store.alerts_today(limit=100)
        debates = self.store.list_debate_runs(limit=100)
        risk_rows = self.store.list_risk_approvals(limit=100)
        account = account_payload.get("account", {})
        equity = float(account.get("equity") or 0.0)
        last_equity = float(account.get("last_equity") or 0.0)
        pnl = equity - last_equity if last_equity else 0.0
        trades = orders_payload.get("orders", [])
        esg_hit_notes = [row.get("agent_analysis", "") for row in alerts[:5] if "esg" in str(row.get("agent_analysis", "")).lower()]
        approved = sum(1 for row in risk_rows if str(row.get("verdict", "")).lower() in {"approve", "reduce"})
        blocked = sum(1 for row in risk_rows if str(row.get("verdict", "")).lower() in {"reject", "halt"})
        report = DailyReviewReport(
            review_id=f"review-{uuid.uuid4().hex[:12]}",
            review_date=date.today().isoformat(),
            generated_at=utc_now(),
            pnl=round(pnl, 2),
            trades_count=len(trades),
            esg_signals=esg_hit_notes,
            approved_decisions=approved,
            blocked_decisions=blocked,
            report_text=self._build_review_text(pnl=pnl, trades=trades, approved=approved, blocked=blocked, alerts=alerts),
            strategy_effectiveness={
                "filled_orders": sum(1 for row in trades if str(row.get("status", "")).lower() == "filled"),
                "alert_count": len(alerts),
                "debate_count": len(debates),
                "approval_rate": round(approved / max(approved + blocked, 1), 4),
            },
            next_day_risk_flags=self._next_day_risk_flags(account_payload, risk_rows),
            metadata={"account": account, "orders": trades[:10]},
            lineage=[
                f"alpaca {execution_mode} fills and positions",
                "debate + risk approval ledgers",
                "esg signal hit notes",
            ],
        )
        payload = self.store.save_daily_review(report)
        return {"generated_at": utc_now(), "review": payload}

    async def _handle_monitor_trigger(self, event: dict[str, Any]) -> None:
        try:
            cycle = self.run_trading_cycle(
                symbol=event["symbol"],
                universe=self._active_watchlist_symbols(),
                query=f"{event['trigger_type']} trigger for {event['symbol']}",
                mode="mixed",
                providers=["local_esg", "marketaux", "alpaca_market"],
                auto_submit=True,
                trigger_event=event,
            )
            alert = PriceAlertRecord(
                alert_id=f"alert-{uuid.uuid4().hex[:12]}",
                timestamp=event["observed_at"],
                symbol=event["symbol"],
                trigger_type=event["trigger_type"],
                trigger_value=float(event["trigger_value"]),
                threshold=float(event["threshold"]),
                agent_analysis=cycle["debate"]["bull_thesis"] if cycle.get("debate") else "trigger captured",
                debate_id=cycle.get("debate", {}).get("debate_id"),
                risk_decision=cycle.get("risk", {}).get("verdict"),
                execution_id=cycle.get("execution", {}).get("execution_id"),
                metadata=event.get("metadata", {}),
            )
            self.store.save_price_alert(alert)
        except Exception as exc:
            logger.warning(f"[TradingMonitor] trigger handling failed: {exc}")

    def run_trading_cycle(
        self,
        *,
        symbol: str,
        universe: list[str] | None = None,
        query: str = "",
        mode: str = "mixed",
        providers: list[str] | None = None,
        quota_guard: bool = True,
        auto_submit: bool = True,
        trigger_event: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        policy = self.get_autopilot_policy()
        strategy_snapshot = self.list_strategies()
        strategy_rows = strategy_snapshot.get("strategies", [])
        enabled_strategies = [
            row["strategy_id"]
            for row in strategy_rows
            if str(row.get("status") or "").lower() == "active"
            and (not row.get("allocation") or str((row.get("allocation") or {}).get("status") or "active").lower() == "active")
        ]
        policy_gate_warnings: list[str] = []
        if policy.get("allowed_universe") and str(symbol or "").upper() not in {
            str(item or "").upper() for item in policy.get("allowed_universe") or []
        }:
            policy_gate_warnings.append("symbol_outside_allowed_universe")
        if policy.get("allowed_strategies"):
            allowed = {
                str(item or "").strip()
                for item in policy.get("allowed_strategies") or []
                if str(item or "").strip()
            }
            enabled_strategies = [strategy_id for strategy_id in enabled_strategies if strategy_id in allowed]
        if not enabled_strategies:
            policy_gate_warnings.append("no_active_strategy_slot")
        auto_submit_allowed = bool(auto_submit) and self._autopilot_ready(policy) and not policy_gate_warnings
        factor_pipeline = self.factor_pipeline_manifest(symbol=symbol, strategy_ids=enabled_strategies)
        prepared = self._prepare_inputs(
            symbol=symbol,
            universe=universe,
            query=query,
            mode=mode,
            providers=providers,
            quota_guard=quota_guard,
        )
        sentiment = SentimentSnapshot.model_validate(prepared["sentiment"])
        debate = self._build_debate_report(
            symbol=symbol,
            universe=prepared["universe"],
            evidence_items=prepared["evidence"].get("items", []),
            factor_cards=prepared["factors"].get("factor_cards", []),
            sentiment_snapshot=sentiment,
            signal=prepared["signal"],
            rebuttal_rounds=2,
            evidence_run_id=prepared["evidence"].get("bundle_id"),
        )
        debate_payload = self.store.save_debate_run(debate)
        risk = self._build_risk_approval(symbol=symbol, debate=debate, signal_ttl_minutes=180)
        risk_payload = self.store.save_risk_approval(risk)
        execution_intent = self._build_execution_intent(
            symbol=symbol,
            debate=debate,
            approval=risk,
            policy=policy,
            strategy_slots=enabled_strategies,
            factor_pipeline=factor_pipeline,
            policy_warnings=policy_gate_warnings,
        )
        execution_result = self._execute_approved_trade(
            symbol=symbol,
            debate=debate,
            approval=risk,
            policy=policy,
            execution_intent=execution_intent,
            auto_submit=auto_submit_allowed,
            trigger_event=trigger_event,
        )
        if policy_gate_warnings:
            execution_result.warnings.extend(policy_gate_warnings)
            execution_result.policy_gate_warnings = list(dict.fromkeys([
                *execution_result.policy_gate_warnings,
                *policy_gate_warnings,
            ]))
            if execution_result.status == "review_only":
                execution_result.status = "guarded"
            execution_result.next_action = "clear_policy_warnings_before_submit"
        execution = execution_result.model_dump(mode="json")
        ledger = self._build_order_approval_ledger(
            symbol=symbol,
            debate=debate,
            approval=risk,
            execution_intent=execution_intent,
            execution_result=execution_result,
        )
        ledger_payload = self.store.save_order_approval_ledger(ledger)
        execution_path = self._build_execution_path_status(
            policy=self.store.get_autopilot_policy(),
            current_stage=execution.get("status", "blocked"),
            judge_passed=debate.judge_verdict in {"long", "short"},
            risk_passed=risk.verdict in {"approve", "reduce"},
        )
        execution_path_payload = self.store.save_execution_path_status(execution_path)
        bundle = TradingDecisionBundle(
            bundle_id=f"bundle-{uuid.uuid4().hex[:12]}",
            symbol=symbol,
            universe=prepared["universe"],
            evidence_run_id=prepared["evidence"].get("bundle_id"),
            sentiment=sentiment,
            debate=debate,
            risk=risk,
            execution=execution,
            alerts=[],
            metadata={"mode": mode, "providers": providers or []},
        )
        payload = bundle.model_dump(mode="json")
        payload["evidence"] = prepared["evidence"]
        payload["factor_run"] = prepared["factors"]
        payload["factor_pipeline_manifest"] = factor_pipeline
        payload["debate"] = debate_payload
        payload["risk"] = risk_payload
        payload["execution_intent"] = execution_intent.model_dump(mode="json")
        payload["execution_result"] = execution
        payload["ledger"] = ledger_payload
        payload["execution_path"] = execution_path_payload
        payload["autopilot_policy"] = policy
        payload["strategy_slots"] = enabled_strategies
        payload["policy_gate_warnings"] = policy_gate_warnings
        payload["storage"] = self.store.storage.persist_record("trading_bundles", bundle.bundle_id, payload)
        return payload

    def _prepare_inputs(
        self,
        *,
        symbol: str,
        universe: list[str] | None,
        query: str,
        mode: str,
        providers: list[str] | None,
        quota_guard: bool,
    ) -> dict[str, Any]:
        normalized_symbol = str(symbol or "").upper().strip()
        normalized_universe = self._normalize_universe(universe, normalized_symbol)
        evidence = self.intelligence.scan(
            universe_symbols=normalized_universe,
            query=query or f"trading cycle for {normalized_symbol}",
            live_connectors=mode in {"live", "mixed"},
            mode=mode,
            providers=providers,
            quota_guard=quota_guard,
            limit=max(4, len(normalized_universe)),
            persist=False,
        )
        factors = self.intelligence.discover_factors(
            universe_symbols=normalized_universe,
            query=query or f"factor discovery for {normalized_symbol}",
            evidence_run_id=evidence.get("bundle_id"),
            horizon_days=20,
            mode=mode,
            providers=providers,
            quota_guard=quota_guard,
            persist=False,
        )
        sentiment = self.run_sentiment(
            universe=normalized_universe,
            providers=providers,
            quota_guard=quota_guard,
        )
        signals = self.quant_system._build_signals(
            self.quant_system.get_default_universe(normalized_universe),
            query or f"trading graph for {normalized_symbol}",
            self.quant_system.default_benchmark,
        )
        signal = next((row for row in signals if str(row.symbol).upper() == normalized_symbol), signals[0])
        return {
            "universe": normalized_universe,
            "evidence": evidence,
            "factors": factors,
            "sentiment": sentiment,
            "signal": signal,
        }

    def _build_debate_report(
        self,
        *,
        symbol: str,
        universe: list[str],
        evidence_items: list[dict[str, Any]],
        factor_cards: list[dict[str, Any]],
        sentiment_snapshot: SentimentSnapshot,
        signal: Any,
        rebuttal_rounds: int,
        evidence_run_id: str | None,
    ) -> DebateReport:
        symbol_items = [item for item in evidence_items if str(item.get("symbol", "")).upper() == symbol.upper()]
        positive_items = [item for item in symbol_items if self._evidence_sentiment(item) > 0.05]
        negative_items = [item for item in symbol_items if self._evidence_sentiment(item) < -0.05]
        cards = [FactorCard.model_validate(card) for card in factor_cards if symbol.upper() in set(card.get("universe", []) or [symbol])]
        promoted = [card for card in cards if card.status == "promoted"]
        rejected = [card for card in cards if card.status in {"rejected", "low_confidence"}]
        symbol_sentiment = next((row for row in sentiment_snapshot.symbol_scores if row.symbol == symbol.upper()), None)
        sentiment_value = float(symbol_sentiment.polarity if symbol_sentiment else sentiment_snapshot.overall_polarity)
        bullish_edge = (
            len(positive_items) * 0.16
            + len(promoted) * 0.12
            + max(sentiment_value, 0.0) * 0.28
            + max(float(getattr(signal, "expected_return", 0.0) or 0.0), 0.0) * 5.0
        )
        bearish_edge = (
            len(negative_items) * 0.16
            + len(rejected) * 0.10
            + max(-sentiment_value, 0.0) * 0.28
            + max(float(getattr(signal, "risk_score", 0.0) or 0.0) / 100.0 - 0.4, 0.0) * 0.35
        )
        delta = bullish_edge - bearish_edge
        dispute_score = _clamp(abs(delta) * 0.5 + abs(sentiment_value) * 0.15 + (0.12 if len(negative_items) and len(positive_items) else 0.0), 0.0, 1.0)
        verdict: TradingAction
        if delta >= 0.14:
            verdict = "long"
        elif delta <= -0.14:
            verdict = "short"
        elif abs(delta) <= 0.03:
            verdict = "block"
        else:
            verdict = "neutral"
        judge_confidence = _clamp(0.46 + abs(delta) * 0.8 + len(promoted) * 0.03, 0.0, 1.0)
        bull_titles = [item.get("title", "") for item in positive_items[:3]]
        bear_titles = [item.get("title", "") for item in negative_items[:3]]
        turns = [
            DebateTurn(
                round_number=index,
                bull_point=self._bull_point(index, signal, bull_titles, promoted, sentiment_value),
                bear_point=self._bear_point(index, signal, bear_titles, rejected, sentiment_value),
                evidence_focus=(bull_titles + bear_titles)[:4],
                confidence_shift=round(delta / max(index, 1), 4),
            )
            for index in range(1, max(rebuttal_rounds, 1) + 1)
        ]
        conflict_points = []
        if positive_items and negative_items:
            conflict_points.append("Same-day evidence contains both supportive and adverse readings.")
        if sentiment_value < -0.15 and promoted:
            conflict_points.append("Factor gate is constructive while sentiment remains negative.")
        if float(getattr(signal, "risk_score", 0.0) or 0.0) >= 55:
            conflict_points.append("Risk score remains elevated relative to current judge verdict.")

        consensus_points = [
            f"ESG / Quant KB delivered {len(symbol_items)} linked items for {symbol.upper()}.",
            f"Sentiment feature projected to {symbol_sentiment.feature_value if symbol_sentiment else 50.0:.2f}.",
            f"Promoted factor count: {len(promoted)} / total cards: {len(cards)}.",
        ]
        return DebateReport(
            debate_id=f"debate-{symbol.upper()}-{uuid.uuid4().hex[:10]}",
            generated_at=utc_now(),
            symbol=symbol.upper(),
            universe=universe,
            bull_thesis=self._bull_thesis(signal, positive_items, promoted, sentiment_value),
            bear_thesis=self._bear_thesis(signal, negative_items, rejected, sentiment_value),
            turns=turns,
            conflict_points=conflict_points or ["No major thesis conflict beyond normal market noise."],
            consensus_points=consensus_points,
            judge_verdict=verdict,
            judge_confidence=round(judge_confidence, 4),
            dispute_score=round(dispute_score, 4),
            recommended_action=verdict,
            confidence_shift=round(delta, 4),
            requires_human_review=bool(dispute_score >= 0.68 or verdict == "block"),
            evidence_run_id=evidence_run_id,
            factor_count=len(cards),
            sentiment_snapshot_id=sentiment_snapshot.snapshot_id,
            sentiment_overview={
                "polarity": round(sentiment_value, 4),
                "confidence": round(float(symbol_sentiment.confidence if symbol_sentiment else sentiment_snapshot.confidence), 4),
                "headline_count": int(symbol_sentiment.article_count if symbol_sentiment else sentiment_snapshot.headline_count),
                "feature_value": round(float(symbol_sentiment.feature_value if symbol_sentiment else 50.0), 2),
                "freshness_score": round(float(symbol_sentiment.freshness_score if symbol_sentiment else sentiment_snapshot.freshness_score), 4),
                "source_mix": dict(symbol_sentiment.source_mix if symbol_sentiment else sentiment_snapshot.source_mix),
            },
            expected_edge=round(float(getattr(signal, "expected_return", 0.0) or 0.0) + sentiment_value * 0.01, 6),
            metadata={
                "positive_items": len(positive_items),
                "negative_items": len(negative_items),
                "bullish_edge": round(bullish_edge, 4),
                "bearish_edge": round(bearish_edge, 4),
            },
            lineage=[
                "market_context",
                "esg_kb_enrichment",
                "sentiment_agent",
                "bull_researcher",
                "bear_researcher",
                "judge_agent",
            ],
        )

    def _build_risk_approval(self, *, symbol: str, debate: DebateReport, signal_ttl_minutes: int) -> RiskApproval:
        execution_mode = _normalize_execution_mode(self.get_autopilot_policy().get("execution_mode"))
        account_payload = self.quant_system.get_execution_account(broker="alpaca", mode=execution_mode)
        positions_payload = self.quant_system.list_execution_positions(broker="alpaca", mode=execution_mode)
        orders_payload = self.quant_system.list_execution_orders(broker="alpaca", status="open", limit=50, mode=execution_mode)
        account = account_payload.get("account", {})
        positions = positions_payload.get("positions", [])
        open_orders = orders_payload.get("orders", [])
        equity = float(account.get("equity") or 0.0)
        last_equity = float(account.get("last_equity") or 0.0)
        buying_power = float(account.get("buying_power") or 0.0)
        drawdown_estimate = max(0.0, (last_equity - equity) / last_equity) if last_equity else 0.0
        duplicate_order = any(str(row.get("symbol", "")).upper() == symbol.upper() for row in open_orders)
        position_value = 0.0
        for row in positions:
            if str(row.get("symbol", "")).upper() == symbol.upper():
                position_value = abs(float(row.get("market_value") or 0.0))
                break
        concentration = position_value / max(equity, 1.0)
        max_weight = float(getattr(self.quant_system, "default_capital", 1_000_000.0))
        _ = max_weight  # keep linter happy while we use explicit cap below
        configured_cap = float(getattr(settings, "EXECUTION_SINGLE_NAME_WEIGHT_CAP", 0.26) or 0.26)
        kelly_fraction = self._fractional_kelly(
            expected_edge=float(debate.expected_edge or 0.0),
            confidence=float(debate.judge_confidence or 0.0),
            dispute=float(debate.dispute_score or 0.0),
        )
        recommended_weight = min(configured_cap, kelly_fraction)
        recommended_notional = round(max(0.0, equity * recommended_weight), 2)
        rationale: list[str] = []
        hard_blocks: list[str] = []
        risk_flags: list[str] = []
        market_clock = account_payload.get("market_clock", {})
        market_open = bool(market_clock.get("is_open")) if market_clock else None

        if bool(getattr(settings, "EXECUTION_KILL_SWITCH", False)):
            hard_blocks.append("Global execution kill switch is enabled.")
        if debate.recommended_action in {"neutral", "block"}:
            hard_blocks.append("Judge verdict is not executable.")
        if debate.requires_human_review:
            risk_flags.append("Debate requires human review because dispute score is elevated.")
        if duplicate_order:
            hard_blocks.append(f"Duplicate open order detected for {symbol.upper()}.")
        if drawdown_estimate >= 0.08:
            hard_blocks.append("Estimated account drawdown breached 8% intraday control.")
        elif drawdown_estimate >= 0.04:
            risk_flags.append("Estimated account drawdown is above the soft warning threshold.")
        if concentration >= configured_cap:
            hard_blocks.append("Existing concentration already exceeds the configured single-name cap.")
        if recommended_notional > buying_power and buying_power > 0:
            risk_flags.append("Recommended notional exceeds current buying power; size will be reduced.")
            recommended_notional = round(max(0.0, buying_power * 0.9), 2)
            recommended_weight = recommended_notional / max(equity, 1.0)
        if signal_ttl_minutes <= 0:
            hard_blocks.append("Signal TTL has expired.")

        if hard_blocks:
            verdict = "halt" if any("kill switch" in item.lower() or "drawdown" in item.lower() for item in hard_blocks) else "reject"
            approved_action: TradingAction = "block"
        elif risk_flags or recommended_notional <= 0:
            verdict = "reduce"
            approved_action = "long" if debate.recommended_action == "long" else debate.recommended_action
        else:
            verdict = "approve"
            approved_action = debate.recommended_action

        if recommended_notional < 25:
            risk_flags.append("Recommended notional is tiny; execution value is low.")
            if not hard_blocks:
                verdict = "reject"
                approved_action = "block"

        rationale.append(f"Kelly fraction set to {kelly_fraction:.4f}.")
        rationale.append(f"Recommended notional set to {recommended_notional:.2f}.")
        rationale.append(f"Drawdown estimate at {drawdown_estimate:.4f}.")
        return RiskApproval(
            approval_id=f"risk-{symbol.upper()}-{uuid.uuid4().hex[:10]}",
            generated_at=utc_now(),
            symbol=symbol.upper(),
            debate_id=debate.debate_id,
            requested_action=debate.recommended_action,
            approved_action=approved_action,
            verdict=verdict,
            kelly_fraction=round(kelly_fraction, 6),
            recommended_weight=round(recommended_weight, 6),
            recommended_notional=round(recommended_notional, 2),
            max_position_weight=round(configured_cap, 4),
            drawdown_estimate=round(drawdown_estimate, 6),
            signal_ttl_minutes=signal_ttl_minutes,
            duplicate_order_detected=duplicate_order,
            market_open=market_open,
            hard_blocks=hard_blocks,
            risk_flags=risk_flags,
            rationale=rationale,
            account_snapshot=account_payload,
            positions_snapshot=positions[:10],
            metadata={"open_order_count": len(open_orders), "buying_power": buying_power},
            lineage=[
                "judge_agent",
                "risk_manager_agent",
                "broker account and position checks",
                "execution auto-submit gate",
            ],
        )

    def _execute_approved_trade(
        self,
        *,
        symbol: str,
        debate: DebateReport,
        approval: RiskApproval,
        policy: dict[str, Any],
        execution_intent: ExecutionIntent,
        auto_submit: bool,
        trigger_event: dict[str, Any] | None,
    ) -> ExecutionResult:
        execution_id = f"trade-{symbol.upper()}-{uuid.uuid4().hex[:10]}"
        execution_mode = _normalize_execution_mode(policy.get("execution_mode"))
        payload = ExecutionResult(
            execution_id=execution_id,
            generated_at=utc_now(),
            symbol=symbol.upper(),
            status="review_only",
            venue=f"alpaca_{execution_mode}",
            execution_mode=execution_mode,
            submitted=False,
            auto_submit=bool(auto_submit),
            requested_action=debate.recommended_action,
            approved_action=approval.approved_action,
            verdict=approval.verdict,
            order_payload={},
            receipt=None,
            warnings=list(approval.risk_flags),
            policy_gate_warnings=[],
            next_action="manual_review_only",
            trigger_event=trigger_event or {},
            metadata={"intent_id": execution_intent.intent_id},
        )
        if not auto_submit:
            return payload
        if approval.verdict not in {"approve", "reduce"} or approval.approved_action not in {"long", "short"}:
            payload.status = "blocked"
            payload.next_action = "risk_gate_blocked_submit"
            return payload
        side = "buy" if approval.approved_action == "long" else "sell"
        order_payload = {
            "symbol": symbol.upper(),
            "side": side,
            "type": "market",
            "time_in_force": "day",
            "notional": max(25.0, round(float(approval.recommended_notional), 2)),
            "client_order_id": f"{execution_id}-{side}",
        }
        payload.order_payload = order_payload
        try:
            if hasattr(self.quant_system.alpaca, "set_runtime_mode"):
                self.quant_system.alpaca.set_runtime_mode(execution_mode)
            receipt = self.quant_system.alpaca.submit_order(order_payload)
            payload.submitted = True
            payload.status = "submitted"
            payload.receipt = receipt
            payload.next_action = "monitor_fill_and_review"
        except Exception as exc:
            payload.status = "submit_failed"
            payload.warnings.append(str(exc))
            payload.next_action = "inspect_broker_receipt_and_retry_review_only"
        return payload

    def _active_watchlist_symbols(self) -> list[str]:
        rows = self.store.list_watchlist(enabled_only=True)
        values = [str(row.get("symbol") or "").upper().strip() for row in rows if str(row.get("symbol") or "").strip()]
        return values or list(self.DEFAULT_WATCHLIST)

    @staticmethod
    def _normalize_universe(universe: list[str] | None, symbol: str) -> list[str]:
        values = [str(item or "").upper().strip() for item in universe or [] if str(item or "").strip()]
        if symbol and symbol.upper() not in values:
            values.insert(0, symbol.upper())
        return list(dict.fromkeys(values or [symbol.upper()]))

    @staticmethod
    def _evidence_sentiment(item: dict[str, Any]) -> float:
        text = " ".join(
            [
                str(item.get("title") or ""),
                str(item.get("summary") or ""),
                str(item.get("provider") or ""),
            ]
        ).lower()
        positive = sum(1 for token in ("improving", "upgrade", "beat", "resilient", "positive", "gain") if token in text)
        negative = sum(1 for token in ("controversy", "probe", "miss", "risk", "negative", "decline") if token in text)
        if not positive and not negative:
            return 0.0
        return (positive - negative) / max(positive + negative, 1)

    @staticmethod
    def _bull_thesis(signal: Any, positive_items: list[dict[str, Any]], promoted: list[FactorCard], sentiment_value: float) -> str:
        return (
            f"Bull sees {signal.symbol} as a supported long because {len(promoted)} factor gates are promotable, "
            f"{len(positive_items)} linked evidence items lean constructive, and sentiment sits at {sentiment_value:.2f}."
        )

    @staticmethod
    def _bear_thesis(signal: Any, negative_items: list[dict[str, Any]], rejected: list[FactorCard], sentiment_value: float) -> str:
        return (
            f"Bear argues {signal.symbol} should be constrained because {len(negative_items)} evidence items lean adverse, "
            f"{len(rejected)} factor gates are weak or rejected, and sentiment sits at {sentiment_value:.2f}."
        )

    @staticmethod
    def _bull_point(index: int, signal: Any, bull_titles: list[str], promoted: list[FactorCard], sentiment_value: float) -> str:
        if index == 1:
            return f"Initial bull case: {signal.symbol} retains positive expected edge with {len(promoted)} promoted factor cards."
        return f"Rebuttal {index}: bull leans on {bull_titles[0] if bull_titles else 'supportive factor structure'} and sentiment {sentiment_value:.2f}."

    @staticmethod
    def _bear_point(index: int, signal: Any, bear_titles: list[str], rejected: list[FactorCard], sentiment_value: float) -> str:
        if index == 1:
            return f"Initial bear case: {signal.symbol} remains vulnerable to evidence conflict and risk-score pressure."
        return f"Rebuttal {index}: bear highlights {bear_titles[0] if bear_titles else 'weak confirmation breadth'} and {len(rejected)} gated factors."

    @staticmethod
    def _fractional_kelly(*, expected_edge: float, confidence: float, dispute: float) -> float:
        raw = max(expected_edge, 0.0) / max(0.03 + dispute * 0.08, 0.05)
        scaled = raw * max(confidence, 0.1) * 0.25
        return _clamp(scaled, 0.0, 0.25)

    def _overnight_context(self) -> dict[str, Any]:
        symbols = ["SPY", "QQQ"]
        context: dict[str, Any] = {}
        for symbol in symbols:
            try:
                bars = self.quant_system.market_data.get_daily_bars(symbol, limit=3)
                frame = bars.bars
                closes = frame["close"].astype(float).tolist()
                if len(closes) >= 2:
                    context[symbol] = {
                        "last_close": closes[-1],
                        "previous_close": closes[-2],
                        "change_pct": round((closes[-1] - closes[-2]) / closes[-2], 6) if closes[-2] else 0.0,
                        "provider": bars.provider,
                    }
            except Exception as exc:
                context[symbol] = {"warning": str(exc)}
        return context

    @staticmethod
    def _build_review_text(
        *,
        pnl: float,
        trades: list[dict[str, Any]],
        approved: int,
        blocked: int,
        alerts: list[dict[str, Any]],
    ) -> str:
        return (
            f"Daily review: pnl={pnl:.2f}, trades={len(trades)}, approvals={approved}, blocked={blocked}, "
            f"alerts={len(alerts)}. ESG-linked and debate-driven decisions remain guardrailed by judge and risk."
        )

    @staticmethod
    def _next_day_risk_flags(account_payload: dict[str, Any], risk_rows: list[dict[str, Any]]) -> list[str]:
        flags: list[str] = []
        account = account_payload.get("account", {})
        equity = float(account.get("equity") or 0.0)
        last_equity = float(account.get("last_equity") or 0.0)
        if last_equity and equity < last_equity * 0.97:
            flags.append("Execution equity is down more than 3% day-over-day.")
        if any(str(row.get("verdict", "")).lower() == "halt" for row in risk_rows):
            flags.append("A halt verdict was issued during the session.")
        return flags or ["No additional next-day risk flags."]

    def _autopilot_warnings(self, payload: dict[str, Any]) -> list[str]:
        warnings: list[str] = []
        if not self._policy_auto_submit_enabled(payload):
            warnings.append("auto_submit_disabled")
        if not payload.get("armed"):
            warnings.append("autopilot_disarmed")
        if payload.get("kill_switch"):
            warnings.append("kill_switch_enabled")
        if float(payload.get("daily_budget_cap") or 0.0) <= 0:
            warnings.append("daily_budget_not_set")
        if not payload.get("allowed_strategies"):
            warnings.append("no_strategy_allowlist")
        return warnings

    def _autopilot_ready(self, policy: dict[str, Any]) -> bool:
        return (
            _normalize_execution_permission(policy.get("execution_permission")) == "auto_submit"
            and self._policy_auto_submit_enabled(policy)
            and bool(policy.get("armed"))
            and not bool(policy.get("kill_switch"))
        )

    def _build_execution_path_status(
        self,
        *,
        policy: dict[str, Any],
        current_stage: str,
        judge_passed: bool,
        risk_passed: bool,
    ) -> ExecutionPathStatus:
        stages = [
            {"stage": "scan", "status": "ready"},
            {"stage": "factors", "status": "ready"},
            {"stage": "debate", "status": "ready"},
            {"stage": "judge", "status": "passed" if judge_passed else "pending"},
            {"stage": "risk", "status": "passed" if risk_passed else "pending"},
            {"stage": "submit", "status": "ready" if risk_passed and self._autopilot_ready(policy) else "blocked"},
            {"stage": "monitor", "status": "ready" if self._autopilot_ready(policy) else "standby"},
            {"stage": "review", "status": "ready"},
        ]
        budget = float(policy.get("daily_budget_cap") or 0.0)
        return ExecutionPathStatus(
            generated_at=utc_now(),
            mode=_normalize_execution_mode(policy.get("execution_mode")),
            armed=bool(policy.get("armed")),
            daily_budget_cap=budget,
            budget_remaining=budget,
            judge_passed=judge_passed,
            risk_passed=risk_passed,
            kill_switch=bool(policy.get("kill_switch")),
            current_stage=current_stage,
            stages=stages,
            lineage=["scan", "factors", "debate", "judge", "risk", "submit", "monitor", "review"],
            warnings=self._autopilot_warnings(policy),
        )

    def _build_execution_intent(
        self,
        *,
        symbol: str,
        debate: DebateReport,
        approval: RiskApproval,
        policy: dict[str, Any],
        strategy_slots: list[str],
        factor_pipeline: dict[str, Any],
        policy_warnings: list[str],
    ) -> ExecutionIntent:
        return ExecutionIntent(
            intent_id=f"intent-{symbol.upper()}-{uuid.uuid4().hex[:10]}",
            created_at=utc_now(),
            symbol=symbol.upper(),
            requested_action=debate.recommended_action,
            approved_action=approval.approved_action,
            execution_mode=_normalize_execution_mode(policy.get("execution_mode")),
            strategy_slots=list(strategy_slots),
            factor_dependencies=list(factor_pipeline.get("factor_dependencies") or []),
            recommended_weight=float(approval.recommended_weight or 0.0),
            recommended_notional=float(approval.recommended_notional or 0.0),
            signal_ttl_minutes=int(approval.signal_ttl_minutes or 0),
            guards=[
                "judge_gate",
                "risk_gate",
                *list(policy_warnings or []),
            ],
            metadata={
                "debate_id": debate.debate_id,
                "approval_id": approval.approval_id,
                "factor_pipeline_manifest": factor_pipeline.get("manifest_id"),
            },
        )

    def _sample_execution_intent(self) -> ExecutionIntent:
        factor_pipeline = self.factor_pipeline_manifest()
        strategy_slots = list(factor_pipeline.get("strategy_slots") or [])
        return ExecutionIntent(
            intent_id="intent-execution-sample",
            created_at=utc_now(),
            symbol=(self._active_watchlist_symbols()[0] if self._active_watchlist_symbols() else "AAPL"),
            requested_action="long",
            approved_action="long",
            execution_mode=_normalize_execution_mode(self.get_autopilot_policy().get("execution_mode")),
            strategy_slots=strategy_slots,
            factor_dependencies=list(factor_pipeline.get("factor_dependencies") or []),
            recommended_weight=0.05,
            recommended_notional=5000.0,
            signal_ttl_minutes=180,
            guards=["judge_gate", "risk_gate", "auto_submit"],
            metadata={"sample": True},
        )

    def _sample_execution_result(self) -> ExecutionResult:
        return ExecutionResult(
            execution_id="execution-runtime-sample",
            generated_at=utc_now(),
            symbol=(self._active_watchlist_symbols()[0] if self._active_watchlist_symbols() else "AAPL"),
            status="review_only",
            venue="alpaca",
            execution_mode=_normalize_execution_mode(self.get_autopilot_policy().get("execution_mode")),
            submitted=False,
            auto_submit=False,
            requested_action="long",
            approved_action="long",
            verdict="approve",
            order_payload={},
            receipt=None,
            warnings=[],
            policy_gate_warnings=[],
            next_action="arm_autopilot_or_run_manual_review",
            trigger_event={},
            metadata={"sample": True},
        )

    def _build_order_approval_ledger(
        self,
        *,
        symbol: str,
        debate: DebateReport,
        approval: RiskApproval,
        execution_intent: ExecutionIntent,
        execution_result: ExecutionResult,
    ) -> OrderApprovalLedger:
        status = str(execution_result.status or "blocked")
        verdict = "submitted" if execution_result.submitted else (
            "review_only" if status in {"review_only", "guarded"} else "submit_failed" if status == "submit_failed" else "blocked"
        )
        return OrderApprovalLedger(
            ledger_id=f"ledger-{symbol.upper()}-{uuid.uuid4().hex[:10]}",
            generated_at=utc_now(),
            symbol=symbol.upper(),
            execution_intent=execution_intent,
            execution_result=execution_result,
            debate_id=debate.debate_id,
            approval_id=approval.approval_id,
            verdict=verdict,
            submitted=bool(execution_result.submitted),
            receipt=execution_result.receipt,
            warnings=list(execution_result.warnings or []),
            lineage=["lean_order_lifecycle", "judge", "risk_manager", "submit"],
            metadata={"execution_status": status},
        )

    @staticmethod
    def _is_market_day() -> bool:
        try:
            now = datetime.now(ZoneInfo(getattr(settings, "SCHEDULER_TIMEZONE", "America/New_York")))
        except Exception:
            now = datetime.now(timezone.utc)
        return now.weekday() < 5


_trading_service: TradingAgentService | None = None


def get_trading_service(*, quant_system: QuantSystemService, get_client: Any | None = None) -> TradingAgentService:
    global _trading_service
    if _trading_service is None:
        _trading_service = TradingAgentService(quant_system=quant_system, get_client=get_client)
    return _trading_service
