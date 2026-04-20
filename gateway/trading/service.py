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
    DailyReviewReport,
    DebateReport,
    DebateTurn,
    PriceAlertRecord,
    RiskApproval,
    SentimentSnapshot,
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
                "paper auto-submit gate",
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
            "notifier": {
                "telegram_configured": bool(
                    getattr(settings, "TELEGRAM_BOT_TOKEN", "") and getattr(settings, "TELEGRAM_CHAT_ID", "")
                ),
                "mode": "paper_shadow_notify",
            },
        }

    def list_watchlist(self) -> dict[str, Any]:
        rows = self.store.list_watchlist(enabled_only=True)
        return {
            "generated_at": utc_now(),
            "watchlist": rows,
            "count": len(rows),
            "mode": "paper_auto_submit",
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
        account_payload = self.quant_system.get_execution_account(broker="alpaca", mode="paper")
        positions_payload = self.quant_system.list_execution_positions(broker="alpaca", mode="paper")
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
                "alpaca paper account",
                "position pnl and drawdown rollup",
                "midday risk checkpoint",
            ],
        }
        summary["storage"] = self.store.storage.persist_record("trading_midday", summary["summary_id"], summary)
        return summary

    def run_review_agent(self) -> dict[str, Any]:
        account_payload = self.quant_system.get_execution_account(broker="alpaca", mode="paper")
        orders_payload = self.quant_system.list_execution_orders(broker="alpaca", status="all", limit=50, mode="paper")
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
                "alpaca paper fills and positions",
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
        execution = self._execute_approved_trade(
            symbol=symbol,
            debate=debate,
            approval=risk,
            auto_submit=auto_submit,
            trigger_event=trigger_event,
        )
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
        payload["debate"] = debate_payload
        payload["risk"] = risk_payload
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
        account_payload = self.quant_system.get_execution_account(broker="alpaca", mode="paper")
        positions_payload = self.quant_system.list_execution_positions(broker="alpaca", mode="paper")
        orders_payload = self.quant_system.list_execution_orders(broker="alpaca", status="open", limit=50, mode="paper")
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
                "paper auto-submit gate",
            ],
        )

    def _execute_approved_trade(
        self,
        *,
        symbol: str,
        debate: DebateReport,
        approval: RiskApproval,
        auto_submit: bool,
        trigger_event: dict[str, Any] | None,
    ) -> dict[str, Any]:
        execution_id = f"trade-{symbol.upper()}-{uuid.uuid4().hex[:10]}"
        payload = {
            "execution_id": execution_id,
            "symbol": symbol.upper(),
            "requested_action": debate.recommended_action,
            "approved_action": approval.approved_action,
            "verdict": approval.verdict,
            "auto_submit": bool(auto_submit),
            "submitted": False,
            "warnings": list(approval.risk_flags),
            "trigger_event": trigger_event or {},
        }
        if not auto_submit:
            payload["status"] = "review_only"
            return payload
        if approval.verdict not in {"approve", "reduce"} or approval.approved_action not in {"long", "short"}:
            payload["status"] = "blocked"
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
        try:
            receipt = self.quant_system.alpaca.submit_order(order_payload)
            payload["submitted"] = True
            payload["status"] = "submitted"
            payload["receipt"] = receipt
        except Exception as exc:
            payload["status"] = "submit_failed"
            payload["warnings"].append(str(exc))
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
            f"alerts={len(alerts)}. ESG-linked and debate-driven decisions remain paper-only."
        )

    @staticmethod
    def _next_day_risk_flags(account_payload: dict[str, Any], risk_rows: list[dict[str, Any]]) -> list[str]:
        flags: list[str] = []
        account = account_payload.get("account", {})
        equity = float(account.get("equity") or 0.0)
        last_equity = float(account.get("last_equity") or 0.0)
        if last_equity and equity < last_equity * 0.97:
            flags.append("Paper equity is down more than 3% day-over-day.")
        if any(str(row.get("verdict", "")).lower() == "halt" for row in risk_rows):
            flags.append("A halt verdict was issued during the session.")
        return flags or ["No additional next-day risk flags."]

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
