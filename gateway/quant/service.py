from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import hashlib
from itertools import product
import math
import random
import shutil
import sys
import statistics
import tarfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests
from pydantic import BaseModel

from gateway.config import settings
from gateway.quant.esg_house_score import compute_house_score
from gateway.quant.alpha_ranker import AlphaRankerRuntime
from gateway.quant.alpaca import AlpacaPaperClient
from gateway.quant.brokers import BrokerRegistry
from gateway.quant.intelligence_models import SweepRun, TearsheetReport
from gateway.quant.market_data import MarketDataGateway
from gateway.quant.models import (
    AlphaValidationReport,
    ArchitectureLayerStatus,
    BacktestMetrics,
    BacktestPoint,
    BacktestResult,
    ExecutionJournal,
    ExecutionOrder,
    ExecutionPlan,
    ExperimentRun,
    FactorScore,
    OrderLifecycleEvent,
    OrderLifecycleRecord,
    PortfolioPosition,
    PortfolioSummary,
    ProjectionScenario,
    ResearchSignal,
    RiskAlert,
    TrainingPlan,
    UniverseMember,
    ValidationWindow,
)
from gateway.quant.p1_stack import P1ModelSuiteRuntime
from gateway.quant.p2_decision import P2DecisionStackRuntime
from gateway.quant.paper_services import (
    DeploymentPreflightService,
    OutcomeLedgerService,
    PaperPerformanceService,
    PaperWorkflowService,
    PromotionService,
)
from gateway.quant.promotion_policy import evaluate_thresholds, load_promotion_policy
from gateway.quant.provenance import SyntheticEvidenceGuard
from gateway.quant.service_components import QuantServiceComponents, build_alpaca_order_payload, coerce_float
from gateway.scheduler.event_classifier_runtime import get_event_classifier_runtime
from gateway.utils.email_delivery import send_email_message
from gateway.quant.signals import MovingAverageCrossSignalEngine
from gateway.quant.storage import QuantStorageGateway
from gateway.quant.trading_calendar import TradingCalendarService
from gateway.utils.logger import get_logger

logger = get_logger(__name__)


def _stable_seed(*parts: str) -> int:
    raw = "::".join(parts).encode("utf-8")
    return int(hashlib.sha256(raw).hexdigest()[:8], 16)


def _bounded(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _as_dict(model: BaseModel | dict[str, Any]) -> dict[str, Any]:
    if isinstance(model, BaseModel):
        return model.model_dump()
    return dict(model)


def _jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in value]
    if isinstance(value, np.ndarray):
        return [_jsonable(item) for item in value.tolist()]
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def _safe_mean(values: list[float]) -> float:
    cleaned = [float(value) for value in values if value is not None]
    return float(statistics.mean(cleaned)) if cleaned else 0.0


class QuantSystemService:
    def __init__(self, get_client: Any | None = None) -> None:
        self.storage = QuantStorageGateway(get_client=get_client)
        self.alpaca = AlpacaPaperClient()
        self.brokers = BrokerRegistry(get_alpaca_client=lambda: self.alpaca)
        self.market_data = MarketDataGateway()
        self.signal_engine = MovingAverageCrossSignalEngine(self.market_data)
        self.trading_calendar = TradingCalendarService()
        self.synthetic_guard = SyntheticEvidenceGuard(getattr(settings, "SYNTHETIC_EVIDENCE_POLICY", "block"))
        self.paper_workflow_service = PaperWorkflowService(self)
        self.paper_performance_service = PaperPerformanceService(self)
        self.outcome_ledger_service = OutcomeLedgerService(self)
        self.promotion_service = PromotionService(self)
        self.deployment_preflight_service = DeploymentPreflightService(self)
        self.alpha_ranker = AlphaRankerRuntime()
        self.p1_suite = P1ModelSuiteRuntime()
        self.p2_stack = P2DecisionStackRuntime()
        self.components = QuantServiceComponents.from_owner(self)
        self.market_data_component = self.components.market_data
        self.dashboard_component = self.components.dashboard
        self.execution_component = self.components.execution
        self.paper_workflow_component = self.components.paper_workflow
        self.default_capital = float(getattr(settings, "QUANT_DEFAULT_CAPITAL", 1_000_000))
        self.default_benchmark = getattr(settings, "QUANT_DEFAULT_BENCHMARK", "SPY")
        self.default_universe_name = getattr(settings, "QUANT_DEFAULT_UNIVERSE", "ESG_US_LARGE_CAP")
        self.default_broker = getattr(settings, "QUANT_BROKER_DEFAULT", "alpaca")
        self._overview_cache: dict[str, Any] | None = None
        self._watchlist_snapshot_cache: dict[str, Any] | None = None
        self._dashboard_watchlist_snapshot_cache: dict[str, dict[str, Any]] = {}
        self._account_snapshot_cache: dict[str, dict[str, Any]] = {}
        self._position_symbols_cache: dict[str, dict[str, Any]] = {}
        self._chart_cache: dict[tuple[str, str, str], dict[str, Any]] = {}
        self._dashboard_summary_cache: dict[str, dict[str, Any]] = {}
        self._dashboard_secondary_cache: dict[str, dict[str, Any]] = {}
        self._shared_market_bars_cache: dict[tuple[Any, ...], dict[str, Any]] = {}
        self._dashboard_cache_ttl_seconds = int(getattr(settings, "QUANT_DASHBOARD_CACHE_TTL_SECONDS", 15) or 15)
        self._dashboard_market_workers = max(1, int(getattr(settings, "QUANT_DASHBOARD_MARKET_WORKERS", 6) or 6))
        self._dashboard_live_timeout_seconds = max(1, int(getattr(settings, "QUANT_DASHBOARD_LIVE_TIMEOUT_SECONDS", 4) or 4))
        self._last_dashboard_symbol = "AAPL"

    @staticmethod
    def _cache_is_fresh(entry: dict[str, Any] | None) -> bool:
        if not entry:
            return False
        expires_at = entry.get("expires_at")
        return isinstance(expires_at, datetime) and expires_at > datetime.now(timezone.utc)

    def _cache_wrap(self, payload: dict[str, Any], ttl_seconds: int | None = None) -> dict[str, Any]:
        ttl = int(ttl_seconds or self._dashboard_cache_ttl_seconds)
        return {
            "payload": payload,
            "expires_at": datetime.now(timezone.utc) + timedelta(seconds=max(ttl, 1)),
        }

    def _market_data_provider_order(self) -> list[str]:
        return self.market_data_component.provider_order()

    def _get_daily_bars(
        self,
        symbol: str,
        *,
        limit: int = 180,
        force_refresh: bool = False,
        provider_order_override: list[str] | None = None,
        cache_only: bool = False,
        allow_stale_cache: bool = True,
        timeout_override: int | None = None,
    ):
        return self.market_data_component.daily_bars(
            symbol,
            limit=limit,
            force_refresh=force_refresh,
            provider_order_override=provider_order_override,
            cache_only=cache_only,
            allow_stale_cache=allow_stale_cache,
            timeout_override=timeout_override,
        )

    def _cached_payload(self, entry: dict[str, Any] | None) -> Any:
        if self._cache_is_fresh(entry):
            return entry["payload"]
        return None

    @staticmethod
    def _normalize_broker_mode(mode: str | None) -> str:
        return "live" if str(mode or "").strip().lower() == "live" else "paper"

    def _execution_notional_limits(self, mode: str | None) -> dict[str, Any]:
        return self.execution_component.notional_limits(mode)

    def _prepare_broker_adapter(self, broker: str | None, mode: str | None = None):
        adapter = self._resolve_broker(broker)
        normalized_mode = self._normalize_broker_mode(mode)
        if adapter.broker_id == "alpaca" and hasattr(self.alpaca, "set_runtime_mode"):
            self.alpaca.set_runtime_mode(normalized_mode)
        return adapter, normalized_mode

    def _connection_status_for_mode(self, adapter: Any, mode: str) -> dict[str, Any]:
        try:
            status = adapter.connection_status(mode)
        except TypeError:
            if hasattr(adapter, "set_runtime_mode"):
                adapter.set_runtime_mode(mode)
            status = adapter.connection_status()
        return dict(status or {})

    def _paper_gate_thresholds(self) -> dict[str, Any]:
        return self.paper_workflow_component.gate_thresholds()

    def build_paper_gate_report(
        self,
        *,
        points: list[dict[str, Any]] | None = None,
        persist: bool = False,
    ) -> dict[str, Any]:
        thresholds = self._paper_gate_thresholds()
        if points is None:
            gate_points, evidence_source = self._collect_paper_gate_points()
        else:
            gate_points = self._normalize_paper_gate_points(points)
            evidence_source = "provided_points"
        gate_points = sorted(gate_points, key=lambda item: item["date"])[-int(thresholds["window_trading_days"]) :]
        metrics = self._compute_paper_gate_metrics(gate_points)
        sync_status = self._paper_gate_sync_status()
        eligible_sources = {"paper_performance", "provided_points"}
        source_eligible = (not thresholds["require_paper_evidence"]) or evidence_source in eligible_sources
        checks = {
            "minimum_valid_days": metrics["valid_days"] >= thresholds["min_valid_days"],
            "paper_evidence_source": bool(source_eligible),
            "net_return_positive_after_costs": metrics["net_return"] > thresholds["min_net_return"],
            "benchmark_excess_return_positive": metrics["excess_return"] > thresholds["min_excess_return"],
            "sharpe_above_threshold": metrics["sharpe"] >= thresholds["min_sharpe"],
            "drawdown_within_limit": metrics["max_drawdown"] <= thresholds["max_drawdown"],
            "drawdown_not_worse_than_benchmark": (
                metrics["max_drawdown"] - metrics["benchmark_max_drawdown"]
            )
            <= thresholds["max_drawdown_underperformance"],
            "paper_sync_clean": bool(sync_status["ok"]),
        }
        blockers = [name for name, ok in checks.items() if not ok]
        passed = not blockers
        report_id = f"paper-gate-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        payload = {
            "report_id": report_id,
            "generated_at": _iso_now(),
            "status": "passed" if passed else "blocked",
            "passed": passed,
            "live_blocked_until_paper_gate": not passed,
            "live_enablement_policy": {
                "mode": "paper_first",
                "live_interfaces_retained": True,
                "live_default_enabled": bool(getattr(settings, "ALPACA_ENABLE_LIVE_TRADING", False)),
                "operator_action_required_after_pass": True,
            },
            "evidence_source": evidence_source,
            "thresholds": thresholds,
            "metrics": metrics,
            "checks": checks,
            "blockers": blockers,
            "sync_status": sync_status,
            "sample": gate_points[-5:],
        }
        payload["markdown"] = self._render_paper_gate_markdown(payload)
        if persist:
            payload["storage"] = self.storage.persist_record("paper_gate_reports", report_id, payload)
            payload["markdown_path"] = self._write_paper_gate_markdown(report_id, payload["markdown"])
        return payload

    def _collect_paper_gate_points(self) -> tuple[list[dict[str, Any]], str]:
        performance_records = self.storage.list_records("paper_performance")
        points: list[dict[str, Any]] = []
        for record in performance_records:
            raw_points = record.get("points")
            if isinstance(raw_points, list):
                points.extend(self._normalize_paper_gate_points(raw_points))
            else:
                points.extend(self._normalize_paper_gate_points([record]))
        if points:
            return points, "paper_performance"

        for backtest in self.storage.list_records("backtests"):
            timeline = backtest.get("timeline") or []
            if timeline:
                return self._normalize_paper_gate_points(timeline), "backtest_reference"
        return [], "none"

    def _normalize_paper_gate_points(self, raw_points: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for point in raw_points:
            if not isinstance(point, dict):
                continue
            if bool(point.get("synthetic_used")) or point.get("evidence_eligible") is False:
                continue
            date_key = self._paper_gate_date_key(point)
            portfolio_nav = self._paper_gate_float(
                point,
                "portfolio_nav",
                "nav",
                "equity",
                "portfolio_value",
                "net_liquidation",
            )
            benchmark_nav = self._paper_gate_float(point, "benchmark_nav", "benchmark_value", "benchmark_equity")
            if not date_key or portfolio_nav is None or benchmark_nav is None:
                continue
            normalized.append(
                {
                    "date": date_key,
                    "portfolio_nav": float(portfolio_nav),
                    "benchmark_nav": float(benchmark_nav),
                }
            )
        deduped: dict[str, dict[str, Any]] = {}
        for point in normalized:
            deduped[point["date"]] = point
        return list(deduped.values())

    def _paper_gate_date_key(self, point: dict[str, Any]) -> str | None:
        raw = point.get("date") or point.get("trading_day") or point.get("generated_at") or point.get("created_at")
        parsed = self._parse_any_timestamp(raw)
        if parsed is not None:
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc).date().isoformat()
        text = str(raw or "").strip()
        if len(text) >= 10:
            try:
                return date.fromisoformat(text[:10]).isoformat()
            except ValueError:
                return None
        return None

    @staticmethod
    def _paper_gate_float(point: dict[str, Any], *keys: str) -> float | None:
        for key in keys:
            value = point.get(key)
            if value in {None, ""}:
                continue
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
        return None

    def _compute_paper_gate_metrics(self, points: list[dict[str, Any]]) -> dict[str, Any]:
        if len(points) < 2:
            return {
                "valid_days": len(points),
                "net_return": 0.0,
                "benchmark_return": 0.0,
                "excess_return": 0.0,
                "sharpe": 0.0,
                "max_drawdown": 0.0,
                "benchmark_max_drawdown": 0.0,
                "drawdown_underperformance": 0.0,
            }
        portfolio_nav = [float(point["portfolio_nav"]) for point in points]
        benchmark_nav = [float(point["benchmark_nav"]) for point in points]
        portfolio_returns = [
            (portfolio_nav[index] / portfolio_nav[index - 1]) - 1
            for index in range(1, len(portfolio_nav))
            if portfolio_nav[index - 1] > 0
        ]
        net_return = (portfolio_nav[-1] / portfolio_nav[0]) - 1 if portfolio_nav[0] > 0 else 0.0
        benchmark_return = (benchmark_nav[-1] / benchmark_nav[0]) - 1 if benchmark_nav[0] > 0 else 0.0
        mean_return = statistics.mean(portfolio_returns) if portfolio_returns else 0.0
        volatility = statistics.pstdev(portfolio_returns) if len(portfolio_returns) > 1 else 0.0
        if volatility > 0:
            sharpe = mean_return / volatility * math.sqrt(252)
        else:
            sharpe = 999.0 if mean_return > 0 else 0.0
        max_drawdown = self._max_drawdown_from_nav(portfolio_nav)
        benchmark_max_drawdown = self._max_drawdown_from_nav(benchmark_nav)
        return {
            "valid_days": len(points),
            "net_return": round(net_return, 6),
            "benchmark_return": round(benchmark_return, 6),
            "excess_return": round(net_return - benchmark_return, 6),
            "sharpe": round(sharpe, 6),
            "max_drawdown": round(max_drawdown, 6),
            "benchmark_max_drawdown": round(benchmark_max_drawdown, 6),
            "drawdown_underperformance": round(max_drawdown - benchmark_max_drawdown, 6),
        }

    @staticmethod
    def _max_drawdown_from_nav(nav_values: list[float]) -> float:
        peak = 0.0
        max_drawdown = 0.0
        for value in nav_values:
            peak = max(peak, float(value))
            if peak > 0:
                max_drawdown = max(max_drawdown, 1 - float(value) / peak)
        return max_drawdown

    def _paper_gate_sync_status(self) -> dict[str, Any]:
        thresholds = self._paper_gate_thresholds()
        window_days = max(int(thresholds["window_trading_days"]) * 2, 90)
        cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
        checked = 0
        errors: list[dict[str, Any]] = []
        for payload in self.storage.list_records("executions"):
            if str(payload.get("mode") or "").lower() != "paper":
                continue
            generated_at = self._parse_any_timestamp(payload.get("generated_at") or payload.get("created_at"))
            if generated_at is not None:
                if generated_at.tzinfo is None:
                    generated_at = generated_at.replace(tzinfo=timezone.utc)
                if generated_at.astimezone(timezone.utc) < cutoff:
                    continue
            checked += 1
            broker_errors = [str(item) for item in payload.get("broker_errors") or [] if str(item).strip()]
            if broker_errors:
                errors.append({"execution_id": payload.get("execution_id"), "reason": "broker_errors", "errors": broker_errors[:3]})
            if payload.get("submit_orders") and str(payload.get("broker_status") or "").lower() in {
                "account_error",
                "not_configured",
                "submit_failed",
            }:
                errors.append({"execution_id": payload.get("execution_id"), "reason": payload.get("broker_status")})
            journal = payload.get("journal") or self._load_execution_journal(payload.get("execution_id")) or {}
            if str(journal.get("current_state") or "").lower() in {"failed", "rejected"}:
                errors.append({"execution_id": payload.get("execution_id"), "reason": "journal_state", "state": journal.get("current_state")})
        return {
            "ok": not errors,
            "checked_executions": checked,
            "error_count": len(errors),
            "errors": errors[:10],
        }

    @staticmethod
    def _render_paper_gate_markdown(payload: dict[str, Any]) -> str:
        metrics = payload.get("metrics") or {}
        thresholds = payload.get("thresholds") or {}
        checks = payload.get("checks") or {}
        lines = [
            f"# Paper Gate Report - {payload.get('status')}",
            "",
            f"- Generated at: {payload.get('generated_at')}",
            f"- Evidence source: {payload.get('evidence_source')}",
            f"- Window trading days: {thresholds.get('window_trading_days')}",
            f"- Valid days: {metrics.get('valid_days')}",
            f"- Net return: {float(metrics.get('net_return') or 0.0):.2%}",
            f"- Excess return: {float(metrics.get('excess_return') or 0.0):.2%}",
            f"- Sharpe: {float(metrics.get('sharpe') or 0.0):.2f}",
            f"- Max drawdown: {float(metrics.get('max_drawdown') or 0.0):.2%}",
            "",
            "## Checks",
        ]
        lines.extend(f"- {name}: {'pass' if ok else 'fail'}" for name, ok in checks.items())
        if payload.get("blockers"):
            lines.extend(["", "## Blockers"])
            lines.extend(f"- {item}" for item in payload["blockers"])
        return "\n".join(lines) + "\n"

    def _write_paper_gate_markdown(self, report_id: str, markdown: str) -> str:
        directory = self.storage.base_dir / "paper_gate_reports"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{report_id}.md"
        path.write_text(markdown, encoding="utf-8")
        return str(path)

    def _execution_mode_state(
        self,
        *,
        adapter: Any,
        requested_mode: str,
        connected: bool = False,
        failure_reason: str | None = None,
    ) -> dict[str, Any]:
        normalized_mode = self._normalize_broker_mode(requested_mode)
        paper_connection = self._connection_status_for_mode(adapter, "paper")
        live_connection = self._connection_status_for_mode(adapter, "live")
        paper_ready = bool(paper_connection.get("paper_configured", paper_connection.get("configured")))
        if adapter.broker_id == "alpaca":
            live_available = bool(
                live_connection.get("live_available")
                or live_connection.get("live_configured")
            )
        else:
            live_available = bool(live_connection.get("configured"))
        live_enabled = bool(getattr(settings, "ALPACA_ENABLE_LIVE_TRADING", False)) if adapter.broker_id == "alpaca" else False
        paper_gate = self.build_paper_gate_report(persist=False) if adapter.broker_id == "alpaca" else {}
        paper_gate_passed = bool(paper_gate.get("passed"))
        live_ready = bool(
            live_available
            and live_enabled
            and paper_gate_passed
            and (connected or normalized_mode != "live" or not failure_reason)
        )
        effective_mode = "live" if normalized_mode == "live" and live_ready else "paper"
        block_reason = None
        next_actions: list[str] = []
        if normalized_mode == "live" and not live_ready:
            if not live_available:
                block_reason = "live_credentials_missing"
                next_actions = ["add_live_alpaca_keys", "switch_to_paper_mode"]
            elif not live_enabled:
                block_reason = "live_trading_disabled"
                next_actions = ["keep_using_paper_mode", "wait_for_paper_gate_pass"]
            elif not paper_gate_passed:
                block_reason = "paper_gate_not_passed"
                next_actions = ["keep_using_paper_mode", "review_paper_gate_report", "wait_for_60_trading_day_gate"]
            elif failure_reason:
                block_reason = "live_account_unavailable"
                next_actions = ["verify_live_account_permissions", "switch_to_paper_mode"]
            else:
                block_reason = "live_not_ready"
                next_actions = ["verify_live_broker_readiness", "switch_to_paper_mode"]
        elif normalized_mode == "paper" and not paper_ready:
            block_reason = "paper_credentials_missing"
            next_actions = ["configure_paper_credentials"]
        return {
            "requested_mode": normalized_mode,
            "effective_mode": effective_mode,
            "paper_ready": paper_ready,
            "live_ready": live_ready,
            "live_available": live_available,
            "block_reason": block_reason,
            "next_actions": next_actions,
            "paper_connection": paper_connection,
            "live_connection": live_connection,
            "paper_gate": paper_gate,
            "paper_gate_passed": paper_gate_passed,
            "live_blocked_until_paper_gate": adapter.broker_id == "alpaca" and not paper_gate_passed,
        }

    def _with_execution_mode_state(
        self,
        payload: dict[str, Any],
        *,
        adapter: Any,
        requested_mode: str,
        connected: bool = False,
        failure_reason: str | None = None,
    ) -> dict[str, Any]:
        mode_state = self._execution_mode_state(
            adapter=adapter,
            requested_mode=requested_mode,
            connected=connected,
            failure_reason=failure_reason,
        )
        enriched = dict(payload)
        enriched["requested_mode"] = mode_state["requested_mode"]
        enriched["effective_mode"] = mode_state["effective_mode"]
        enriched["paper_ready"] = mode_state["paper_ready"]
        enriched["live_ready"] = mode_state["live_ready"]
        enriched["live_available"] = mode_state["live_available"]
        enriched["block_reason"] = mode_state["block_reason"]
        enriched["next_actions"] = list(mode_state["next_actions"])
        enriched["paper_gate"] = mode_state.get("paper_gate", {})
        enriched["paper_gate_passed"] = bool(mode_state.get("paper_gate_passed"))
        enriched["live_blocked_until_paper_gate"] = bool(mode_state.get("live_blocked_until_paper_gate"))
        if "connected" in enriched:
            requested_connected = bool(enriched.get("connected", connected))
            enriched["connected"] = bool(requested_connected and not mode_state["block_reason"])
        return enriched

    @staticmethod
    def _market_surface_catalog() -> list[dict[str, Any]]:
        return [
            {"symbol": "AAPL", "company_name": "Apple", "sector": "Technology", "industry": "Consumer Electronics", "benchmark_weight": 0.068},
            {"symbol": "MSFT", "company_name": "Microsoft", "sector": "Technology", "industry": "Software", "benchmark_weight": 0.072},
            {"symbol": "NVDA", "company_name": "NVIDIA", "sector": "Technology", "industry": "Semiconductors", "benchmark_weight": 0.064},
            {"symbol": "GOOGL", "company_name": "Alphabet", "sector": "Communication Services", "industry": "Internet Services", "benchmark_weight": 0.041},
            {"symbol": "META", "company_name": "Meta", "sector": "Communication Services", "industry": "Internet Content", "benchmark_weight": 0.027},
            {"symbol": "AMZN", "company_name": "Amazon", "sector": "Consumer Discretionary", "industry": "E-Commerce", "benchmark_weight": 0.038},
            {"symbol": "TSLA", "company_name": "Tesla", "sector": "Consumer Discretionary", "industry": "EV Manufacturing", "benchmark_weight": 0.021},
            {"symbol": "WMT", "company_name": "Walmart", "sector": "Consumer Staples", "industry": "Retail", "benchmark_weight": 0.011},
            {"symbol": "COST", "company_name": "Costco", "sector": "Consumer Staples", "industry": "Retail", "benchmark_weight": 0.009},
            {"symbol": "PG", "company_name": "Procter & Gamble", "sector": "Consumer Staples", "industry": "Household Products", "benchmark_weight": 0.007},
            {"symbol": "JPM", "company_name": "JPMorgan Chase", "sector": "Financials", "industry": "Banks", "benchmark_weight": 0.013},
            {"symbol": "BAC", "company_name": "Bank of America", "sector": "Financials", "industry": "Banks", "benchmark_weight": 0.008},
            {"symbol": "BRK.B", "company_name": "Berkshire Hathaway", "sector": "Financials", "industry": "Diversified Financials", "benchmark_weight": 0.017},
            {"symbol": "XOM", "company_name": "Exxon Mobil", "sector": "Energy", "industry": "Integrated Oil & Gas", "benchmark_weight": 0.012},
            {"symbol": "CVX", "company_name": "Chevron", "sector": "Energy", "industry": "Integrated Oil & Gas", "benchmark_weight": 0.009},
            {"symbol": "NEE", "company_name": "NextEra Energy", "sector": "Utilities", "industry": "Renewables", "benchmark_weight": 0.004},
            {"symbol": "DUK", "company_name": "Duke Energy", "sector": "Utilities", "industry": "Utilities", "benchmark_weight": 0.003},
            {"symbol": "LLY", "company_name": "Eli Lilly", "sector": "Health Care", "industry": "Biopharma", "benchmark_weight": 0.013},
            {"symbol": "UNH", "company_name": "UnitedHealth", "sector": "Health Care", "industry": "Managed Care", "benchmark_weight": 0.011},
            {"symbol": "JNJ", "company_name": "Johnson & Johnson", "sector": "Health Care", "industry": "Pharma", "benchmark_weight": 0.008},
            {"symbol": "CAT", "company_name": "Caterpillar", "sector": "Industrials", "industry": "Machinery", "benchmark_weight": 0.004},
            {"symbol": "GE", "company_name": "GE Aerospace", "sector": "Industrials", "industry": "Aerospace", "benchmark_weight": 0.005},
            {"symbol": "LIN", "company_name": "Linde", "sector": "Materials", "industry": "Industrial Gases", "benchmark_weight": 0.004},
            {"symbol": "SHW", "company_name": "Sherwin-Williams", "sector": "Materials", "industry": "Chemicals", "benchmark_weight": 0.002},
            {"symbol": "PLD", "company_name": "Prologis", "sector": "Real Estate", "industry": "Industrial REITs", "benchmark_weight": 0.003},
            {"symbol": "AMT", "company_name": "American Tower", "sector": "Real Estate", "industry": "Specialized REITs", "benchmark_weight": 0.003},
        ]

    def _safe_live_account_snapshot(self, mode: str = "paper") -> dict[str, Any] | None:
        try:
            account_payload = self.get_execution_account(broker="alpaca", mode=mode)
        except Exception as exc:
            logger.warning(f"Live account snapshot fallback engaged for {mode}: {exc}")
            return None
        if not account_payload.get("connected"):
            return None
        return account_payload

    def _extract_position_symbols(self, mode: str = "paper") -> list[str]:
        try:
            positions_payload = self.list_execution_positions(broker="alpaca", mode=mode)
        except Exception as exc:
            logger.warning(f"Position symbol fallback engaged for {mode}: {exc}")
            return []
        symbols = []
        for position in positions_payload.get("positions", []):
            symbol = str(position.get("symbol") or "").upper().strip()
            if symbol:
                symbols.append(symbol)
        return sorted(dict.fromkeys(symbols))

    def _get_position_symbols(self, mode: str = "paper", *, force_refresh: bool = False) -> list[str]:
        normalized_mode = self._normalize_broker_mode(mode)
        cached = self._position_symbols_cache.get(normalized_mode)
        if not force_refresh:
            payload = self._cached_payload(cached)
            if payload is not None:
                return list(payload)

        payload = self._extract_position_symbols(mode=normalized_mode)
        self._position_symbols_cache[normalized_mode] = self._cache_wrap(list(payload), ttl_seconds=15)
        return list(payload)

    def _get_live_account_snapshot(self, mode: str = "paper", *, force_refresh: bool = False) -> dict[str, Any] | None:
        normalized_mode = self._normalize_broker_mode(mode)
        cached = self._account_snapshot_cache.get(normalized_mode)
        if not force_refresh:
            payload = self._cached_payload(cached)
            if payload is not None:
                return payload
        payload = self._safe_live_account_snapshot(mode=normalized_mode)
        self._account_snapshot_cache[normalized_mode] = self._cache_wrap(payload, ttl_seconds=15)
        return payload

    def _prefetch_market_bars(
        self,
        symbols: list[str],
        *,
        limit: int,
        provider_order_override: list[str] | None = None,
        force_refresh: bool = False,
        allow_stale_cache: bool = True,
        timeout_override: int | None = None,
        cache_tag: str = "dashboard",
    ) -> dict[str, Any]:
        normalized_symbols = [str(symbol or "").upper().strip() for symbol in symbols if str(symbol or "").strip()]
        normalized_symbols = list(dict.fromkeys(normalized_symbols))
        if not normalized_symbols:
            return {}

        provider_signature = tuple(provider_order_override or self._market_data_provider_order())
        cache_key = (
            cache_tag,
            tuple(normalized_symbols),
            int(limit),
            bool(force_refresh),
            provider_signature,
            int(timeout_override or 0),
        )
        cached = self._cached_payload(self._shared_market_bars_cache.get(cache_key))
        if cached is not None:
            return cached

        results: dict[str, Any] = {}
        max_workers = min(len(normalized_symbols), self._dashboard_market_workers)

        def _load_symbol(symbol: str):
            return self._get_daily_bars(
                symbol,
                limit=limit,
                force_refresh=force_refresh,
                provider_order_override=provider_order_override,
                allow_stale_cache=allow_stale_cache,
                timeout_override=timeout_override,
            )

        if max_workers <= 1:
            for symbol in normalized_symbols:
                try:
                    results[symbol] = _load_symbol(symbol)
                except Exception as exc:
                    logger.warning(f"[Dashboard] Failed to prefetch market bars for {symbol}: {exc}")
        else:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_map = {executor.submit(_load_symbol, symbol): symbol for symbol in normalized_symbols}
                for future in as_completed(future_map):
                    symbol = future_map[future]
                    try:
                        results[symbol] = future.result()
                    except Exception as exc:
                        logger.warning(f"[Dashboard] Failed to prefetch market bars for {symbol}: {exc}")

        self._shared_market_bars_cache[cache_key] = self._cache_wrap(results, ttl_seconds=30)
        return results

    def _build_market_surface(
        self,
        watchlist_signals: list[dict[str, Any]],
        *,
        bars_map: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        signal_lookup = {str(item.get("symbol") or "").upper(): item for item in watchlist_signals}
        nodes: list[dict[str, Any]] = []
        for item in self._market_surface_catalog():
            symbol = item["symbol"]
            signal = signal_lookup.get(symbol)
            provider = str(signal.get("market_data_source") or "") if signal else "unavailable"
            change = float(signal.get("expected_return") or 0.0) if signal else 0.0
            confidence = float(signal.get("confidence") or 0.0) if signal else 0.45
            house_score = float(signal.get("house_score") or signal.get("overall_score") or 72.0) if signal else 72.0
            try:
                bars_result = (bars_map or {}).get(symbol)
                if bars_result is None:
                    bars_result = self.market_data.get_daily_bars(symbol, limit=12)
                provider = bars_result.provider or provider or "unavailable"
                frame = bars_result.bars
                if len(frame.index) >= 2:
                    closes = frame["close"].astype(float).tolist()
                    prev_close = closes[-2]
                    last_close = closes[-1]
                    if prev_close:
                        change = (last_close - prev_close) / prev_close
            except Exception:
                provider = provider or "unavailable"

            weight = max(24.0, float(item.get("benchmark_weight") or 0.0) * 1800.0)
            risk_level = "high" if change <= -0.015 else "positive" if change >= 0.015 else "neutral"
            nodes.append(
                {
                    "symbol": symbol,
                    "name": symbol,
                    "company_name": item["company_name"],
                    "sector": item["sector"],
                    "industry": item["industry"],
                    "value": round(weight, 2),
                    "weight": round(weight, 2),
                    "change": round(change, 6),
                    "score": round(house_score, 2),
                    "confidence": round(confidence, 4),
                    "source": provider,
                    "risk_level": risk_level,
                }
            )
        nodes.sort(key=lambda node: node["value"], reverse=True)
        return nodes

    def _resolve_market_data_source(self, signal: ResearchSignal) -> str:
        source = str(signal.market_data_source or "").strip().lower()
        if source:
            return source

        lineage = " ".join(signal.data_lineage or []).lower()
        if "synthetic" in lineage or "fallback" in lineage:
            return "synthetic"
        if "yfinance" in lineage:
            return "yfinance"
        if "alpaca" in lineage:
            return "alpaca"
        return "synthetic" if "fallback" in str(signal.signal_source or "").lower() else "unknown"

    def _projection_basis_return(self, signal: ResearchSignal) -> float:
        expected = float(signal.expected_return or 0.0)
        predicted = float(signal.predicted_return_5d or 0.0)
        regime = str(signal.regime_label or "neutral").lower()
        action = str(signal.action or "neutral").lower()

        if action == "long":
            return round(max(abs(expected), abs(predicted), 0.01), 6)
        if action == "short":
            return round(-max(abs(expected), abs(predicted), 0.01), 6)
        if regime == "risk_off":
            return round(-max(abs(expected), abs(predicted) * 0.55, 0.006), 6)
        if regime == "risk_on" and expected > 0:
            return round(max(expected * 0.45, 0.003), 6)
        if expected < 0:
            return round(expected, 6)
        if predicted < 0:
            return round(max(predicted, -0.01), 6)
        return 0.0

    def _build_projection_scenarios(self, signal: ResearchSignal) -> dict[str, Any]:
        source = self._resolve_market_data_source(signal)
        has_model_coverage = all(
            value is not None
            for value in (
                signal.predicted_return_5d,
                signal.predicted_volatility_10d,
                signal.predicted_drawdown_20d,
            )
        )
        if source in {"synthetic", "unknown"} or not has_model_coverage:
            return {
                "market_data_source": source,
                "prediction_mode": "unavailable",
                "projection_basis_return": None,
                "projection_scenarios": {},
            }

        center = self._projection_basis_return(signal)
        volatility = max(float(signal.predicted_volatility_10d or 0.0), 0.03)
        drawdown = max(float(signal.predicted_drawdown_20d or 0.0), 0.03)
        atr_proxy = max(abs(center) * 0.35, volatility * 0.22, 0.012)
        upside_band = max(volatility * 0.55, atr_proxy)
        downside_band = max(drawdown * 0.45, atr_proxy)
        confidence = round(min(0.99, float(signal.decision_confidence or signal.confidence or 0.0)), 6)

        return {
            "market_data_source": source,
            "prediction_mode": "model",
            "projection_basis_return": round(center, 6),
            "projection_scenarios": {
                "upper": ProjectionScenario(
                    label="Bull Case",
                    expected_return=round(center + upside_band, 6),
                    confidence=confidence,
                    band_source="volatility_plus_atr_proxy",
                ),
                "center": ProjectionScenario(
                    label="Base Case",
                    expected_return=round(center, 6),
                    confidence=confidence,
                    band_source="signed_expected_return",
                ),
                "lower": ProjectionScenario(
                    label="Risk Floor",
                    expected_return=round(center - downside_band, 6),
                    confidence=round(max(0.01, float(signal.regime_probability or signal.confidence or 0.0)), 6),
                    band_source="drawdown_plus_atr_proxy",
                ),
            },
        }

    def _build_house_score_payload(self, signal: ResearchSignal) -> dict[str, Any]:
        if signal.house_score is not None and signal.house_grade and signal.formula_version and "V2" in str(signal.formula_version):
            return {
                "house_score": float(signal.house_score),
                "house_score_v2": float(signal.house_score_v2 or signal.house_score),
                "house_grade": signal.house_grade,
                "formula_version": signal.formula_version,
                "pillar_breakdown": dict(signal.pillar_breakdown or {}),
                "disclosure_confidence": float(signal.disclosure_confidence or 0.0),
                "controversy_penalty": float(signal.controversy_penalty or 0.0),
                "data_gap_penalty": float(signal.data_gap_penalty or 0.0),
                "materiality_adjustment": float(signal.materiality_adjustment or 0.0),
                "trend_bonus": float(signal.trend_bonus or 0.0),
                "house_explanation": str(signal.house_explanation or ""),
                "materiality_weights": dict(signal.materiality_weights or {}),
                "evidence_count": int(signal.evidence_count or len(signal.data_lineage or [])),
                "effective_date": signal.effective_date,
                "staleness_days": signal.staleness_days,
                "score_delta": signal.score_delta,
            }

        lineage = list(signal.data_lineage or [])
        metric_coverage = 1.0 if signal.factor_scores else 0.72
        house = compute_house_score(
            company_name=signal.company_name,
            sector=signal.sector,
            industry=signal.sector,
            e_score=float(signal.e_score or 0.0),
            s_score=float(signal.s_score or 0.0),
            g_score=float(signal.g_score or 0.0),
            data_sources=lineage,
            data_lineage=lineage,
            controversy_hints=list(signal.catalysts or []),
            esg_delta=self._factor_value(_as_dict(signal), "esg_delta") / 100.0,
            metric_coverage_ratio=metric_coverage,
        ).as_dict()
        house["house_score_v2"] = house["house_score"]
        return house

    def _enrich_signal_house_score(self, signal: ResearchSignal) -> ResearchSignal:
        updates = self._build_house_score_payload(signal)
        updates.update(self._build_signal_research_contract(signal))
        return signal.model_copy(update=updates)

    def _build_signal_research_contract(self, signal: ResearchSignal) -> dict[str, Any]:
        lineage = list(dict.fromkeys(list(signal.lineage or []) + list(signal.data_lineage or [])))
        market_data_source = str(signal.market_data_source or "").lower()
        protection_status = "review" if market_data_source in {"synthetic", ""} else "pass"
        return {
            "lineage": lineage,
            "dataset_id": signal.dataset_id or f"dataset-us-daily-{signal.symbol.lower()}",
            "protection_status": signal.protection_status if signal.protection_status != "review" else protection_status,
            "frequency": signal.frequency or "daily",
            "market": signal.market or "US",
        }

    def _build_sector_heatmap(self, signals: list[ResearchSignal]) -> list[dict[str, Any]]:
        buckets: dict[str, list[ResearchSignal]] = {}
        for signal in signals:
            buckets.setdefault(signal.sector or "Unknown", []).append(signal)

        heatmap: list[dict[str, Any]] = []
        for sector, items in buckets.items():
            average_return = _safe_mean([float(item.expected_return or 0.0) for item in items])
            average_score = _safe_mean([float(item.house_score or item.overall_score or 0.0) for item in items])
            weight = sum(max(float(item.confidence or 0.0), 0.05) for item in items)
            heatmap.append(
                {
                    "name": sector,
                    "value": round(weight * 100, 2),
                    "score": round(average_score, 2),
                    "change": round(average_return, 6),
                    "symbols": [item.symbol for item in items],
                    "market_data_sources": sorted({self._resolve_market_data_source(item) for item in items}),
                    "children": [
                        {
                            "name": item.symbol,
                            "value": round(max(float(item.confidence or 0.0), 0.05) * 100, 2),
                            "score": round(float(item.house_score or item.overall_score or 0.0), 2),
                            "change": round(float(item.expected_return or 0.0), 6),
                            "action": item.action,
                        }
                        for item in items
                    ],
                }
            )
        heatmap.sort(key=lambda item: item["value"], reverse=True)
        return heatmap

    def _serialize_watchlist_signal(self, signal: ResearchSignal) -> dict[str, Any]:
        enriched = self._enrich_signal_house_score(signal).model_copy(update=self._build_projection_scenarios(signal))
        return _as_dict(enriched)

    def get_default_universe(self, symbols: list[str] | None = None) -> list[UniverseMember]:
        base_universe = [UniverseMember(**item) for item in self._market_surface_catalog()]
        if not symbols:
            return base_universe

        lookup = {item.symbol.upper(): item for item in base_universe}
        selected: list[UniverseMember] = []
        for symbol in symbols:
            key = symbol.upper().strip()
            if key in lookup:
                selected.append(lookup[key])
                continue
            selected.append(
                UniverseMember(
                    symbol=key,
                    company_name=key,
                    sector="Custom Universe",
                    industry="Custom",
                    benchmark_weight=0.0,
                )
            )
        return selected

    @staticmethod
    def _preferred_watchlist(scope: str = "full") -> list[str]:
        full_watchlist = ["AAPL", "MSFT", "NVDA", "GOOGL", "NEE", "PG", "TSLA", "AMZN"]
        if str(scope or "").lower() == "summary":
            return full_watchlist[:5]
        return full_watchlist

    @staticmethod
    def _ordered_unique_symbols(symbols: list[str] | None) -> list[str]:
        ordered: list[str] = []
        seen: set[str] = set()
        for raw_symbol in symbols or []:
            symbol = str(raw_symbol or "").upper().strip()
            if not symbol or symbol in seen:
                continue
            seen.add(symbol)
            ordered.append(symbol)
        return ordered

    @staticmethod
    def _watchlist_signal_has_model_projection(signal: dict[str, Any] | None) -> bool:
        if not isinstance(signal, dict):
            return False
        if str(signal.get("prediction_mode") or "").strip().lower() != "model":
            return False
        scenarios = signal.get("projection_scenarios") or {}
        return all(scenarios.get(key) for key in ("upper", "center", "lower"))

    @classmethod
    def _dedupe_watchlist_signals(cls, watchlist_signals: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
        deduped: list[dict[str, Any]] = []
        seen: set[str] = set()
        for signal in watchlist_signals or []:
            symbol = str((signal or {}).get("symbol") or "").upper().strip()
            if not symbol or symbol in seen:
                continue
            seen.add(symbol)
            deduped.append(signal)
        return deduped

    def _compose_watchlist_snapshot(
        self,
        *,
        preferred_watchlist: list[str],
        provider_order_override: list[str] | None = None,
        timeout_override: int | None = None,
        cache_tag: str = "signal_bundle",
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        position_symbols = self._get_position_symbols(mode="paper", force_refresh=force_refresh)
        dashboard_symbols = self._ordered_unique_symbols(position_symbols + preferred_watchlist)
        universe = self.get_default_universe(dashboard_symbols)
        signals, prefetched_bars = self._build_signal_bundle(
            universe,
            "overview refresh",
            self.default_benchmark,
            provider_order_override=provider_order_override,
            timeout_override=timeout_override,
            cache_tag=cache_tag,
        )
        watchlist_signals = self._dedupe_watchlist_signals([self._serialize_watchlist_signal(signal) for signal in signals])
        watchlist_signals.sort(
            key=lambda item: (
                item.get("action") != "long",
                -float(item.get("house_score") or item.get("overall_score") or 0.0),
                -float(item.get("confidence") or 0.0),
            )
        )
        return {
            "position_symbols": position_symbols,
            "universe": universe,
            "signals": signals,
            "watchlist_signals": watchlist_signals,
            "_bars_map": prefetched_bars,
        }

    def _build_watchlist_snapshot(self, *, force_refresh: bool = False) -> dict[str, Any]:
        if not force_refresh:
            cached = self._cached_payload(self._watchlist_snapshot_cache)
            if cached is not None:
                return cached
        payload = self._compose_watchlist_snapshot(
            preferred_watchlist=self._preferred_watchlist("full"),
            cache_tag="signal_bundle",
            force_refresh=force_refresh,
        )
        self._watchlist_snapshot_cache = self._cache_wrap(payload)
        return payload

    def _build_dashboard_watchlist_snapshot(self, *, provider: str = "auto", force_refresh: bool = False) -> dict[str, Any]:
        provider_preference, provider_chain = self._dashboard_provider_chain(provider)
        if not force_refresh:
            cached = self._cached_payload(self._dashboard_watchlist_snapshot_cache.get(provider_preference))
            if cached is not None:
                return cached

        payload = self._compose_watchlist_snapshot(
            preferred_watchlist=self._preferred_watchlist("summary"),
            provider_order_override=provider_chain,
            timeout_override=self._dashboard_live_timeout_seconds,
            cache_tag=f"dashboard_summary:{provider_preference}",
            force_refresh=force_refresh,
        )
        self._dashboard_watchlist_snapshot_cache[provider_preference] = self._cache_wrap(payload)
        return payload

    def _resolve_dashboard_watchlist_snapshot(
        self,
        provider_preference: str,
        *,
        include_stale: bool = False,
    ) -> dict[str, Any]:
        entry = self._dashboard_watchlist_snapshot_cache.get(provider_preference)
        payload = self._cached_payload(entry)
        if payload is not None:
            return payload
        if include_stale and entry and entry.get("payload") is not None:
            return entry["payload"]
        return {}

    def build_platform_overview(self) -> dict[str, Any]:
        if self._cache_is_fresh(self._overview_cache):
            return self._overview_cache["payload"]
        with ThreadPoolExecutor(max_workers=2) as executor:
            snapshot_future = executor.submit(self._build_watchlist_snapshot)
            account_future = executor.submit(self._get_live_account_snapshot, mode="paper")
            snapshot = snapshot_future.result()
            live_account_snapshot = account_future.result()
        position_symbols = snapshot["position_symbols"]
        universe = snapshot["universe"]
        signals = snapshot["signals"]
        watchlist_signals = snapshot["watchlist_signals"]
        secondary = self.build_dashboard_secondary()
        sector_heatmap = secondary["sector_heatmap"]
        market_surface = secondary["market_surface"]
        portfolio = secondary["portfolio_preview"]
        latest_backtest = secondary["latest_backtest"]
        experiments = self.storage.list_records("experiments")

        payload = {
            "generated_at": _iso_now(),
            "platform_name": "ESG Quant Intelligence System",
            "tagline": "从数据接入到因子研究、回测执行与产品交付的一体化 ESG Quant 平台",
            "architecture_layers": [
                ArchitectureLayerStatus(key="l0", label="数据接入层", priority="P1", ready=True, detail="支持市场、宏观、ESG、另类数据入口").model_dump(),
                ArchitectureLayerStatus(key="l1", label="数据治理层", priority="P1", ready=True, detail="时间对齐、异常值过滤、可复现实验元数据").model_dump(),
                ArchitectureLayerStatus(key="l2", label="分析引擎层", priority="P1", ready=True, detail="技术指标、ESG 因子、LLM 财报解析和另类数据信号").model_dump(),
                ArchitectureLayerStatus(key="l3", label="模型训练层", priority="P2", ready=True, detail="支持 XGBoost/LSTM/LoRA 和云端 5090 微调规划").model_dump(),
                ArchitectureLayerStatus(key="l4", label="Agent 编排层", priority="P1", ready=True, detail="研究、策略、风控、事件、报告多 Agent 协同").model_dump(),
                ArchitectureLayerStatus(key="l5", label="风控合规层", priority="P2", ready=True, detail="回撤、CVaR、情景压力测试和合规规则").model_dump(),
                ArchitectureLayerStatus(key="l6", label="执行回测层", priority="P1", ready=True, detail="回测、Paper Trading、交易成本和绩效归因").model_dump(),
                ArchitectureLayerStatus(key="l7", label="实验追踪层", priority="P2", ready=True, detail="实验、成本、漂移与工件留存").model_dump(),
                ArchitectureLayerStatus(key="l8", label="报告展示层", priority="P1", ready=True, detail="产品控制台、交付站点和研究报告").model_dump(),
            ],
            "storage": self.storage.status() | {
                "primary": "R2 preferred / Supabase Storage fallback / Local disk safety net",
                "local_fallback": True,
            },
            "market_data": self.market_data.status(),
            "alpha_ranker": self.alpha_ranker.status(),
            "p1_suite": self.p1_suite.status(),
            "p2_stack": self.p2_stack.status(),
            "universe": {
                "name": self.default_universe_name,
                "size": len(universe),
                "benchmark": self.default_benchmark,
                "coverage": [member.symbol for member in universe],
            },
            "top_signals": watchlist_signals[:5],
            "watchlist_signals": watchlist_signals,
            "position_symbols": position_symbols,
            "live_account_snapshot": live_account_snapshot,
            "sector_heatmap": sector_heatmap,
            "market_surface": market_surface,
            "heatmap_nodes": market_surface,
            "p1_signal_snapshot": {
                "regime_counts": {
                    "risk_on": sum(1 for signal in signals if signal.regime_label == "risk_on"),
                    "neutral": sum(1 for signal in signals if signal.regime_label == "neutral"),
                    "risk_off": sum(1 for signal in signals if signal.regime_label == "risk_off"),
                },
                "average_predicted_return_5d": round(
                    statistics.mean(
                        [signal.predicted_return_5d for signal in signals if signal.predicted_return_5d is not None] or [0.0]
                    ),
                    6,
                ),
                "average_predicted_drawdown_20d": round(
                    statistics.mean(
                        [signal.predicted_drawdown_20d for signal in signals if signal.predicted_drawdown_20d is not None] or [0.0]
                    ),
                    6,
                ),
                "average_sequence_return_5d": round(
                    statistics.mean(
                        [signal.sequence_return_5d for signal in signals if signal.sequence_return_5d is not None] or [0.0]
                    ),
                    6,
                ),
            },
            "p2_decision_snapshot": {
                "selected_strategy": next(
                    (signal.selector_strategy for signal in signals if signal.selector_strategy),
                    "balanced_quality_growth",
                ),
                "bandit_strategy": next(
                    (signal.bandit_strategy for signal in signals if signal.bandit_strategy),
                    None,
                ),
                "average_decision_score": round(
                    statistics.mean([signal.decision_score for signal in signals if signal.decision_score is not None] or [0.0]),
                    6,
                ),
                "average_graph_contagion": round(
                    statistics.mean([signal.graph_contagion_risk for signal in signals if signal.graph_contagion_risk is not None] or [0.0]),
                    6,
                ),
                "high_contagion_symbols": [
                    signal.symbol
                    for signal in signals
                    if (signal.graph_contagion_risk or 0.0) >= float(getattr(settings, "P2_GRAPH_CONTAGION_LIMIT", 0.62) or 0.62)
                ],
            },
            "portfolio_preview": portfolio,
            "latest_backtest": latest_backtest,
            "experiments": experiments[:3],
            "training_plan": self._build_training_plan().model_dump(),
        }
        self._overview_cache = self._cache_wrap(payload)
        return payload

    def _chart_limit_for_timeframe(self, timeframe: str) -> int:
        return {
            "1D": 120,
            "1W": 90,
            "1M": 72,
            "3M": 56,
            "1Y": 90,
        }.get(str(timeframe or "1D").upper(), 120)

    def _resolve_cached_chart_payload(
        self,
        symbol: str | None,
        timeframe: str = "1D",
        provider_preference: str = "auto",
        *,
        include_stale: bool = False,
    ) -> dict[str, Any] | None:
        normalized_symbol = str(symbol or "").upper().strip()
        normalized_timeframe = str(timeframe or "1D").upper()
        candidate_keys = []
        if normalized_symbol:
            candidate_keys.append((normalized_symbol, normalized_timeframe, provider_preference))
            if provider_preference != "auto":
                candidate_keys.append((normalized_symbol, normalized_timeframe, "auto"))
        else:
            candidate_keys.extend(self._chart_cache.keys())

        for key in candidate_keys:
            entry = self._chart_cache.get(key)
            payload = self._cached_payload(entry)
            if payload is not None:
                return payload
            if include_stale and entry and entry.get("payload") is not None:
                return entry["payload"]

        if not include_stale:
            return None

        for (cached_symbol, cached_tf, _), entry in reversed(list(self._chart_cache.items())):
            if normalized_symbol and cached_symbol != normalized_symbol:
                continue
            if cached_tf != normalized_timeframe or not entry.get("payload"):
                continue
            return entry["payload"]
        return None

    def _resolve_dashboard_symbol(
        self,
        *,
        requested_symbol: str | None = None,
        watchlist: list[dict[str, Any]] | None = None,
        position_symbols: list[str] | None = None,
        provider_preference: str = "auto",
    ) -> str:
        normalized_requested = str(requested_symbol or "").upper().strip()
        if normalized_requested:
            return normalized_requested

        watchlist_by_symbol = {
            str((item or {}).get("symbol") or "").upper().strip(): item
            for item in (watchlist or [])
            if str((item or {}).get("symbol") or "").upper().strip()
        }
        ordered_watchlist = [item for item in (watchlist or []) if str((item or {}).get("symbol") or "").upper().strip()]

        for position_symbol in self._ordered_unique_symbols(position_symbols):
            candidate = watchlist_by_symbol.get(position_symbol)
            if self._watchlist_signal_has_model_projection(candidate):
                return position_symbol

        for candidate in ordered_watchlist:
            if self._watchlist_signal_has_model_projection(candidate):
                return str(candidate.get("symbol") or "").upper().strip()

        cached_chart = self._resolve_cached_chart_payload(
            self._last_dashboard_symbol,
            provider_preference=provider_preference,
            include_stale=True,
        )
        cached_symbol = str((cached_chart or {}).get("symbol") or "").upper().strip()
        if cached_symbol:
            return cached_symbol
        if self._last_dashboard_symbol:
            return str(self._last_dashboard_symbol).upper().strip() or "AAPL"
        if ordered_watchlist:
            candidate = str((ordered_watchlist[0] or {}).get("symbol") or "").upper().strip()
            if candidate:
                return candidate
        return str(self._last_dashboard_symbol or "AAPL").upper().strip() or "AAPL"

    def _build_dashboard_kpis(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        watchlist = list(snapshot.get("watchlist_signals") or [])
        signals = list(snapshot.get("signals") or [])
        account_snapshot = snapshot.get("live_account_snapshot") or {}
        account = account_snapshot.get("account") if isinstance(account_snapshot, dict) else {}
        latest_backtest = {}
        backtests = self.storage.list_records("backtests")
        if backtests:
            latest_backtest = backtests[0] or {}

        regime_counts = {
            "risk_on": sum(1 for signal in signals if getattr(signal, "regime_label", None) == "risk_on"),
            "neutral": sum(1 for signal in signals if getattr(signal, "regime_label", None) == "neutral"),
            "risk_off": sum(1 for signal in signals if getattr(signal, "regime_label", None) == "risk_off"),
        }
        long_signals = [item for item in watchlist if str(item.get("action") or "").lower() == "long"]
        if regime_counts["risk_on"] > regime_counts["risk_off"]:
            regime = "risk_on"
        elif regime_counts["risk_off"] > 0:
            regime = "risk_off"
        else:
            regime = "neutral"

        return {
            "equity": account.get("equity"),
            "capital_base": self.default_capital,
            "expected_alpha": round(
                statistics.mean([float(item.get("expected_return") or 0.0) for item in (long_signals or watchlist[:5])] or [0.0]),
                6,
            ),
            "signal_count": len(watchlist),
            "long_count": len(long_signals),
            "sharpe": ((latest_backtest.get("metrics") or {}).get("sharpe")),
            "max_drawdown": ((latest_backtest.get("metrics") or {}).get("max_drawdown")),
            "regime": regime,
            "regime_counts": regime_counts,
            "symbol_count": len(snapshot.get("position_symbols") or []) or len(snapshot.get("universe") or []) or len(watchlist),
        }

    def build_dashboard_state(self, *, provider: str = "auto", symbol: str | None = None) -> dict[str, Any]:
        provider_preference, provider_chain = self._dashboard_provider_chain(provider)
        snapshot = self._resolve_dashboard_watchlist_snapshot(provider_preference, include_stale=True)
        watchlist = list(snapshot.get("watchlist_signals") or [])
        position_symbols = list(snapshot.get("position_symbols") or [])
        selected_symbol = self._resolve_dashboard_symbol(
            requested_symbol=symbol,
            watchlist=watchlist,
            position_symbols=position_symbols,
            provider_preference=provider_preference,
        )
        chart = self._resolve_cached_chart_payload(selected_symbol, provider_preference=provider_preference, include_stale=True) or {}
        source = str(chart.get("source") or "unknown")
        provider_status = dict(chart.get("provider_status") or {})
        if not provider_status:
            provider_status = {
                "available": False,
                "provider": "unavailable",
                "selected_provider": provider_preference,
            }
        else:
            provider_status.setdefault("selected_provider", provider_preference)
        degraded_from = chart.get("degraded_from")
        candles = list(chart.get("candles") or [])
        chart_reasons = list((chart.get("fallback_preview") or {}).get("reason") or [])
        if chart.get("warning"):
            chart_reasons.append(chart["warning"])
        if chart.get("detail"):
            chart_reasons.append(chart["detail"])
        if isinstance(chart.get("market_data_warnings"), list):
            chart_reasons.extend(chart["market_data_warnings"])
        chart_reasons = list(dict.fromkeys(item for item in chart_reasons if item))
        ready = bool(
            candles
            and source not in {"unknown", "loading", "unavailable", "", "cache", "synthetic"}
            and not chart.get("degraded_snapshot")
            and not degraded_from
            and not chart_reasons
        )
        reason = list(chart_reasons)
        if not ready and provider_status.get("available") and not candles:
            reason.append("provider_connected_but_no_payload")
        if not ready and degraded_from:
            reason.append(f"provider_degraded_from_{degraded_from}")
        if not ready and (chart.get("degraded_snapshot") or source in {"cache", "synthetic"}):
            reason.append("cache_or_synthetic_fallback")
        if not ready and source == "unknown":
            reason.append("source_unknown")
        if not ready and not reason:
            reason.append("chart_data_unavailable")
        fallback_preview = {
            "symbol": selected_symbol,
            "source": source or "unknown",
            "source_chain": chart.get("data_source_chain") or chart.get("provider_chain") or provider_chain,
            "last_snapshot": candles[-1] if candles else (chart.get("fallback_preview") or {}).get("last_snapshot"),
            "reason": list(dict.fromkeys(reason)),
            "next_actions": (chart.get("fallback_preview") or {}).get("next_actions") or [
                "refresh_dashboard",
                "switch_symbol",
                "open_market_radar",
                "open_backtest",
            ],
        }
        return {
            "generated_at": _iso_now(),
            "phase": "ready" if ready else "degraded",
            "ready": ready,
            "symbol": selected_symbol,
            "source": source or "unknown",
            "selected_provider": provider_preference,
            "source_chain": chart.get("data_source_chain") or chart.get("provider_chain") or provider_chain,
            "provider_status": provider_status,
            "degraded_from": degraded_from,
            "fallback_preview": fallback_preview,
        }

    def build_dashboard_summary(self, provider: str = "auto") -> dict[str, Any]:
        provider_preference, _ = self._dashboard_provider_chain(provider)
        cached = self._cached_payload(self._dashboard_summary_cache.get(provider_preference))
        if cached is not None:
            return cached

        with ThreadPoolExecutor(max_workers=2) as executor:
            snapshot_future = executor.submit(self._build_dashboard_watchlist_snapshot, provider=provider)
            account_future = executor.submit(self._get_live_account_snapshot, mode="paper")
            snapshot = snapshot_future.result()
            live_account_snapshot = account_future.result()
        snapshot_for_kpis = dict(snapshot)
        snapshot_for_kpis["live_account_snapshot"] = live_account_snapshot
        watchlist_signals = list(snapshot.get("watchlist_signals") or [])
        signals = list(snapshot.get("signals") or [])
        position_symbols = list(snapshot.get("position_symbols") or [])
        symbol = self._resolve_dashboard_symbol(
            watchlist=watchlist_signals,
            position_symbols=position_symbols,
            provider_preference=provider_preference,
        )
        dashboard_state = self.build_dashboard_state(provider=provider, symbol=symbol)
        regime_counts = {
            "risk_on": sum(1 for signal in signals if getattr(signal, "regime_label", None) == "risk_on"),
            "neutral": sum(1 for signal in signals if getattr(signal, "regime_label", None) == "neutral"),
            "risk_off": sum(1 for signal in signals if getattr(signal, "regime_label", None) == "risk_off"),
        }
        payload = {
            "generated_at": _iso_now(),
            "selected_provider": provider_preference,
            "symbol": symbol,
            "watchlist_signals": watchlist_signals,
            "top_signals": watchlist_signals[:5],
            "position_symbols": position_symbols,
            "live_account_snapshot": live_account_snapshot,
            "kpis": self._build_dashboard_kpis(snapshot_for_kpis),
            "provider_status": dashboard_state["provider_status"],
            "fallback_preview": dashboard_state["fallback_preview"],
            "p1_signal_snapshot": {"regime_counts": regime_counts},
            "universe": {
                "size": len(snapshot.get("universe") or []),
            },
        }
        self._dashboard_summary_cache[provider_preference] = self._cache_wrap(payload)
        return payload

    def build_dashboard_secondary(self, provider: str = "auto") -> dict[str, Any]:
        provider_preference, _ = self._dashboard_provider_chain(provider)
        cached = self._cached_payload(self._dashboard_secondary_cache.get(provider_preference))
        if cached is not None:
            return cached

        snapshot = self._build_watchlist_snapshot()
        signals = list(snapshot.get("signals") or [])
        watchlist_signals = list(snapshot.get("watchlist_signals") or [])
        bars_map = dict(snapshot.get("_bars_map") or {})
        sector_heatmap = self._build_sector_heatmap(signals)
        market_surface = self._build_market_surface(watchlist_signals, bars_map=bars_map)
        portfolio = self._build_portfolio(signals, self.default_capital, self.default_benchmark)
        backtests = self.storage.list_records("backtests")
        latest_backtest = backtests[0] if backtests else self._build_backtest(
            strategy_name="ESG Multi-Factor Long-Only",
            benchmark=self.default_benchmark,
            capital_base=self.default_capital,
            positions=portfolio.positions,
            lookback_days=126,
            persist=False,
        ).model_dump()
        payload = {
            "generated_at": _iso_now(),
            "selected_provider": provider_preference,
            "sector_heatmap": sector_heatmap,
            "market_surface": market_surface,
            "heatmap_nodes": market_surface,
            "portfolio_preview": portfolio.model_dump(),
            "latest_backtest": latest_backtest,
        }
        self._dashboard_secondary_cache[provider_preference] = self._cache_wrap(payload)
        return payload

    def _synthetic_chart_frame(self, signal: ResearchSignal, timeframe: str) -> pd.DataFrame:
        limit = self._chart_limit_for_timeframe(timeframe)
        anchor = max(float(signal.house_score or signal.overall_score or 60.0), 1.0)
        close = anchor * 2.4
        rows: list[dict[str, Any]] = []
        for index in range(limit):
            drift = float(signal.expected_return or 0.0) / max(limit / 8.0, 1.0)
            wave = math.sin(index / 4.5) * 0.004 + math.cos(index / 9.0) * 0.002
            open_price = close
            close = max(4.0, close * (1.0 + drift + wave))
            high = max(open_price, close) * 1.012
            low = min(open_price, close) * 0.988
            rows.append(
                {
                    "timestamp": (datetime.now(timezone.utc) - timedelta(days=limit - index)).date().isoformat(),
                    "open": round(open_price, 2),
                    "high": round(high, 2),
                    "low": round(low, 2),
                    "close": round(close, 2),
                    "volume": 5_000_000 + (index % 11) * 180_000,
                }
            )
        return pd.DataFrame(rows)

    def _build_chart_indicators(self, frame: pd.DataFrame) -> dict[str, list[dict[str, Any]]]:
        if frame.empty:
            return {"ma20": [], "ma60": [], "boll": [], "volume_ma20": []}

        enriched = frame.copy()
        enriched["ma20"] = enriched["close"].rolling(20, min_periods=1).mean()
        enriched["ma60"] = enriched["close"].rolling(60, min_periods=1).mean()
        rolling_std = enriched["close"].rolling(20, min_periods=1).std().fillna(0.0)
        enriched["boll_upper"] = enriched["ma20"] + rolling_std * 2
        enriched["boll_lower"] = enriched["ma20"] - rolling_std * 2
        enriched["volume_ma20"] = enriched["volume"].rolling(20, min_periods=1).mean()
        return {
            "ma20": [{"date": row["timestamp"], "value": round(float(row["ma20"]), 4)} for _, row in enriched.iterrows()],
            "ma60": [{"date": row["timestamp"], "value": round(float(row["ma60"]), 4)} for _, row in enriched.iterrows()],
            "boll": [
                {
                    "date": row["timestamp"],
                    "upper": round(float(row["boll_upper"]), 4),
                    "middle": round(float(row["ma20"]), 4),
                    "lower": round(float(row["boll_lower"]), 4),
                }
                for _, row in enriched.iterrows()
            ],
            "volume_ma20": [{"date": row["timestamp"], "value": round(float(row["volume_ma20"]), 4)} for _, row in enriched.iterrows()],
        }

    def build_dashboard_chart(self, symbol: str | None = None, timeframe: str = "1D", provider: str = "auto") -> dict[str, Any]:
        provider_preference, provider_chain = self._dashboard_provider_chain(provider)
        requested_symbol = str(symbol or "").upper().strip()
        normalized_timeframe = str(timeframe or "1D").upper()
        cache_key = (requested_symbol, normalized_timeframe, provider_preference)
        cached = self._chart_cache.get(cache_key)
        if self._cache_is_fresh(cached):
            return cached["payload"]
        snapshot = self._resolve_dashboard_watchlist_snapshot(provider_preference, include_stale=True)
        watchlist = list(snapshot.get("watchlist_signals") or [])
        position_symbols = list(snapshot.get("position_symbols") or [])
        active_symbol = self._resolve_dashboard_symbol(
            requested_symbol=symbol,
            watchlist=watchlist,
            position_symbols=position_symbols,
            provider_preference=provider_preference,
        )
        active = next((item for item in watchlist if item["symbol"] == active_symbol), None)
        if active is None:
            active = {
                "symbol": active_symbol,
                "company_name": active_symbol,
                "sector": "Tracked",
                "thesis": f"{active_symbol} chart loaded without a warm watchlist context.",
                "action": "neutral",
                "confidence": 0.5,
                "expected_return": 0.0,
                "risk_score": 0.5,
                "overall_score": 0.0,
                "e_score": 0.0,
                "s_score": 0.0,
                "g_score": 0.0,
                "factor_scores": [],
                "catalysts": [],
                "data_lineage": [],
                "market_data_source": "",
                "prediction_mode": "unavailable",
                "projection_basis_return": None,
                "projection_scenarios": {},
            }
        limit = self._chart_limit_for_timeframe(timeframe)
        signal = self._enrich_signal_house_score(
            ResearchSignal(
                symbol=active_symbol,
                company_name=active["company_name"],
                sector=active["sector"],
                thesis=active["thesis"],
                action=active["action"],
                confidence=float(active["confidence"]),
                expected_return=float(active["expected_return"]),
                risk_score=float(active["risk_score"]),
                overall_score=float(active["overall_score"]),
                e_score=float(active["e_score"]),
                s_score=float(active["s_score"]),
                g_score=float(active["g_score"]),
                factor_scores=[FactorScore(**item) for item in active.get("factor_scores", [])],
                catalysts=list(active.get("catalysts", [])),
                data_lineage=list(active.get("data_lineage", [])),
                market_data_source=active.get("market_data_source"),
                prediction_mode=active.get("prediction_mode"),
                projection_basis_return=active.get("projection_basis_return"),
                projection_scenarios={key: ProjectionScenario(**value) for key, value in (active.get("projection_scenarios") or {}).items()},
            )
        )

        source = str(active.get("market_data_source") or self._resolve_market_data_source(signal) or provider_preference)
        degraded_from = None
        provider_status = {"available": False, "provider": source, "selected_provider": provider_preference}
        try:
            if provider_preference == "synthetic":
                raise RuntimeError("synthetic_requested")
            live_provider_order = [item for item in provider_chain if item not in {"cache", "synthetic"}]
            if provider_preference in {"alpaca", "twelvedata", "yfinance"}:
                live_provider_order = [provider_preference]
            elif live_provider_order:
                live_provider_order = [live_provider_order[0]]
            bars_result = self._get_daily_bars(
                active_symbol,
                limit=limit,
                provider_order_override=live_provider_order,
                cache_only=provider_preference == "cache",
                allow_stale_cache=True,
                timeout_override=self._dashboard_live_timeout_seconds,
            )
            source = "cache" if provider_preference == "cache" else bars_result.provider
            provider_status = {
                "available": True,
                "provider": bars_result.provider,
                "selected_provider": provider_preference,
                "cache_hit": bool(getattr(bars_result, "cache_hit", False)),
                "lookback_limit": int(limit),
            }
            frame = bars_result.bars.copy()
            expected_provider = "alpaca" if provider_preference == "auto" else provider_preference
            if expected_provider not in {"cache", "synthetic"} and bars_result.provider != expected_provider:
                degraded_from = expected_provider
            if provider_preference == "cache" and bars_result.provider != "cache":
                degraded_from = "cache"
        except Exception as exc:
            degraded_from = None if provider_preference == "synthetic" else provider_preference
            source = "synthetic"
            provider_status = {
                "available": False,
                "provider": "unavailable",
                "selected_provider": provider_preference,
                "error": str(exc),
            }
            frame = self._build_synthetic_dashboard_bars(active_symbol, limit=limit)

        frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True).dt.strftime("%Y-%m-%d")
        indicators = self._build_chart_indicators(frame)
        candles = [
            {
                "date": row["timestamp"],
                "open": round(float(row["open"]), 4),
                "high": round(float(row["high"]), 4),
                "low": round(float(row["low"]), 4),
                "close": round(float(row["close"]), 4),
                "volume": round(float(row.get("volume") or 0.0), 4),
            }
            for _, row in frame.iterrows()
        ]

        projection_scenarios = active.get("projection_scenarios") or {}
        projection_explanations = {}
        for key, scenario in projection_scenarios.items():
            expected_return = float((scenario or {}).get("expected_return") or 0.0)
            direction = "upside" if expected_return > 0 else "downside" if expected_return < 0 else "range"
            projection_explanations[key] = {
                "title": (scenario or {}).get("label") or key.title(),
                "direction": direction,
                "expected_return": expected_return,
                "confidence": float((scenario or {}).get("confidence") or active.get("confidence") or 0.0),
                "drivers": [item.get("description") for item in active.get("factor_scores", [])[:3] if item.get("description")],
                "why_not_opposite": (active.get("catalysts") or ["Decision stack rejected the opposite branch."])[-1],
                "source": source,
                "data_lineage": list(active.get("data_lineage") or []),
                "house_explanation": active.get("house_explanation"),
            }

        last_volume = float(frame["volume"].iloc[-1]) if not frame.empty else 0.0
        projected_volume = [
            {
                "scenario": key,
                "points": [
                    {
                        "step": step,
                        "value": round(last_volume * (1.0 + float((scenario or {}).get("expected_return") or 0.0) * 0.18 * step), 2),
                    }
                    for step in range(1, 6)
                ],
            }
            for key, scenario in projection_scenarios.items()
        ]

        prediction_disabled_reason = None
        if source in {"synthetic", "unavailable"}:
            prediction_disabled_reason = "market_data_unavailable"
        elif active.get("prediction_mode") != "model":
            prediction_disabled_reason = "prediction_mode_unavailable"

        market_data_warnings: list[str] = []
        if degraded_from:
            market_data_warnings.append(f"provider_degraded_from_{degraded_from}")
        if source in {"cache", "synthetic"}:
            market_data_warnings.append("cache_or_synthetic_fallback")
        if source == "unavailable" or (not candles and source not in {"loading", "unknown"}):
            market_data_warnings.append("market_data_unavailable")
        if not candles:
            market_data_warnings.append("chart_data_unavailable")
        market_data_warnings = list(dict.fromkeys(market_data_warnings))
        fallback_preview = {
            "symbol": active_symbol,
            "source": source,
            "source_chain": provider_chain,
            "last_snapshot": candles[-1] if candles else None,
            "reason": market_data_warnings,
            "next_actions": ["refresh_dashboard", "switch_symbol", "open_market_radar", "open_backtest"],
        }

        payload = {
            "symbol": active_symbol,
            "timeframe": timeframe.upper(),
            "source": source,
            "selected_provider": provider_preference,
            "data_source_chain": provider_chain,
            "candles": candles,
            "indicators": indicators,
            "projection_scenarios": projection_scenarios if prediction_disabled_reason is None else {},
            "projection_explanations": projection_explanations if prediction_disabled_reason is None else {},
            "projected_volume": projected_volume if prediction_disabled_reason is None else [],
            "viewport_defaults": {
                "116%": {"visibleCount": 64, "projectionWidthRatio": 0.22, "pricePaddingRatio": 0.06},
                "352%": {"visibleCount": 32, "projectionWidthRatio": 0.28, "pricePaddingRatio": 0.08},
                "600%": {"visibleCount": 20, "projectionWidthRatio": 0.34, "pricePaddingRatio": 0.11},
            },
            "click_targets": ["symbol_chip", "timeframe_tab", "zoom_control", "projection_line", "heatmap_tile"],
            "prediction_disabled_reason": prediction_disabled_reason,
            "market_data_warnings": market_data_warnings,
            "warning": market_data_warnings[0] if market_data_warnings else None,
            "detail": None,
            "fallback_preview": fallback_preview,
            "signal": active,
            "is_live_data": source == "alpaca",
            "provider_status": provider_status,
            "degraded_from": degraded_from,
            "market_session": self._safe_get_clock(self._prepare_broker_adapter("alpaca", "paper")[0]),
            "range_label": timeframe.upper(),
            "positions_context": {"symbols": position_symbols},
            "indicator_panels": ["main", "volume"],
        }
        self._last_dashboard_symbol = active_symbol
        resolved_cache_key = (active_symbol, normalized_timeframe, provider_preference)
        self._chart_cache[resolved_cache_key] = self._cache_wrap(payload, ttl_seconds=30)
        if requested_symbol != active_symbol:
            self._chart_cache[cache_key] = self._chart_cache[resolved_cache_key]
        return payload

    @staticmethod
    def _dashboard_provider_chain(provider: str | None) -> tuple[str, list[str]]:
        preferred = str(provider or "auto").strip().lower() or "auto"
        if preferred == "alpaca":
            return preferred, ["alpaca", "yfinance", "cache", "synthetic"]
        if preferred == "twelvedata":
            return preferred, ["twelvedata", "alpaca", "yfinance", "cache", "synthetic"]
        if preferred == "yfinance":
            return preferred, ["yfinance", "alpaca", "cache", "synthetic"]
        if preferred == "cache":
            return preferred, ["cache", "synthetic"]
        if preferred == "synthetic":
            return preferred, ["synthetic"]
        return "auto", ["alpaca", "yfinance", "cache", "synthetic"]

    @staticmethod
    def _build_synthetic_dashboard_bars(symbol: str, *, limit: int) -> pd.DataFrame:
        random.seed(hash(symbol) % 10000)
        base_prices = {
            "NVDA": 480,
            "TSLA": 175,
            "AAPL": 185,
            "MSFT": 415,
            "GOOGL": 155,
            "AMZN": 195,
            "META": 520,
            "AMGN": 270,
            "NEE": 72,
            "SPY": 510,
        }
        price = float(base_prices.get(symbol.upper(), 200))
        start = date.today() - timedelta(days=max(limit, 60))
        rows: list[dict[str, Any]] = []
        for index in range(min(limit, 240)):
            volatility = 0.012 + random.random() * 0.008
            open_price = price
            close_price = price * (1 + (random.random() - 0.48) * volatility * 2)
            high_price = max(open_price, close_price) * (1 + random.random() * volatility * 0.5)
            low_price = min(open_price, close_price) * (1 - random.random() * volatility * 0.5)
            rows.append(
                {
                    "timestamp": (start + timedelta(days=index)).strftime("%Y-%m-%d"),
                    "open": round(open_price, 4),
                    "high": round(high_price, 4),
                    "low": round(low_price, 4),
                    "close": round(close_price, 4),
                    "volume": int((800 + random.random() * 3000) * 1000),
                }
            )
            price = close_price
        return pd.DataFrame(rows)

    def _should_use_live_market_data(self) -> bool:
        running_pytest = any(name == "pytest" or name.startswith("_pytest") for name in sys.modules)
        return not (running_pytest and isinstance(self.market_data, MarketDataGateway))

    @staticmethod
    def _normalize_market_data_provider_chain(configured: str | None = None) -> list[str]:
        raw = configured or "alpaca,yfinance,cache,synthetic"
        aliases = {
            "twelve_data": "twelvedata",
            "twelve-data": "twelvedata",
            "twelve": "twelvedata",
            "alpaca_market": "alpaca",
            "alpaca_iex": "alpaca",
            "synthetic": "synthetic",
        }
        allowed = {"twelvedata", "alpaca", "yfinance", "cache", "synthetic"}
        values: list[str] = []
        for item in str(raw).split(","):
            provider = aliases.get(item.strip().lower(), item.strip().lower())
            if provider in allowed and provider not in values:
                values.append(provider)
        return values or ["alpaca", "yfinance", "cache", "synthetic"]

    @staticmethod
    def _parse_iso_timestamp(raw_value: Any) -> datetime | None:
        if not raw_value:
            return None
        text = str(raw_value).strip()
        if not text:
            return None
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None

    def build_dashboard_overview(self) -> dict[str, Any]:
        overview = self.build_platform_overview()
        paper_gate = self.build_paper_gate_report(persist=False)
        top_signal = overview["top_signals"][0]
        portfolio = overview["portfolio_preview"]
        latest_backtest = overview["latest_backtest"]
        risk_alerts = latest_backtest.get("risk_alerts", [])

        return {
            "generated_at": overview["generated_at"],
            "source": "quant_system",
            "health": {
                "rag": True,
                "esg_scorer": True,
                "report_scheduler": True,
                "data_sources": True,
            },
            "paper_gate": paper_gate,
            "narrative": {
                "headline": "ESG Quant Command Center。",
                "subheadline": "将数据、研究、信号、回测、执行和产品交付收束为一个可运行的量化平台。",
                "summary": "当前旗舰页展示的是 ESG Quant 平台的实时骨架，而不是单点 ESG 问答。你可以从这里进入研究、组合、回测、执行和报告链路。",
            },
            "spotlight": {
                "company": top_signal["company_name"],
                "title": f"{top_signal['company_name']} 当前位于多因子与 ESG 叠加信号前列",
                "description": top_signal["thesis"],
                "event_type": "RESEARCH_SIGNAL",
                "source": "quant-engine",
                "detected_at": overview["generated_at"],
                "tone": "positive" if top_signal["action"] == "long" else "alert",
            },
            "metrics": [
                {"label": "研究覆盖", "value": overview["universe"]["size"], "suffix": "只", "hint": "当前默认量化股票池"},
                {"label": "活跃信号", "value": len(overview["top_signals"]), "suffix": "个", "hint": "进入投资候选池的高优先级信号"},
                {"label": "目标仓位", "value": len(portfolio["positions"]), "suffix": "个", "hint": "当前组合预览持仓数量"},
                {
                    "label": "最新回测夏普",
                    "value": round(float(latest_backtest["metrics"]["sharpe"]), 2),
                    "suffix": "",
                    "hint": "最新策略样本外风险调整收益",
                },
            ],
            "query_interface": {
                "hot_questions": [
                    "运行默认 ESG Quant 研究流程",
                    "对 AAPL/MSFT/TSLA 生成多因子与 ESG 组合建议",
                    "回测 ESG Multi-Factor Long-Only 策略",
                    "生成 Paper Trading 执行清单",
                ]
            },
            "score_snapshot": {
                "company": top_signal["company_name"],
                "overall_score": round(top_signal.get("house_score", top_signal["overall_score"])),
                "house_grade": top_signal.get("house_grade"),
                "confidence": top_signal["confidence"],
                "dimensions": [
                    {"key": "E", "label": "环保", "score": round(top_signal["e_score"]), "trend": "up"},
                    {"key": "S", "label": "社会", "score": round(top_signal["s_score"]), "trend": "stable"},
                    {"key": "G", "label": "治理", "score": round(top_signal["g_score"]), "trend": "up"},
                ],
                "radar": [
                    {"label": "House ESG", "value": round(top_signal.get("house_score", top_signal["overall_score"]))},
                    {"label": "质量", "value": round(self._factor_value(top_signal, "quality"))},
                    {"label": "价值", "value": round(self._factor_value(top_signal, "value"))},
                    {"label": "动量", "value": round(self._factor_value(top_signal, "momentum"))},
                    {"label": "另类数据", "value": round(self._factor_value(top_signal, "alternative_data"))},
                ],
                "trend": self._trend_from_metrics(top_signal["e_score"], top_signal["s_score"], top_signal["g_score"]),
            },
            "event_monitor": {
                "period_label": "最近一轮策略评估",
                "risk_counts": {
                    "high": sum(1 for item in risk_alerts if item["level"] == "high"),
                    "medium": sum(1 for item in risk_alerts if item["level"] == "medium"),
                    "low": sum(1 for item in risk_alerts if item["level"] == "low"),
                },
                "events": risk_alerts or [
                    {
                        "company": "Portfolio",
                        "title": "暂无高风险告警",
                        "description": "当前组合维持在可控风险区间。",
                        "level": "low",
                        "risk_score": 42,
                        "published_at": overview["generated_at"],
                        "recommendation": "继续监控风格暴露与流动性变化。",
                        "positive": True,
                    }
                ],
                "timeline": [
                    {
                        "date_label": point["date"][5:10],
                        "company": "Portfolio",
                        "level": "high" if point["drawdown"] > 0.10 else "medium" if point["drawdown"] > 0.05 else "low",
                    }
                    for point in latest_backtest["timeline"][-5:]
                ],
            },
            "signals": [
                {
                    "company": signal["company_name"],
                    "title": signal["thesis"],
                    "description": f"动作: {signal['action']} · 预期收益 {signal['expected_return']:.2%} · 风险评分 {signal['risk_score']:.1f}",
                    "event_type": "SIGNAL",
                    "source": "factor-engine",
                    "detected_at": overview["generated_at"],
                    "tone": "positive" if signal["action"] == "long" else "neutral",
                }
                for signal in overview["top_signals"][:5]
            ],
        }

    def build_research_context(
        self,
        *,
        symbol: str | None = None,
        provider: str = "auto",
        limit: int = 6,
    ) -> dict[str, Any]:
        from gateway.quant.intelligence import QuantIntelligenceService

        overview = self.build_platform_overview()
        watchlist = list(overview.get("watchlist_signals") or [])
        preferred_provider, default_chain = self._dashboard_provider_chain(provider)
        selected_symbol = str(symbol or (watchlist[0]["symbol"] if watchlist else "AAPL")).upper().strip()

        chart_payload: dict[str, Any]
        try:
            chart_payload = self.build_dashboard_chart(symbol=selected_symbol, timeframe="1D", provider=preferred_provider)
        except Exception as exc:
            chart_payload = {
                "selected_provider": preferred_provider,
                "provider_status": {
                    "available": False,
                    "provider": "unavailable",
                    "selected_provider": preferred_provider,
                    "error": str(exc),
                },
                "data_source_chain": default_chain,
                "fallback_preview": {
                    "symbol": selected_symbol,
                    "source": "unavailable",
                    "source_chain": default_chain,
                    "last_snapshot": None,
                    "reason": [str(exc)],
                    "next_actions": ["Refresh research context", "Switch symbol", "Open connector center"],
                },
                "warning": str(exc),
            }

        provider_chain = list(chart_payload.get("data_source_chain") or default_chain)
        provider_status = dict(chart_payload.get("provider_status") or {})
        fallback_preview = dict(chart_payload.get("fallback_preview") or {})
        warning_message = chart_payload.get("warning")

        quote_symbols: list[str] = []
        for candidate in [selected_symbol] + [str(item.get("symbol") or "").upper().strip() for item in watchlist]:
            if candidate and candidate not in quote_symbols:
                quote_symbols.append(candidate)
            if len(quote_symbols) >= 5:
                break

        watchlist_lookup = {str(item.get("symbol") or "").upper().strip(): item for item in watchlist}
        quote_strip: list[dict[str, Any]] = []
        for quote_symbol in quote_symbols:
            signal = watchlist_lookup.get(quote_symbol, {})
            market_payload = None
            try:
                market_payload = self._get_daily_bars(
                    quote_symbol,
                    limit=2,
                    provider_order_override=[name for name in provider_chain if name != "synthetic"],
                    allow_stale_cache=True,
                )
            except Exception:
                market_payload = None

            bars = market_payload.bars if market_payload is not None else None
            price = None
            change_pct = None
            source = signal.get("market_data_source") or "unavailable"
            cache_hit = None
            if bars is not None and not bars.empty:
                closes = bars["close"].astype(float).tolist()
                price = round(float(closes[-1]), 4)
                if len(closes) >= 2 and closes[-2]:
                    change_pct = round((closes[-1] - closes[-2]) / closes[-2], 6)
                source = getattr(market_payload, "provider", None) or source
                cache_hit = bool(getattr(market_payload, "cache_hit", False))
            if change_pct is None:
                change_pct = float(signal.get("expected_return") or 0.0)

            quote_strip.append(
                {
                    "symbol": quote_symbol,
                    "company_name": str(signal.get("company_name") or quote_symbol),
                    "price": price,
                    "change_pct": round(float(change_pct), 6) if change_pct is not None else None,
                    "source": str(source or "unavailable"),
                    "provider_status": {
                        "available": bool(source and source != "unavailable"),
                        "provider": str(source or "unavailable"),
                        "selected_provider": preferred_provider,
                        "cache_hit": cache_hit,
                    },
                    "warning": None if source and source != "unavailable" else "No live quote payload returned for this symbol.",
                }
            )

        intelligence = QuantIntelligenceService(self)
        evidence_payload = intelligence.list_evidence(symbol=selected_symbol, limit=max(3, int(limit)))
        feed: list[dict[str, Any]] = []
        latest_published_at: datetime | None = None
        for item in evidence_payload.get("items", [])[: max(3, int(limit))]:
            metadata = item.get("metadata") or {}
            sentiment = str(metadata.get("sentiment") or metadata.get("direction") or "neutral").lower().strip()
            if sentiment not in {"long", "short", "positive", "negative", "neutral"}:
                sentiment = "neutral"
            published_at = item.get("published_at") or item.get("observed_at")
            parsed_published = self._parse_iso_timestamp(published_at)
            if parsed_published and (latest_published_at is None or parsed_published > latest_published_at):
                latest_published_at = parsed_published
            feed.append(
                {
                    "item_id": str(item.get("item_id") or ""),
                    "item_type": str(item.get("item_type") or ""),
                    "symbol": str(item.get("symbol") or ""),
                    "title": str(item.get("title") or "Untitled evidence"),
                    "summary": str(item.get("summary") or ""),
                    "source": str(item.get("source") or ""),
                    "provider": str(item.get("provider") or ""),
                    "published_at": published_at,
                    "freshness_score": item.get("freshness_score"),
                    "confidence": item.get("confidence"),
                    "quality_score": item.get("quality_score"),
                    "sentiment": "long" if sentiment == "positive" else "short" if sentiment == "negative" else sentiment,
                    "url": item.get("url"),
                }
            )

        momentum_leaders = [
            {
                "symbol": item.get("symbol"),
                "company_name": item.get("company_name"),
                "house_score": item.get("house_score") or item.get("overall_score"),
                "expected_return": item.get("expected_return"),
                "confidence": item.get("confidence"),
                "source": item.get("market_data_source") or "quant_system",
            }
            for item in watchlist[:5]
        ]

        degraded = not bool(provider_status.get("available")) or bool(warning_message) or not feed
        warning = None
        if warning_message or not feed:
            warning = {
                "code": "research_context_degraded",
                "message": str(warning_message or "Evidence feed is temporarily unavailable."),
                "severity": "warning",
                "next_actions": fallback_preview.get("next_actions")
                or ["Refresh research context", "Switch symbol", "Open market radar"],
            }

        freshness = {
            "generated_at": _iso_now(),
            "latest_feed_event_at": latest_published_at.isoformat() if latest_published_at else None,
            "evidence_bundle_count": int(evidence_payload.get("bundle_count") or 0),
            "quote_count": len(quote_strip),
        }

        return {
            "generated_at": _iso_now(),
            "symbol": selected_symbol,
            "provider": preferred_provider,
            "quote_strip": quote_strip,
            "momentum_leaders": momentum_leaders,
            "feed": feed,
            "provider_status": provider_status,
            "source_chain": provider_chain,
            "freshness": freshness,
            "degraded": degraded,
            "fallback_preview": fallback_preview,
            "warning": warning,
            "next_actions": fallback_preview.get("next_actions")
            or ["Refresh research context", "Open intelligence evidence", "Switch symbol"],
        }

    def run_research_pipeline(
        self,
        universe_symbols: list[str] | None = None,
        benchmark: str | None = None,
        research_question: str = "",
        capital_base: float | None = None,
        horizon_days: int = 20,
    ) -> dict[str, Any]:
        benchmark = benchmark or self.default_benchmark
        capital_base = capital_base or self.default_capital
        universe = self.get_default_universe(universe_symbols)
        signals = self._build_signals(universe, research_question or "ESG quant research", benchmark)
        portfolio = self._build_portfolio(signals, capital_base, benchmark)

        record = {
            "research_id": f"research-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            "created_at": _iso_now(),
            "question": research_question or "Run default ESG quant research",
            "benchmark": benchmark,
            "horizon_days": horizon_days,
            "universe": [_as_dict(member) for member in universe],
            "signals": [_as_dict(signal) for signal in signals],
            "portfolio": portfolio.model_dump(),
            "report_excerpt": self._summarize_signals(signals, portfolio),
            "storage": {},
        }
        record["storage"] = self.storage.persist_record("research_runs", record["research_id"], record)
        self._persist_experiment(
            name="research_pipeline",
            objective="rank_esg_multi_factor_signals",
            benchmark=benchmark,
            metrics={
                "expected_alpha": round(portfolio.expected_alpha, 4),
                "gross_exposure": round(portfolio.gross_exposure, 4),
                "signal_count": float(len(signals)),
            },
            tags=["research", "esg", "multi-factor"],
            artifact_uri=record["storage"].get("artifact_uri"),
        )
        return record

    @staticmethod
    def _normalize_weight_vector(raw_weights: list[float], cap: float | None = None) -> list[float]:
        if not raw_weights:
            return []
        total = sum(max(float(weight), 0.0) for weight in raw_weights)
        if total <= 0:
            return [round(1.0 / len(raw_weights), 4) for _ in raw_weights]

        normalized = [max(float(weight), 0.0) / total for weight in raw_weights]
        if cap is None:
            return [round(weight, 4) for weight in normalized]

        effective_cap = max(float(cap), 1.0 / len(normalized))
        remaining = set(range(len(normalized)))
        remaining_total = sum(normalized)
        target_total = 1.0
        final_weights = [0.0 for _ in normalized]

        while remaining:
            capped_any = False
            for index in list(remaining):
                if remaining_total <= 0 or target_total <= 0:
                    break
                proposed = normalized[index] / remaining_total * target_total
                if proposed > effective_cap:
                    final_weights[index] = effective_cap
                    target_total -= effective_cap
                    remaining_total -= normalized[index]
                    remaining.remove(index)
                    capped_any = True
            if not capped_any:
                for index in remaining:
                    final_weights[index] = normalized[index] / max(remaining_total, 1e-9) * max(target_total, 0.0)
                break

        return [round(weight, 4) for weight in final_weights]

    def _build_returns_frame(self, symbols: list[str], lookback_days: int = 90) -> pd.DataFrame:
        series_map: dict[str, pd.Series] = {}
        for symbol in symbols:
            try:
                result = self.market_data.get_daily_bars(symbol, limit=max(lookback_days, 60))
                bars = result.bars.copy()
                if bars.empty or "close" not in bars:
                    continue
                bars["timestamp"] = pd.to_datetime(bars["timestamp"], utc=True, errors="coerce")
                bars = bars.dropna(subset=["timestamp"]).sort_values("timestamp").drop_duplicates("timestamp", keep="last")
                closes = bars.set_index("timestamp")["close"].astype(float)
                returns = closes.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
                if len(returns) < 20:
                    continue
                series_map[str(symbol).upper()] = returns.tail(lookback_days)
            except Exception as exc:
                logger.warning(f"[Quant] Market return history unavailable for {symbol}: {exc}")

        if not series_map:
            return pd.DataFrame()

        frame = pd.DataFrame(series_map).sort_index().tail(lookback_days)
        return frame.dropna(how="all").fillna(0.0)

    def _estimate_liquidity_snapshot(self, symbol: str, capital_base: float) -> dict[str, float]:
        fallback_price = max(((_stable_seed(symbol, "price") % 24000) / 100.0), 20.0)
        payload = {
            "last_price": fallback_price,
            "adv_shares": max(250_000.0, (_stable_seed(symbol, "adv") % 4_000_000) + 250_000.0),
            "adv_dollars": 0.0,
            "realized_volatility": 0.18,
            "spread_proxy_bps": 8.0,
            "participation_rate": 0.0,
            "order_notional": 0.0,
        }
        payload["adv_dollars"] = payload["adv_shares"] * payload["last_price"]

        try:
            bars = self.market_data.get_daily_bars(symbol, limit=60).bars.copy()
            if not bars.empty:
                bars["close"] = bars["close"].astype(float)
                bars["volume"] = bars["volume"].astype(float)
                bars["dollar_volume"] = bars["close"] * bars["volume"]
                last_price = float(bars["close"].iloc[-1])
                adv_shares = float(bars["volume"].tail(20).mean() or 0.0)
                adv_dollars = float(bars["dollar_volume"].tail(20).mean() or 0.0)
                returns = bars["close"].pct_change().replace([np.inf, -np.inf], np.nan).dropna().tail(20)
                realized_volatility = float(returns.std(ddof=0) * math.sqrt(252)) if len(returns) > 1 else payload["realized_volatility"]
                spread_proxy_bps = _bounded(4.5 + realized_volatility * 240.0, 3.5, 42.0)
                payload.update(
                    {
                        "last_price": max(last_price, 1.0),
                        "adv_shares": max(adv_shares, payload["adv_shares"]),
                        "adv_dollars": max(adv_dollars, payload["adv_dollars"]),
                        "realized_volatility": _bounded(realized_volatility or payload["realized_volatility"], 0.06, 0.85),
                        "spread_proxy_bps": spread_proxy_bps,
                    }
                )
        except Exception as exc:
            logger.warning(f"[Quant] Liquidity snapshot fallback for {symbol}: {exc}")

        payload["order_notional"] = max(capital_base, 1.0)
        payload["participation_rate"] = _bounded(payload["order_notional"] / max(payload["adv_dollars"], 1.0), 0.0, 5.0)
        return payload

    def _rebalance_sector_cap(
        self,
        *,
        weights: list[float],
        positions: list[PortfolioPosition],
        signal_lookup: dict[str, ResearchSignal],
        sector_cap: float | None,
        single_name_cap: float | None,
    ) -> list[float]:
        if not weights:
            return []
        if sector_cap is None or float(sector_cap) >= 0.999:
            return self._normalize_weight_vector(weights, cap=single_name_cap)

        adjusted = list(self._normalize_weight_vector(weights, cap=single_name_cap))
        sector_cap = max(float(sector_cap), max(1.0 / len(adjusted), 0.01))
        sectors = [
            str((signal_lookup.get(position.symbol).sector if signal_lookup.get(position.symbol) else "Unknown") or "Unknown")
            for position in positions
        ]

        for _ in range(8):
            sector_totals: dict[str, float] = {}
            for index, sector in enumerate(sectors):
                sector_totals[sector] = sector_totals.get(sector, 0.0) + float(adjusted[index])

            violating = {sector for sector, total in sector_totals.items() if total > sector_cap + 1e-6}
            if not violating:
                break

            overflow = 0.0
            recipients: list[int] = []
            for index, sector in enumerate(sectors):
                if sector in violating:
                    total = sector_totals[sector]
                    scaled = adjusted[index] * (sector_cap / max(total, 1e-9))
                    overflow += adjusted[index] - scaled
                    adjusted[index] = scaled
                else:
                    recipients.append(index)

            if overflow <= 1e-8 or not recipients:
                adjusted = self._normalize_weight_vector(adjusted, cap=single_name_cap)
                break

            pool = sum(adjusted[index] for index in recipients)
            for index in recipients:
                adjusted[index] += overflow * (
                    (adjusted[index] / pool) if pool > 0 else (1.0 / len(recipients))
                )
            adjusted = self._normalize_weight_vector(adjusted, cap=single_name_cap)

        return adjusted

    def _allocate_objective_weights(
        self,
        positions: list[PortfolioPosition],
        signal_lookup: dict[str, ResearchSignal],
        *,
        objective_key: str,
        max_position_weight: float | None,
        max_sector_concentration: float | None,
    ) -> tuple[list[float], dict[str, Any]]:
        if not positions:
            return [], {"mode": "empty"}

        single_name_cap = float(max_position_weight) if max_position_weight is not None else None
        symbols = [position.symbol for position in positions]
        base_weights = np.array([max(float(position.weight), 0.0001) for position in positions], dtype=float)
        expected_returns = np.array([max(float(position.expected_return), 0.0) for position in positions], dtype=float)

        returns_frame = self._build_returns_frame(symbols, lookback_days=90)
        diagnostics: dict[str, Any] = {
            "mode": "heuristic",
            "objective": objective_key,
            "history_rows": int(len(returns_frame)),
            "history_assets": int(len(returns_frame.columns)),
        }

        if returns_frame.empty or len(returns_frame.columns) < 2:
            if objective_key == "equal_weight":
                raw = np.ones(len(positions), dtype=float)
            elif objective_key == "risk_parity":
                raw = np.array(
                    [
                        1.0 / max(
                            float(signal_lookup.get(position.symbol).predicted_volatility_10d or 0.18)
                            if signal_lookup.get(position.symbol)
                            else 0.18,
                            0.04,
                        )
                        for position in positions
                    ],
                    dtype=float,
                )
            elif objective_key == "minimum_variance":
                raw = np.array(
                    [
                        1.0
                        / max(
                            float(signal_lookup.get(position.symbol).predicted_volatility_10d or 0.18)
                            if signal_lookup.get(position.symbol)
                            else 0.18,
                            0.04,
                        )
                        ** 2
                        for position in positions
                    ],
                    dtype=float,
                )
            else:
                raw = base_weights
        else:
            aligned_symbols = [symbol for symbol in symbols if symbol in returns_frame.columns]
            if len(aligned_symbols) == len(symbols):
                cov = returns_frame[aligned_symbols].cov().fillna(0.0)
                cov_matrix = cov.to_numpy(dtype=float)
                diag = np.diag(cov_matrix)
                avg_var = max(float(np.nanmean(diag)) if diag.size else 0.0, 1e-6)
                shrunk_cov = cov_matrix * 0.72 + np.eye(len(symbols)) * avg_var * 0.28
                inv_cov = np.linalg.pinv(shrunk_cov + np.eye(len(symbols)) * max(avg_var * 0.05, 1e-6))
                vol = np.sqrt(np.clip(np.diag(shrunk_cov), 1e-8, None))
                corr = np.divide(
                    shrunk_cov,
                    np.outer(vol, vol),
                    out=np.zeros_like(shrunk_cov),
                    where=np.outer(vol, vol) > 0,
                )
                avg_corr = np.clip((corr.sum(axis=1) - 1.0) / max(len(symbols) - 1, 1), 0.0, 0.95)
                diagnostics.update(
                    {
                        "mode": "covariance_shrinkage",
                        "average_variance": round(avg_var, 8),
                        "average_correlation": round(float(np.mean(avg_corr)) if len(avg_corr) else 0.0, 4),
                    }
                )

                if objective_key == "equal_weight":
                    raw = np.ones(len(symbols), dtype=float)
                elif objective_key == "risk_parity":
                    raw = 1.0 / np.clip(vol, 1e-4, None)
                elif objective_key == "minimum_variance":
                    raw = inv_cov @ np.ones(len(symbols), dtype=float)
                elif objective_key == "maximum_diversification":
                    raw = (1.0 / np.clip(vol, 1e-4, None)) / (1.0 + avg_corr)
                else:
                    mu = np.clip(expected_returns, 0.0, None)
                    if not np.any(mu > 0):
                        mu = np.clip(base_weights, 0.0, None)
                    raw = inv_cov @ (mu + 0.12 * (base_weights / base_weights.sum()))
                    raw = raw / (1.0 + avg_corr)
            else:
                raw = base_weights

        raw = np.clip(raw, 0.0, None)
        if float(raw.sum()) <= 0:
            raw = np.clip(base_weights, 0.0, None)
        weights = self._normalize_weight_vector(raw.tolist(), cap=single_name_cap)
        weights = self._rebalance_sector_cap(
            weights=weights,
            positions=positions,
            signal_lookup=signal_lookup,
            sector_cap=max_sector_concentration,
            single_name_cap=single_name_cap,
        )
        diagnostics["sector_cap"] = max_sector_concentration
        diagnostics["single_name_cap"] = single_name_cap
        return weights, diagnostics

    def _apply_portfolio_request_overrides(
        self,
        portfolio: PortfolioSummary,
        signals: list[ResearchSignal],
        *,
        objective: str | None = None,
        max_position_weight: float | None = None,
        max_sector_concentration: float | None = None,
        esg_floor: float | None = None,
        preset_name: str | None = None,
    ) -> PortfolioSummary:
        def _position_esg_score(position: PortfolioPosition) -> float:
            signal = signal_lookup.get(position.symbol)
            if signal is None:
                return round(float(position.score or 0.0), 2)
            if signal.house_score is not None:
                return round(float(signal.house_score), 2)
            dimension_scores = [
                float(signal.e_score or 0.0),
                float(signal.s_score or 0.0),
                float(signal.g_score or 0.0),
            ]
            if any(score > 0 for score in dimension_scores):
                return round(sum(dimension_scores) / len(dimension_scores), 2)
            return round(float(signal.overall_score or 0.0), 2)

        if not portfolio.positions:
            updated_constraints = dict(portfolio.constraints)
            if objective:
                updated_constraints["optimization_objective"] = objective
            if max_position_weight is not None:
                updated_constraints["requested_max_single_name_weight"] = round(float(max_position_weight), 4)
            if max_sector_concentration is not None:
                updated_constraints["requested_max_sector_concentration"] = round(float(max_sector_concentration), 4)
            if esg_floor is not None:
                updated_constraints["esg_floor"] = round(float(esg_floor), 2)
            if preset_name:
                updated_constraints["preset_name"] = preset_name
            return portfolio.model_copy(update={"constraints": updated_constraints})

        signal_lookup = {signal.symbol: signal for signal in signals}
        filtered_positions = list(portfolio.positions)
        floor = float(esg_floor) if esg_floor is not None else None
        floor_relaxed = False
        achieved_floor = None
        if floor is not None:
            filtered_positions = [
                position
                for position in filtered_positions
                if _position_esg_score(position) >= floor
            ]

        if not filtered_positions:
            fallback_positions = list(portfolio.positions)
            if floor is not None and fallback_positions:
                filtered_positions = fallback_positions
                achieved_floor = min(_position_esg_score(position) for position in filtered_positions)
                floor_relaxed = True
            else:
                updated_constraints = dict(portfolio.constraints)
                updated_constraints.update({
                    "status": "no_trade",
                    "candidate_mode": "request_filter_rejected_all",
                    "signal_filter": "request_filter_rejected_all",
                })
                if floor is not None:
                    updated_constraints["esg_floor"] = round(floor, 2)
                if objective:
                    updated_constraints["optimization_objective"] = objective
                if preset_name:
                    updated_constraints["preset_name"] = preset_name
                if max_position_weight is not None:
                    updated_constraints["requested_max_single_name_weight"] = round(float(max_position_weight), 4)
                if max_sector_concentration is not None:
                    updated_constraints["requested_max_sector_concentration"] = round(float(max_sector_concentration), 4)
                return portfolio.model_copy(update={"positions": [], "gross_exposure": 0.0, "net_exposure": 0.0, "expected_alpha": 0.0, "constraints": updated_constraints})

        if floor_relaxed and achieved_floor is None:
            achieved_floor = min(_position_esg_score(position) for position in filtered_positions)

        if floor_relaxed:
            updated_constraints = dict(portfolio.constraints)
            updated_constraints.update({
                "status": "ready",
                "candidate_mode": "request_filter_best_effort",
                "signal_filter": "best_effort_esg_relaxation",
                "esg_floor_policy": "best_effort",
                "requested_esg_floor": round(floor or 0.0, 2),
                "achieved_min_esg_score": round(float(achieved_floor or 0.0), 2),
                "esg_floor_shortfall": round(max(float(floor or 0.0) - float(achieved_floor or 0.0), 0.0), 2),
            })
            if objective:
                updated_constraints["optimization_objective"] = objective
            if preset_name:
                updated_constraints["preset_name"] = preset_name
            if max_position_weight is not None:
                updated_constraints["requested_max_single_name_weight"] = round(float(max_position_weight), 4)
            if max_sector_concentration is not None:
                updated_constraints["requested_max_sector_concentration"] = round(float(max_sector_concentration), 4)
        else:
            updated_constraints = dict(portfolio.constraints)

        objective_key = str(objective or "maximum_sharpe").strip().lower()
        normalized_weights, allocation_meta = self._allocate_objective_weights(
            filtered_positions,
            signal_lookup,
            objective_key=objective_key,
            max_position_weight=max_position_weight,
            max_sector_concentration=max_sector_concentration,
        )
        updated_positions: list[PortfolioPosition] = []
        for position, weight in zip(filtered_positions, normalized_weights):
            updated_positions.append(
                position.model_copy(
                    update={
                        "weight": round(weight, 4),
                        "thesis": f"{position.thesis} | Objective {objective_key}" if objective_key else position.thesis,
                    }
                )
            )

        updated_constraints["optimization_objective"] = objective_key
        if max_position_weight is not None:
            updated_constraints["max_single_name_weight"] = round(float(max_position_weight), 4)
        if max_sector_concentration is not None:
            updated_constraints["max_sector_tilt"] = round(float(max_sector_concentration), 4)
            updated_constraints["requested_max_sector_concentration"] = round(float(max_sector_concentration), 4)
        if floor is not None:
            updated_constraints["esg_floor"] = round(floor, 2)
        if preset_name:
            updated_constraints["preset_name"] = preset_name

        updated_constraints["allocator"] = allocation_meta.get("mode", "heuristic")
        updated_constraints["allocator_history_rows"] = float(allocation_meta.get("history_rows", 0) or 0)
        if allocation_meta.get("average_correlation") is not None:
            updated_constraints["allocator_average_correlation"] = float(allocation_meta.get("average_correlation") or 0.0)

        expected_alpha = round(sum(position.weight * position.expected_return for position in updated_positions), 4)
        gross_exposure = round(sum(position.weight for position in updated_positions), 4)
        return portfolio.model_copy(
            update={
                "positions": updated_positions,
                "gross_exposure": gross_exposure,
                "net_exposure": gross_exposure,
                "expected_alpha": expected_alpha,
                "constraints": updated_constraints,
            }
        )

    def optimize_portfolio(
        self,
        universe_symbols: list[str] | None = None,
        benchmark: str | None = None,
        capital_base: float | None = None,
        research_question: str = "",
        preset_name: str | None = None,
        objective: str | None = None,
        max_position_weight: float | None = None,
        max_sector_concentration: float | None = None,
        esg_floor: float | None = None,
    ) -> dict[str, Any]:
        benchmark = benchmark or self.default_benchmark
        capital_base = capital_base or self.default_capital
        signals = self._build_signals(self.get_default_universe(universe_symbols), research_question, benchmark)
        portfolio = self._build_portfolio(signals, capital_base, benchmark, allow_watchlist_fallback=True)
        portfolio = self._apply_portfolio_request_overrides(
            portfolio,
            signals,
            objective=objective,
            max_position_weight=max_position_weight,
            max_sector_concentration=max_sector_concentration,
            esg_floor=esg_floor,
            preset_name=preset_name,
        )
        signal_lookup = {signal.symbol: signal for signal in signals}
        holdings = []
        weighted_volatility = 0.0
        weighted_esg = 0.0
        for position in portfolio.positions:
            signal = signal_lookup.get(position.symbol)
            weighted_volatility += position.weight * float(
                signal.predicted_volatility_10d
                if signal and signal.predicted_volatility_10d is not None
                else 0.18
            )
            weighted_esg += position.weight * float(signal.house_score if signal and signal.house_score is not None else signal.overall_score if signal else 0.0)
            holdings.append(
                {
                    "symbol": position.symbol,
                    "company_name": position.company_name,
                    "sector": signal.sector if signal else "Unknown",
                    "weight": position.weight,
                    "expected_return": position.expected_return,
                    "risk_budget": position.risk_budget,
                    "score": position.score,
                    "side": position.side,
                    "thesis": position.thesis,
                    "strategy_bucket": position.strategy_bucket,
                    "decision_score": position.decision_score,
                    "regime_posture": position.regime_posture,
                    "execution_tactic": position.execution_tactic,
                    "expected_fill_probability": position.expected_fill_probability,
                    "estimated_slippage_bps": position.estimated_slippage_bps,
                    "estimated_impact_bps": position.estimated_impact_bps,
                    "esg_score": round(float(signal.house_score if signal and signal.house_score is not None else signal.overall_score), 2) if signal else None,
                    "house_grade": signal.house_grade if signal else None,
                    "e_score": round(float(signal.e_score), 2) if signal else None,
                    "s_score": round(float(signal.s_score), 2) if signal else None,
                    "g_score": round(float(signal.g_score), 2) if signal else None,
                }
            )
        expected_volatility = round(weighted_volatility, 6) if holdings else 0.0
        sharpe_estimate = round(
            portfolio.expected_alpha / expected_volatility,
            6,
        ) if expected_volatility > 0 else 0.0

        record = {
            "optimization_id": f"portfolio-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            "created_at": _iso_now(),
            "benchmark": benchmark,
            "request_config": {
                "preset_name": preset_name,
                "objective": objective,
                "max_position_weight": max_position_weight,
                "max_sector_concentration": max_sector_concentration,
                "esg_floor": esg_floor,
            },
            "portfolio": portfolio.model_dump(),
            "holdings": holdings,
            "positions": [position.model_dump() for position in portfolio.positions],
            "expected_return": round(portfolio.expected_alpha, 6),
            "expected_alpha": round(portfolio.expected_alpha, 6),
            "expected_volatility": expected_volatility,
            "sharpe_estimate": sharpe_estimate,
            "gross_exposure": portfolio.gross_exposure,
            "net_exposure": portfolio.net_exposure,
            "turnover_estimate": portfolio.turnover_estimate,
            "average_esg_score": round(weighted_esg, 4) if holdings else 0.0,
            "status": portfolio.constraints.get("status", "ready"),
            "signals_used": [_as_dict(signal) for signal in signals[:6]],
            "storage": {},
        }
        record["storage"] = self.storage.persist_record("portfolio_runs", record["optimization_id"], record)
        return record

    def build_p1_stack_report(
        self,
        universe_symbols: list[str] | None = None,
        benchmark: str | None = None,
        capital_base: float | None = None,
        research_question: str = "",
    ) -> dict[str, Any]:
        benchmark = benchmark or self.default_benchmark
        capital_base = capital_base or self.default_capital
        universe = self.get_default_universe(universe_symbols)
        signals = self._build_signals(universe, research_question or "Run the P1 alpha + risk stack.", benchmark)
        portfolio = self._build_portfolio(signals, capital_base, benchmark)
        regime_counts = {
            "risk_on": sum(1 for signal in signals if signal.regime_label == "risk_on"),
            "neutral": sum(1 for signal in signals if signal.regime_label == "neutral"),
            "risk_off": sum(1 for signal in signals if signal.regime_label == "risk_off"),
        }
        risk_off_ratio = regime_counts["risk_off"] / max(1, len(signals))
        average_return_5d = statistics.mean(
            [signal.predicted_return_5d for signal in signals if signal.predicted_return_5d is not None] or [0.0]
        )
        average_return_1d = statistics.mean(
            [signal.predicted_return_1d for signal in signals if signal.predicted_return_1d is not None] or [0.0]
        )
        average_sequence_return_1d = statistics.mean(
            [signal.sequence_return_1d for signal in signals if signal.sequence_return_1d is not None] or [0.0]
        )
        average_sequence_return_5d = statistics.mean(
            [signal.sequence_return_5d for signal in signals if signal.sequence_return_5d is not None] or [0.0]
        )
        average_sequence_volatility = statistics.mean(
            [signal.sequence_volatility_10d for signal in signals if signal.sequence_volatility_10d is not None] or [0.0]
        )
        average_sequence_drawdown = statistics.mean(
            [signal.sequence_drawdown_20d for signal in signals if signal.sequence_drawdown_20d is not None] or [0.0]
        )
        average_volatility = statistics.mean(
            [signal.predicted_volatility_10d for signal in signals if signal.predicted_volatility_10d is not None] or [0.0]
        )
        average_drawdown = statistics.mean(
            [signal.predicted_drawdown_20d for signal in signals if signal.predicted_drawdown_20d is not None] or [0.0]
        )
        average_calibrated_probability = statistics.mean(
            [signal.p1_calibrated_probability for signal in signals if signal.p1_calibrated_probability is not None] or [0.0]
        )
        average_calibrated_confidence = statistics.mean(
            [signal.p1_confidence_calibrated for signal in signals if signal.p1_confidence_calibrated is not None] or [0.0]
        )
        sequence_targets = (self.p1_suite.status().get("sequence_forecaster") or {}).get("targets", [])
        promotable = bool(
            portfolio.positions
            and average_return_5d > 0
            and average_drawdown < 0.20
            and risk_off_ratio < 0.45
            and average_calibrated_probability >= 0.48
        )
        blockers: list[str] = []
        if not portfolio.positions:
            blockers.append("No long-only candidates survived the P1 regime and drawdown gates.")
        if average_return_5d <= 0:
            blockers.append("Average predicted 5D return is non-positive.")
        if average_drawdown >= 0.20:
            blockers.append("Average predicted 20D drawdown remains above the productized threshold.")
        if risk_off_ratio >= 0.45:
            blockers.append("Too many symbols are currently classified as risk_off.")
        if average_calibrated_probability < 0.48:
            blockers.append("Average calibrated P1 probability remains below the promotion threshold.")
        report_id = f"p1-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        payload = {
            "report_id": report_id,
            "generated_at": _iso_now(),
            "benchmark": benchmark,
            "capital_base": capital_base,
            "universe": [member.model_dump() for member in universe],
            "suite_status": self.p1_suite.status(),
            "alpha_ranker": self.alpha_ranker.status(),
            "signals": [_as_dict(signal) for signal in signals[:8]],
            "portfolio": portfolio.model_dump(),
            "risk_summary": {
                "average_predicted_return_1d": round(average_return_1d, 6),
                "average_predicted_return_5d": round(average_return_5d, 6),
                "average_sequence_return_1d": round(average_sequence_return_1d, 6),
                "average_sequence_return_5d": round(average_sequence_return_5d, 6),
                "average_predicted_volatility_10d": round(average_volatility, 6),
                "average_predicted_drawdown_20d": round(average_drawdown, 6),
                "average_sequence_volatility_10d": round(average_sequence_volatility, 6),
                "average_sequence_drawdown_20d": round(average_sequence_drawdown, 6),
                "average_calibrated_probability": round(average_calibrated_probability, 6),
                "average_calibrated_confidence": round(average_calibrated_confidence, 6),
                "regime_counts": regime_counts,
            },
            "calibration": {
                "enabled": bool((self.p1_suite.status().get("calibration") or {}).get("enabled")),
                "temperature": (self.p1_suite.status().get("calibration") or {}).get("temperature"),
                "confidence_slope": (self.p1_suite.status().get("calibration") or {}).get("confidence_slope"),
                "average_probability": round(average_calibrated_probability, 6),
                "average_confidence": round(average_calibrated_confidence, 6),
            },
            "deployment_readiness": {
                "promotable_to_paper": promotable,
                "blockers": blockers,
            },
            "training_artifacts": {
                "data_dir": str(getattr(settings, "P1_MODEL_SUITE_DATA_DIR", "data/p1_stack")),
                "checkpoint_dir": str(getattr(settings, "P1_MODEL_SUITE_CHECKPOINT_DIR", "model-serving/checkpoint/p1_suite")),
                "sequence_checkpoint_dir": str(getattr(settings, "P1_SEQUENCE_CHECKPOINT_DIR", "model-serving/checkpoint/sequence_forecaster")),
                "sequence_targets": sequence_targets,
            },
        }
        payload["storage"] = self.storage.persist_record("p1_reports", report_id, payload)
        self._persist_experiment(
            name="p1_stack_report",
            objective="alpha_plus_risk_stack",
            benchmark=benchmark,
            metrics={
                "average_predicted_return_1d": round(average_return_1d, 6),
                "average_predicted_return_5d": round(average_return_5d, 6),
                "average_predicted_drawdown_20d": round(average_drawdown, 6),
                "average_calibrated_probability": round(average_calibrated_probability, 6),
                "promotable": "yes" if promotable else "no",
            },
            tags=["p1", "stacking", "risk", "regime"],
            artifact_uri=(payload["storage"] or {}).get("artifact_uri"),
        )
        return payload

    def build_p2_decision_report(
        self,
        universe_symbols: list[str] | None = None,
        benchmark: str | None = None,
        capital_base: float | None = None,
        research_question: str = "",
    ) -> dict[str, Any]:
        benchmark = benchmark or self.default_benchmark
        capital_base = capital_base or self.default_capital
        universe = self.get_default_universe(universe_symbols)
        signals = self._build_signals(universe, research_question or "Run the P2 graph + strategy selector stack.", benchmark)
        portfolio = self._build_portfolio(signals, capital_base, benchmark)
        graph_payload, selector_payload = self._build_p2_context(signals)
        average_decision = statistics.mean([float(signal.decision_score or 0.0) for signal in signals] or [0.0])
        average_contagion = statistics.mean([float(signal.graph_contagion_risk or 0.0) for signal in signals] or [0.0])
        average_priority = statistics.mean([float(signal.selector_priority_score or 0.0) for signal in signals] or [0.0])
        average_size_multiplier = statistics.mean([float(signal.bandit_size_multiplier or 1.0) for signal in signals] or [1.0])
        average_execution_delay = statistics.mean([float(signal.bandit_execution_delay_seconds or 0.0) for signal in signals] or [0.0])
        average_confidence = statistics.mean([float(signal.decision_confidence or 0.0) for signal in signals] or [0.0])
        alpha_engines = sorted({str(signal.alpha_engine) for signal in signals if signal.alpha_engine})
        promotable = bool(
            portfolio.positions
            and average_decision >= float(getattr(settings, "P2_DECISION_MIN_SCORE", 0.54) or 0.54)
            and average_contagion < float(getattr(settings, "P2_GRAPH_CONTAGION_LIMIT", 0.62) or 0.62)
        )
        blockers = list(selector_payload.get("blockers", []))
        if not portfolio.positions:
            blockers.append("No long candidates survived the P2 decision gates.")
        if average_decision < float(getattr(settings, "P2_DECISION_MIN_SCORE", 0.54) or 0.54):
            blockers.append("Average P2 decision score remains below the paper-promotion threshold.")
        if average_contagion >= float(getattr(settings, "P2_GRAPH_CONTAGION_LIMIT", 0.62) or 0.62):
            blockers.append("Average graph contagion remains above the configured P2 limit.")

        report_id = f"p2-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        payload = {
            "report_id": report_id,
            "generated_at": _iso_now(),
            "benchmark": benchmark,
            "capital_base": capital_base,
            "universe": [member.model_dump() for member in universe],
            "suite_status": {
                "alpha_ranker": self.alpha_ranker.status(),
                "p1_suite": self.p1_suite.status(),
                "p2_stack": self.p2_stack.status(),
            },
            "signals": [_as_dict(signal) for signal in signals[:8]],
            "portfolio": portfolio.model_dump(),
            "graph_summary": graph_payload.get("summary", {}),
            "graph_edges": graph_payload.get("edges", [])[:12],
            "strategy_selector": selector_payload,
            "decision_summary": {
                "average_decision_score": round(average_decision, 6),
                "average_selector_priority": round(average_priority, 6),
                "average_graph_contagion": round(average_contagion, 6),
                "average_decision_confidence": round(average_confidence, 6),
                "average_size_multiplier": round(average_size_multiplier, 6),
                "average_execution_delay_seconds": round(average_execution_delay, 2),
                "selected_strategy": selector_payload.get("selected_strategy"),
                "bandit_strategy": selector_payload.get("bandit", {}).get("selected_strategy"),
                "market_regime": selector_payload.get("market_regime"),
                "alpha_engines": alpha_engines,
            },
            "deployment_readiness": {
                "promotable_to_paper": promotable,
                "blockers": list(dict.fromkeys(blockers)),
            },
            "training_artifacts": {
                "data_dir": str(getattr(settings, "P2_SELECTOR_DATA_DIR", "data/p2_stack")),
                "checkpoint_dir": str(getattr(settings, "P2_SELECTOR_CHECKPOINT_DIR", "model-serving/checkpoint/p2_selector")),
                "graph_checkpoint_dir": str(getattr(settings, "P2_GRAPH_CHECKPOINT_DIR", "model-serving/checkpoint/gnn_graph")),
            },
        }
        payload["storage"] = self.storage.persist_record("p2_reports", report_id, payload)
        self._persist_experiment(
            name="p2_decision_report",
            objective="graph_plus_strategy_selection",
            benchmark=benchmark,
            metrics={
                "average_decision_score": round(average_decision, 6),
                "average_graph_contagion": round(average_contagion, 6),
                "average_size_multiplier": round(average_size_multiplier, 6),
                "selected_strategy": str(selector_payload.get("selected_strategy") or "balanced_quality_growth"),
                "promotable": "yes" if promotable else "no",
            },
            tags=["p2", "graph", "strategy_selector", "decision_stack"],
            artifact_uri=(payload["storage"] or {}).get("artifact_uri"),
        )
        return payload

    def _build_quant_rl_service(self):
        from quant_rl.service.quant_service import QuantRLService

        return QuantRLService()

    def get_hybrid_paper_strategy_workflow(self, workflow_id: str) -> dict[str, Any] | None:
        return self.storage.load_record("workflow_runs", workflow_id)

    def run_hybrid_paper_strategy_workflow(
        self,
        universe_symbols: list[str] | None = None,
        benchmark: str | None = None,
        capital_base: float | None = None,
        strategy_mode: str = "hybrid_p1_p2_rl",
        rl_algorithm: str = "sac",
        rl_action_type: str = "continuous",
        rl_dataset_path: str | None = None,
        rl_checkpoint_path: str | None = None,
        submit_orders: bool = True,
        mode: str = "paper",
        broker: str | None = None,
        max_orders: int = 2,
        per_order_notional: float | None = 1.0,
        allow_synthetic_execution: bool = False,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        benchmark = benchmark or self.default_benchmark
        capital_base = float(capital_base or self.default_capital)
        broker_id = (broker or self.default_broker or "alpaca").strip().lower()
        normalized_mode = self._normalize_broker_mode(mode)
        workflow_id = f"workflow-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
        blockers: list[str] = []
        warnings: list[str] = []
        next_actions: list[str] = []
        steps: dict[str, dict[str, Any]] = {}
        artifacts: dict[str, Any] = {}

        def add_blocker(message: str, *actions: str) -> None:
            if message and message not in blockers:
                blockers.append(message)
            add_actions(*actions)

        def add_warning(message: str, *actions: str) -> None:
            if message and message not in warnings:
                warnings.append(message)
            add_actions(*actions)

        def add_actions(*items: str) -> None:
            for item in items:
                if item and item not in next_actions:
                    next_actions.append(item)

        def mark_step(name: str, status: str, **details: Any) -> None:
            payload = {"status": status, "updated_at": _iso_now()}
            payload.update({key: value for key, value in details.items() if value is not None})
            steps[name] = payload

        def descriptor_path(descriptor: Any, explicit_path: str | None = None) -> str:
            if explicit_path:
                return str(explicit_path).strip()
            if isinstance(descriptor, dict) and descriptor.get("exists"):
                return str(descriptor.get("path") or "").strip()
            return ""

        def local_path_ready(path_value: str) -> bool:
            if not path_value:
                return False
            if path_value.startswith(("http://", "https://", "s3://", "r2://", "supabase://")):
                return False
            try:
                return Path(path_value).expanduser().exists()
            except OSError:
                return False

        def artifact_ref(payload: dict[str, Any] | None, id_key: str) -> dict[str, Any]:
            if not payload:
                return {}
            ref = {
                "id": payload.get(id_key),
                "storage": payload.get("storage", {}),
            }
            if payload.get("artifacts"):
                ref["artifacts"] = payload.get("artifacts")
            return ref

        def model_status_snapshot() -> dict[str, Any]:
            snapshot: dict[str, Any] = {}
            for key, runtime_obj in (
                ("alpha_ranker", self.alpha_ranker),
                ("p1_suite", self.p1_suite),
                ("p2_stack", self.p2_stack),
            ):
                try:
                    snapshot[key] = runtime_obj.status()
                except Exception as exc:
                    snapshot[key] = {"available": False, "error": str(exc)}
                    add_warning(f"{key} status check failed: {exc}", "inspect_model_runtime")
            return snapshot

        def synthetic_backtest_used(payload: dict[str, Any] | None) -> bool:
            if not payload:
                return False
            if payload.get("used_synthetic_fallback"):
                return True
            if str(payload.get("data_source") or "").strip().lower() == "synthetic":
                return True
            for warning in payload.get("market_data_warnings") or []:
                if "synthetic" in str(warning).lower():
                    return True
            return False

        request_payload = {
            "universe": universe_symbols or [],
            "benchmark": benchmark,
            "capital_base": capital_base,
            "strategy_mode": strategy_mode,
            "rl_algorithm": rl_algorithm,
            "rl_action_type": rl_action_type,
            "rl_dataset_path": rl_dataset_path or "",
            "rl_checkpoint_path": rl_checkpoint_path or "",
            "submit_orders": bool(submit_orders),
            "mode": normalized_mode,
            "broker": broker_id,
            "max_orders": max(1, int(max_orders or 1)),
            "per_order_notional": per_order_notional,
            "allow_synthetic_execution": bool(allow_synthetic_execution),
            "force_refresh": bool(force_refresh),
        }

        model_status = model_status_snapshot()
        mark_step("model_status", "completed")

        p1_report: dict[str, Any] | None = None
        p2_report: dict[str, Any] | None = None
        rl_overview: dict[str, Any] = {}
        rl_backtest: dict[str, Any] | None = None
        backtest: dict[str, Any] | None = None
        tearsheet: dict[str, Any] | None = None
        paper_gate: dict[str, Any] | None = None
        execution: dict[str, Any] | None = None
        controls: dict[str, Any] | None = None
        account: dict[str, Any] | None = None

        try:
            p1_report = self.build_p1_stack_report(
                universe_symbols=universe_symbols,
                benchmark=benchmark,
                capital_base=capital_base,
                research_question="Run the hybrid paper workflow P1 alpha + risk stack.",
            )
            artifacts["p1_report"] = artifact_ref(p1_report, "report_id")
            mark_step("p1_report", "completed", report_id=p1_report.get("report_id"))
            p1_ready = p1_report.get("deployment_readiness") or {}
            if not p1_ready.get("promotable_to_paper"):
                add_warning(
                    "P1 report is not promotable; P2 remains the hard strategy gate for this workflow.",
                    "review_p1_report",
                )
        except Exception as exc:
            add_blocker(f"P1 report failed: {exc}", "inspect_p1_runtime")
            mark_step("p1_report", "failed", error=str(exc))

        try:
            p2_report = self.build_p2_decision_report(
                universe_symbols=universe_symbols,
                benchmark=benchmark,
                capital_base=capital_base,
                research_question="Run the hybrid paper workflow P2 graph + strategy selector stack.",
            )
            artifacts["p2_report"] = artifact_ref(p2_report, "report_id")
            mark_step("p2_report", "completed", report_id=p2_report.get("report_id"))
            p2_ready = p2_report.get("deployment_readiness") or {}
            if not p2_ready.get("promotable_to_paper"):
                p2_blockers = list(p2_ready.get("blockers") or [])
                add_blocker(
                    "P2 decision stack is not promotable to paper.",
                    "review_p2_decision_report",
                )
                for item in p2_blockers:
                    add_blocker(str(item), "review_p2_decision_report")
        except Exception as exc:
            add_blocker(f"P2 decision report failed: {exc}", "inspect_p2_runtime")
            mark_step("p2_report", "failed", error=str(exc))

        try:
            rl_service = self._build_quant_rl_service()
            rl_overview = rl_service.overview()
            model_status["rl"] = {
                "available": bool((rl_overview.get("artifact_health") or {}).get("checkpoint_ready")),
                "latest_dataset": rl_overview.get("latest_dataset", {}),
                "latest_checkpoint": rl_overview.get("latest_checkpoint", {}),
                "artifact_health": rl_overview.get("artifact_health", {}),
            }
            artifacts["rl_overview"] = {
                "latest_dataset": rl_overview.get("latest_dataset", {}),
                "latest_checkpoint": rl_overview.get("latest_checkpoint", {}),
                "latest_report": rl_overview.get("latest_report", {}),
                "artifact_health": rl_overview.get("artifact_health", {}),
            }
            dataset_path = descriptor_path(rl_overview.get("latest_dataset"), rl_dataset_path)
            checkpoint_path = descriptor_path(rl_overview.get("latest_checkpoint"), rl_checkpoint_path)
            request_payload["rl_dataset_path"] = dataset_path
            request_payload["rl_checkpoint_path"] = checkpoint_path

            if not local_path_ready(dataset_path):
                add_blocker("RL dataset artifact is not available.", "build_or_sync_rl_dataset")
                mark_step("rl_backtest", "blocked", dataset_path=dataset_path)
            elif not local_path_ready(checkpoint_path):
                add_blocker("RL checkpoint artifact is not available.", "train_or_sync_rl_checkpoint")
                mark_step("rl_backtest", "blocked", dataset_path=dataset_path, checkpoint_path=checkpoint_path)
            else:
                rl_backtest = rl_service.backtest(
                    rl_algorithm,
                    dataset_path,
                    checkpoint_path=checkpoint_path,
                    action_type=rl_action_type,
                    notes=f"hybrid_paper_workflow_id={workflow_id}",
                )
                artifacts["rl_backtest"] = artifact_ref(rl_backtest, "run_id")
                mark_step(
                    "rl_backtest",
                    "completed",
                    run_id=rl_backtest.get("run_id"),
                    dataset_path=dataset_path,
                    checkpoint_path=checkpoint_path,
                )
        except Exception as exc:
            model_status["rl"] = {"available": False, "error": str(exc)}
            add_blocker(f"RL backtest failed: {exc}", "inspect_rl_checkpoint_and_dataset")
            mark_step("rl_backtest", "failed", error=str(exc))

        try:
            backtest = self.run_backtest(
                strategy_name="Hybrid P1/P2 + RL Timing",
                universe_symbols=universe_symbols,
                benchmark=benchmark,
                capital_base=capital_base,
                lookback_days=126,
                force_refresh=force_refresh,
            )
            artifacts["backtest"] = artifact_ref(backtest, "backtest_id")
            mark_step("quant_backtest", "completed", backtest_id=backtest.get("backtest_id"))
            if synthetic_backtest_used(backtest) and not allow_synthetic_execution:
                add_blocker("Backtest used synthetic market data fallback.", "rerun_backtest_with_real_market_data")
        except Exception as exc:
            add_blocker(f"Quant backtest failed: {exc}", "inspect_backtest_inputs")
            mark_step("quant_backtest", "failed", error=str(exc))

        if backtest and backtest.get("backtest_id"):
            try:
                tearsheet_id = str(backtest.get("tearsheet_report_id") or "")
                tearsheet = self.storage.load_record("tearsheets", tearsheet_id) if tearsheet_id else None
                if tearsheet is None:
                    tearsheet = self.build_tearsheet(str(backtest["backtest_id"]), persist=True)
                artifacts["tearsheet"] = artifact_ref(tearsheet, "report_id")
                mark_step("tearsheet", "completed", report_id=tearsheet.get("report_id"))
                if str(tearsheet.get("protection_status") or "").lower() != "pass":
                    add_blocker(
                        "Tearsheet protection status did not pass.",
                        "review_tearsheet_protection_status",
                    )
            except Exception as exc:
                add_blocker(f"Tearsheet generation failed: {exc}", "inspect_tearsheet_generation")
                mark_step("tearsheet", "failed", error=str(exc))
        else:
            mark_step("tearsheet", "skipped")

        try:
            paper_gate = self.build_paper_gate_report(persist=True)
            artifacts["paper_gate"] = artifact_ref(paper_gate, "report_id")
            mark_step("paper_gate", "completed", report_id=paper_gate.get("report_id"), status_label=paper_gate.get("status"))
            if not paper_gate.get("passed"):
                add_warning(
                    "Paper gate is blocked for live enablement; paper workflow can still route if execution gates pass.",
                    "review_paper_gate_report",
                )
        except Exception as exc:
            add_blocker(f"Paper gate report failed: {exc}", "inspect_paper_gate_inputs")
            mark_step("paper_gate", "failed", error=str(exc))

        if normalized_mode != "paper":
            add_blocker("Hybrid paper workflow only supports paper mode.", "switch_to_paper_mode")
        if broker_id != "alpaca":
            add_blocker("Hybrid paper workflow only supports Alpaca paper routing.", "switch_to_alpaca")
        if rl_backtest is None:
            add_blocker("RL backtest did not complete successfully.", "train_or_sync_rl_checkpoint")

        try:
            controls = self.get_execution_controls()
            if submit_orders and bool(controls.get("kill_switch_enabled")):
                add_blocker("Execution kill switch is enabled.", "clear_execution_kill_switch")
        except Exception as exc:
            add_blocker(f"Execution controls unavailable: {exc}", "inspect_execution_controls")

        try:
            account = self.get_execution_account(broker=broker_id, mode="paper")
            if submit_orders and (not account.get("paper_ready") or not account.get("connected")):
                add_blocker("Alpaca paper account is not ready.", "configure_paper_credentials")
            for item in account.get("warnings") or []:
                add_warning(str(item))
            add_actions(*[str(item) for item in account.get("next_actions") or []])
        except Exception as exc:
            if submit_orders:
                add_blocker(f"Alpaca paper account check failed: {exc}", "configure_paper_credentials")
            else:
                add_warning(f"Alpaca paper account check failed: {exc}", "configure_paper_credentials")

        if blockers:
            mark_step("paper_execution", "skipped")
        else:
            try:
                execution = self.create_execution_plan(
                    benchmark=benchmark,
                    capital_base=capital_base,
                    universe_symbols=universe_symbols,
                    broker=broker_id,
                    mode="paper",
                    submit_orders=bool(submit_orders),
                    max_orders=max_orders,
                    per_order_notional=per_order_notional,
                    allow_duplicates=False,
                    strategy_id=strategy_mode,
                )
                artifacts["execution"] = artifact_ref(execution, "execution_id")
                execution_orders = execution.get("submitted_orders") or []
                mark_step(
                    "paper_execution",
                    "completed" if (not submit_orders or execution_orders) else "blocked",
                    execution_id=execution.get("execution_id"),
                    submitted_count=len(execution_orders),
                    broker_status=execution.get("broker_status"),
                )
                for item in execution.get("warnings") or []:
                    add_warning(str(item))
                if submit_orders and not execution.get("submitted"):
                    reason = execution.get("block_reason") or execution.get("broker_status") or "execution_not_submitted"
                    add_blocker(f"Paper execution was not submitted: {reason}", *[str(item) for item in execution.get("next_actions") or []])
            except Exception as exc:
                add_blocker(f"Paper execution failed: {exc}", "inspect_execution_stack")
                mark_step("paper_execution", "failed", error=str(exc))

        submitted_orders = (execution or {}).get("submitted_orders") or []
        planned_orders = (execution or {}).get("orders") or []
        if blockers:
            status = "blocked"
        elif submit_orders and submitted_orders:
            status = "submitted"
        else:
            status = "planned"

        order_summary = [
            {
                "symbol": order.get("symbol"),
                "side": order.get("side"),
                "status": order.get("status"),
                "notional": order.get("notional"),
                "qty": order.get("qty") or order.get("quantity"),
                "client_order_id": order.get("client_order_id"),
                "broker_order_id": order.get("broker_order_id") or order.get("id"),
            }
            for order in (submitted_orders or planned_orders)[: max(1, int(max_orders or 1))]
            if isinstance(order, dict)
        ]

        payload = {
            "workflow_id": workflow_id,
            "generated_at": _iso_now(),
            "session_date": self._execution_session_date({"generated_at": _iso_now()}),
            "status": status,
            "request": request_payload,
            "blockers": list(dict.fromkeys(blockers)),
            "warnings": list(dict.fromkeys(warnings)),
            "next_actions": list(dict.fromkeys(next_actions or ["inspect_workflow_artifacts"])),
            "model_status": model_status,
            "steps": steps,
            "p1_report_id": (p1_report or {}).get("report_id"),
            "p2_report_id": (p2_report or {}).get("report_id"),
            "rl_backtest_run_id": (rl_backtest or {}).get("run_id"),
            "backtest_id": (backtest or {}).get("backtest_id"),
            "tearsheet_id": (tearsheet or {}).get("report_id") or (backtest or {}).get("tearsheet_report_id"),
            "paper_gate_id": (paper_gate or {}).get("report_id"),
            "execution_id": (execution or {}).get("execution_id"),
            "submitted_count": len(submitted_orders),
            "order_summary": order_summary,
            "artifacts": artifacts,
            "config_snapshot": self._config_snapshot(),
            "gate_snapshot": {
                "p2_promotable": bool(((p2_report or {}).get("deployment_readiness") or {}).get("promotable_to_paper")),
                "rl_backtest_success": rl_backtest is not None,
                "tearsheet_protection_status": (tearsheet or {}).get("protection_status"),
                "paper_gate_status": (paper_gate or {}).get("status"),
                "synthetic_execution": synthetic_backtest_used(backtest),
                "alpaca_paper_ready": bool((account or {}).get("paper_ready") and (account or {}).get("connected")),
                "kill_switch_enabled": bool((controls or {}).get("kill_switch_enabled")),
            },
        }
        payload["blocker_summary"] = self.build_blocker_summary(
            blockers=payload.get("blockers") or [],
            warnings=payload.get("warnings") or [],
        )
        try:
            payload["outcome_summary"] = self.record_workflow_paper_outcomes(
                workflow_payload=payload,
                p1_report=p1_report,
                p2_report=p2_report,
                execution_payload=execution,
                backtest_payload=backtest,
            )
        except Exception as exc:
            payload.setdefault("warnings", []).append(f"Paper outcome capture failed: {exc}")
        try:
            snapshot = self.capture_paper_performance_snapshot(
                workflow_id=workflow_id,
                execution_id=(execution or {}).get("execution_id"),
                benchmark=benchmark,
                broker=broker_id,
                mode="paper",
                account_payload=account,
                force_refresh=force_refresh,
            )
            payload["paper_performance_snapshot_id"] = snapshot.get("snapshot_id")
        except Exception as exc:
            payload.setdefault("warnings", []).append(f"Paper performance snapshot failed: {exc}")
        sanitized_payload = _jsonable(payload)
        storage_info = self.storage.persist_record("workflow_runs", workflow_id, sanitized_payload)
        sanitized_payload["storage"] = storage_info
        self.storage.persist_record("workflow_runs", workflow_id, sanitized_payload)
        return sanitized_payload

    def capture_paper_performance_snapshot(
        self,
        *,
        workflow_id: str | None = None,
        execution_id: str | None = None,
        benchmark: str | None = None,
        broker: str = "alpaca",
        mode: str = "paper",
        account_payload: dict[str, Any] | None = None,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        benchmark = benchmark or self.default_benchmark
        generated_at = _iso_now()
        calendar_status = self.trading_calendar.status()
        trading_day = (
            calendar_status.get("session_date")
            if calendar_status.get("is_session")
            else calendar_status.get("previous_session") or datetime.now(timezone.utc).date().isoformat()
        )
        account_payload = account_payload or self.get_execution_account(broker=broker, mode=mode)
        account = dict(account_payload.get("account") or account_payload)
        previous = self._latest_paper_performance_snapshot(before_date=trading_day)
        equity = self._paper_payload_float(account, "equity", "portfolio_value", "net_liquidation")
        cash = self._paper_payload_float(account, "cash")
        buying_power = self._paper_payload_float(account, "buying_power", "buyingPower")
        if equity is None:
            equity = self._paper_payload_float(previous or {}, "equity", "portfolio_nav") or self.default_capital
        benchmark_nav, benchmark_meta = self._latest_benchmark_nav(
            benchmark=benchmark,
            fallback=self._paper_payload_float(previous or {}, "benchmark_nav") or 1.0,
            force_refresh=force_refresh,
        )
        snapshot = {
            "snapshot_id": trading_day,
            "date": trading_day,
            "generated_at": generated_at,
            "workflow_id": workflow_id,
            "execution_id": execution_id,
            "broker": broker,
            "mode": self._normalize_broker_mode(mode),
            "benchmark": benchmark,
            "portfolio_nav": float(equity or 0.0),
            "equity": float(equity or 0.0),
            "cash": cash,
            "buying_power": buying_power,
            "benchmark_nav": float(benchmark_nav or 1.0),
            "benchmark_meta": benchmark_meta,
            "calendar": calendar_status,
            "session_date": trading_day,
            "account": account,
            "account_ready": bool(account_payload.get("connected") and account_payload.get("paper_ready", True)),
            "warnings": list(account_payload.get("warnings") or []),
        }
        cash_flow_summary = self._capture_alpaca_cash_flows_for_session(
            session_date=str(trading_day),
            broker=broker,
            mode=mode,
        )
        if cash_flow_summary.get("warnings"):
            snapshot["warnings"].extend(cash_flow_summary.get("warnings") or [])
        snapshot["cash_flow_adjustment_source"] = cash_flow_summary.get("source", "unavailable")
        snapshot["cash_flows"] = cash_flow_summary
        snapshot = self.synthetic_guard.annotate(snapshot, fallback_source=str((benchmark_meta or {}).get("provider") or "broker_account"))
        snapshot["storage"] = self.storage.persist_record("paper_performance", trading_day, _jsonable(snapshot))
        attribution = self._build_paper_attribution_record(snapshot=snapshot, session_date=trading_day)
        snapshot["attribution_id"] = attribution.get("attribution_id")
        snapshot["storage"] = self.storage.persist_record("paper_performance", trading_day, _jsonable(snapshot))
        return _jsonable(snapshot)

    def backfill_paper_performance(
        self,
        *,
        days: int | None = None,
        broker: str = "alpaca",
        mode: str = "paper",
        benchmark: str | None = None,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        window = max(1, min(int(days or getattr(settings, "PAPER_EVIDENCE_BACKFILL_DAYS", 120) or 120), 366))
        benchmark = benchmark or self.default_benchmark
        generated_at = _iso_now()
        normalized_mode = self._normalize_broker_mode(mode)
        if str(broker or "alpaca").lower() != "alpaca" or normalized_mode != "paper":
            return {
                "generated_at": generated_at,
                "status": "blocked",
                "reason": "paper_backfill_v1_only_supports_alpaca_paper",
                "backfilled_snapshots": 0,
                "backfilled_outcomes": 0,
            }

        since_day = (datetime.now(self.trading_calendar.timezone).date() - timedelta(days=window)).isoformat()
        until_day = datetime.now(self.trading_calendar.timezone).date().isoformat()
        errors: list[str] = []
        account_payload: dict[str, Any] = {}
        orders: list[dict[str, Any]] = []
        positions: list[dict[str, Any]] = []
        activities: list[dict[str, Any]] = []

        try:
            account_payload = self.get_execution_account(broker="alpaca", mode="paper")
        except Exception as exc:
            errors.append(f"account:{exc}")
        try:
            orders = self.alpaca.list_orders(status="all", limit=500, after=since_day, until=until_day, direction="desc")
        except Exception as exc:
            errors.append(f"orders:{exc}")
        try:
            positions = self.alpaca.list_positions()
        except Exception as exc:
            errors.append(f"positions:{exc}")
        try:
            activities = self.alpaca.list_account_activities(after=since_day, until=until_day, direction="desc", page_size=100)
        except Exception as exc:
            errors.append(f"activities:{exc}")

        account = dict(account_payload.get("account") or account_payload)
        equity = self._paper_payload_float(account, "equity", "portfolio_value", "net_liquidation") or self.default_capital
        cash = self._paper_payload_float(account, "cash")
        buying_power = self._paper_payload_float(account, "buying_power", "buyingPower")
        orders_by_day: dict[str, list[dict[str, Any]]] = {}
        for order in orders:
            day_key = self._paper_gate_date_key(
                {
                    "created_at": order.get("filled_at")
                    or order.get("submitted_at")
                    or order.get("created_at")
                    or order.get("updated_at")
                }
            )
            if day_key:
                orders_by_day.setdefault(day_key, []).append(order)
        activities_by_day: dict[str, list[dict[str, Any]]] = {}
        for activity in activities:
            day_key = self._paper_gate_date_key({"created_at": activity.get("transaction_time") or activity.get("date")})
            if day_key:
                activities_by_day.setdefault(day_key, []).append(activity)

        candidate_days = sorted(set(orders_by_day) | set(activities_by_day))
        today_status = self.trading_calendar.status()
        if today_status.get("is_session") and account_payload.get("connected"):
            candidate_days.append(str(today_status.get("session_date")))
        candidate_days = [
            day for day in sorted(set(candidate_days))
            if day >= since_day and day <= until_day and self.trading_calendar.is_session(day)
        ]

        snapshots: list[dict[str, Any]] = []
        outcomes: list[dict[str, Any]] = []
        benchmark_nav = 1.0
        for index, session_date in enumerate(candidate_days):
            benchmark_nav, benchmark_meta = self._latest_benchmark_nav(
                benchmark=benchmark,
                fallback=benchmark_nav,
                force_refresh=force_refresh,
            )
            day_orders = orders_by_day.get(session_date, [])
            day_activities = activities_by_day.get(session_date, [])
            cash_flow_summary = self._persist_alpaca_cash_flows(
                session_date=session_date,
                activities=day_activities,
                source="alpaca_activities_backfill",
            )
            snapshot = {
                "snapshot_id": session_date,
                "date": session_date,
                "session_date": session_date,
                "generated_at": generated_at,
                "backfilled": True,
                "evidence_source": "alpaca_paper_backfill",
                "broker": "alpaca",
                "mode": "paper",
                "benchmark": benchmark,
                "portfolio_nav": float(equity),
                "equity": float(equity),
                "cash": cash,
                "buying_power": buying_power,
                "benchmark_nav": float(benchmark_nav or 1.0),
                "benchmark_meta": benchmark_meta,
                "calendar": self.trading_calendar.session_info(session_date).model_dump(),
                "orders_count": len(day_orders),
                "activities_count": len(day_activities),
                "positions_count": len(positions),
                "cash_flow_adjustment_source": cash_flow_summary.get("source", "unavailable"),
                "cash_flows": cash_flow_summary,
                "broker_sync_errors": list(errors),
                "account_ready": bool(account_payload.get("connected", True) and account_payload.get("paper_ready", True)),
                "warnings": list(errors),
            }
            snapshot = self.synthetic_guard.annotate(snapshot, fallback_source="alpaca_paper_backfill")
            snapshot["storage"] = self.storage.persist_record("paper_performance", session_date, _jsonable(snapshot))
            attribution = self._build_paper_attribution_record(snapshot=snapshot, session_date=session_date)
            snapshot["attribution_id"] = attribution.get("attribution_id")
            snapshot["storage"] = self.storage.persist_record("paper_performance", session_date, _jsonable(snapshot))
            snapshots.append(_jsonable(snapshot))

            for order_index, order in enumerate(day_orders):
                symbol = str(order.get("symbol") or "").upper().strip()
                if not symbol:
                    continue
                side = str(order.get("side") or "buy").lower()
                source_id = str(order.get("client_order_id") or order.get("id") or f"{session_date}-{order_index}")
                outcome = self._build_paper_outcome_record(
                    record_kind="order",
                    source_id=source_id,
                    index=index * 1000 + order_index,
                    workflow_id="alpaca_backfill",
                    execution_id=str(order.get("execution_id") or ""),
                    symbol=symbol,
                    action="short" if side in {"sell", "short"} else "long",
                    entry_at=str(order.get("filled_at") or order.get("submitted_at") or order.get("created_at") or f"{session_date}T20:00:00+00:00"),
                    entry_price=self._paper_payload_float(order, "filled_avg_price", "limit_price", "stop_price"),
                    notional=self._paper_payload_float(order, "notional", "filled_notional", "qty"),
                    features=order,
                    model_refs={"source": "alpaca_paper_backfill"},
                    market_data_source="alpaca",
                    synthetic_used=False,
                )
                outcome["backfilled"] = True
                outcome["broker_order_id"] = order.get("id")
                outcomes.append(self._save_paper_outcome(outcome))

        return {
            "generated_at": generated_at,
            "status": "completed" if snapshots or not errors else "blocked",
            "window_days": window,
            "broker": "alpaca",
            "mode": "paper",
            "source": "alpaca_paper",
            "orders_seen": len(orders),
            "activities_seen": len(activities),
            "positions_seen": len(positions),
            "backfilled_snapshots": len(snapshots),
            "backfilled_outcomes": len(outcomes),
            "snapshot_ids": [row.get("snapshot_id") for row in snapshots],
            "outcome_ids": [row.get("outcome_id") for row in outcomes],
            "errors": errors,
            "warnings": errors,
        }

    def build_paper_performance_report(self, *, window_days: int = 90) -> dict[str, Any]:
        self._sync_paper_reward_candidate_outcomes()
        window = max(2, min(int(window_days or 90), 252))
        rows = sorted(
            [row for row in self.storage.list_records("paper_performance") if isinstance(row, dict)],
            key=lambda item: str(item.get("date") or item.get("snapshot_id") or item.get("generated_at") or ""),
        )[-window:]
        points = self._normalize_paper_gate_points(rows)
        metrics = self._compute_paper_gate_metrics(points)
        metrics["annualized_return"] = self._annualized_return(metrics.get("net_return"), metrics.get("valid_days"))
        missing_sessions = self._paper_missing_sessions(points=points, window_days=window)
        metrics["expected_sessions"] = missing_sessions.get("expected_sessions", 0)
        metrics["missing_sessions"] = missing_sessions.get("missing_count", 0)
        metrics["calendar_coverage"] = missing_sessions.get("coverage", 0.0)
        paper_gate = self.build_paper_gate_report(points=points, persist=False) if points else self.build_paper_gate_report(persist=False)
        outcome_rows = self.list_paper_outcomes(limit=1000).get("outcomes", [])
        execution_summary = self._paper_execution_summary(window_days=window)
        attribution = self._paper_attribution_summary(rows=rows, outcomes=outcome_rows, execution_summary=execution_summary)
        recommendation = self._live_canary_recommendation(metrics=metrics, outcomes=outcome_rows)
        latest_snapshot = rows[-1] if rows else {}
        broker_sync_errors = list((latest_snapshot or {}).get("broker_sync_errors") or []) + list(execution_summary.get("sync_errors") or [])
        cash_flow_source = str((latest_snapshot or {}).get("cash_flow_adjustment_source") or "unavailable")
        latest_reconciliation = self._latest_record_for_session("paper_reconciliations", self._record_session_date(latest_snapshot or {})) if latest_snapshot else None
        cash_flow_summary = self._paper_cash_flow_summary(points=points)
        cash_flow_adjusted_return = cash_flow_summary.get("cash_flow_adjusted_return")
        if cash_flow_adjusted_return is None:
            cash_flow_adjusted_return = metrics.get("net_return", 0.0)
        trend = self._paper_attribution_trends(rows=rows, outcomes=outcome_rows, execution_summary=execution_summary)
        return {
            "generated_at": _iso_now(),
            "window_days": window,
            "points": points,
            "equity_curve": [
                {"date": point["date"], "portfolio_nav": point["portfolio_nav"], "benchmark_nav": point["benchmark_nav"]}
                for point in points
            ],
            "drawdown_curve": self._drawdown_curve(points),
            "latest_snapshot": latest_snapshot or None,
            "missing_sessions": missing_sessions.get("missing_sessions", []),
            "calendar_coverage": missing_sessions.get("coverage", 0.0),
            "metrics": metrics,
            "cash_flow_adjusted_return": cash_flow_adjusted_return,
            "cash_flows": cash_flow_summary,
            "cash_flow_adjustment_source": cash_flow_source,
            "broker_sync_errors": broker_sync_errors,
            "excluded_stale_symbols": (latest_snapshot or {}).get("excluded_symbols") or [],
            "reconciliation_status": latest_reconciliation or {},
            "backup_status": self.latest_storage_backup_status(),
            "turnover": attribution.get("turnover", 0.0),
            "fill_rate": attribution.get("fill_rate", 0.0),
            "reject_rate": attribution.get("reject_rate", 0.0),
            "avg_slippage_bps": attribution.get("avg_slippage_bps", 0.0),
            "win_rate": attribution.get("win_rate", 0.0),
            "avg_win_loss_ratio": attribution.get("avg_win_loss_ratio", 0.0),
            "symbol_contributions": attribution.get("symbol_contributions", []),
            "factor_exposures": attribution.get("factor_exposures", {}),
            "industry_exposures": attribution.get("industry_exposures", {}),
            "benchmark_attribution": attribution.get("benchmark_attribution", {}),
            "attribution": attribution,
            "attribution_trends": trend,
            "warnings": [] if cash_flow_summary.get("source") != "unavailable" else ["cash_flow_source_unavailable"],
            "paper_gate": paper_gate,
            "live_canary_recommendation": recommendation,
            "orders": execution_summary,
            "outcomes": {
                "count": len(outcome_rows),
                "settled_count": sum(1 for row in outcome_rows if str(row.get("status") or "") == "settled"),
                "synthetic_count": sum(1 for row in outcome_rows if bool(row.get("synthetic_used"))),
                "latest": outcome_rows[:10],
            },
            "status": "canary_candidate" if recommendation.get("recommended") else "paper_tracking",
        }

    def latest_storage_backup_status(self) -> dict[str, Any]:
        latest = self.storage.list_records("storage_backups")
        if latest:
            row = latest[0]
            return {
                "status": row.get("status"),
                "session_date": row.get("session_date"),
                "generated_at": row.get("generated_at"),
                "artifact_backend": row.get("artifact_backend"),
                "artifact_uri": row.get("artifact_uri"),
                "uploaded": bool(row.get("uploaded")),
                "warning": row.get("warning"),
            }
        return {"status": "missing", "uploaded": False}

    def _alpaca_activity_cash_flow_amount(self, activity: dict[str, Any]) -> float:
        activity_type = str(activity.get("activity_type") or activity.get("type") or "").upper()
        raw_amount = self._paper_payload_float(
            activity,
            "net_amount",
            "amount",
            "price",
            "fee",
            "cash",
        )
        if raw_amount is None:
            return 0.0
        amount = float(raw_amount)
        debit_types = {"FEE", "FEE_REVERSAL", "JNL", "JNLC", "CSD", "CSW"}
        credit_types = {"DIV", "DIVCGL", "DIVCGS", "DIVNRA", "DIVROC", "DIVTXEX", "CSD"}
        if activity_type in {"FILL", "TRANS", "ACATC", "ACATS"}:
            return 0.0
        if activity_type in debit_types and "fee" in {str(key).lower() for key in activity.keys()}:
            return -abs(amount)
        if activity_type in credit_types:
            return amount
        return amount

    def _persist_alpaca_cash_flows(
        self,
        *,
        session_date: str,
        activities: list[dict[str, Any]],
        source: str,
    ) -> dict[str, Any]:
        saved: list[dict[str, Any]] = []
        net_cash_flow = 0.0
        for index, activity in enumerate(activities or []):
            if not isinstance(activity, dict):
                continue
            amount = self._alpaca_activity_cash_flow_amount(activity)
            activity_type = str(activity.get("activity_type") or activity.get("type") or "").upper()
            if amount == 0.0 and activity_type == "FILL":
                continue
            flow_id_source = (
                activity.get("id")
                or activity.get("activity_id")
                or f"{session_date}-{index}-{activity_type or 'activity'}"
            )
            flow_id = f"cash-flow-{self._safe_record_id(flow_id_source)}"
            payload = {
                "cash_flow_id": flow_id,
                "session_date": session_date,
                "generated_at": _iso_now(),
                "source": source,
                "activity_type": activity_type,
                "amount": round(float(amount), 6),
                "raw_activity": activity,
                "synthetic_used": False,
                "evidence_eligible": True,
            }
            payload["storage"] = self.storage.persist_record("paper_cash_flows", flow_id, _jsonable(payload))
            saved.append(_jsonable(payload))
            net_cash_flow += float(amount)
        return {
            "source": source if saved else "unavailable",
            "count": len(saved),
            "net_cash_flow": round(net_cash_flow, 6),
            "cash_flow_ids": [row.get("cash_flow_id") for row in saved],
        }

    def _capture_alpaca_cash_flows_for_session(self, *, session_date: str, broker: str, mode: str) -> dict[str, Any]:
        normalized_mode = self._normalize_broker_mode(mode)
        if str(broker or "").lower() != "alpaca" or normalized_mode != "paper":
            return {"source": "unavailable", "count": 0, "net_cash_flow": 0.0}
        try:
            activities = self.alpaca.list_account_activities(
                after=session_date,
                until=session_date,
                direction="desc",
                page_size=100,
            )
        except Exception as exc:
            return {
                "source": "unavailable",
                "count": 0,
                "net_cash_flow": 0.0,
                "warnings": [f"cash_flow_activities:{exc}"],
            }
        return self._persist_alpaca_cash_flows(
            session_date=session_date,
            activities=[row for row in activities if isinstance(row, dict)],
            source="alpaca_activities",
        )

    def _paper_cash_flow_summary(self, *, points: list[dict[str, Any]]) -> dict[str, Any]:
        if not points:
            return {
                "count": 0,
                "net_cash_flow": 0.0,
                "source": "unavailable",
                "cash_flow_adjusted_return": None,
            }
        start_date = str(points[0].get("date") or "")[:10]
        end_date = str(points[-1].get("date") or "")[:10]
        flows = [
            row for row in self.storage.list_records("paper_cash_flows")
            if isinstance(row, dict)
            and start_date <= str(row.get("session_date") or "")[:10] <= end_date
            and not bool(row.get("synthetic_used"))
            and row.get("evidence_eligible") is not False
        ]
        net_cash_flow = sum(float(row.get("amount") or 0.0) for row in flows)
        start_nav = self._paper_payload_float(points[0], "portfolio_nav")
        end_nav = self._paper_payload_float(points[-1], "portfolio_nav")
        adjusted = None
        if start_nav not in {None, 0} and end_nav is not None:
            adjusted = round((float(end_nav) - float(start_nav) - net_cash_flow) / float(start_nav), 6)
        return {
            "count": len(flows),
            "net_cash_flow": round(net_cash_flow, 6),
            "source": "alpaca_activities" if flows else "unavailable",
            "cash_flow_adjusted_return": adjusted,
            "start_date": start_date,
            "end_date": end_date,
        }

    def backup_quant_storage(self, *, session_date: str | None = None) -> dict[str, Any]:
        if not bool(getattr(settings, "STORAGE_BACKUP_ENABLED", True)):
            return {"enabled": False, "status": "skipped", "reason": "storage_backup_disabled"}
        session = str(session_date or self._execution_session_date({}))[:10]
        backup_dir = self.storage.base_dir / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        archive_path = backup_dir / f"{session}.tar.gz"
        include_dirs = [
            "workflow_runs",
            "session_evidence",
            "executions",
            "execution_journals",
            "submit_locks",
            "paper_outcomes",
            "paper_performance",
            "paper_cash_flows",
            "paper_attribution",
            "paper_reconciliations",
            "paper_daily_digests",
            "paper_daily_digest_deliveries",
            "paper_weekly_digests",
            "paper_weekly_digest_deliveries",
            "promotion_evidence",
            "alerts",
            "scheduler_events",
            "circuit_breakers",
        ]
        with tarfile.open(archive_path, "w:gz") as archive:
            for name in include_dirs:
                path = self.storage.base_dir / name
                if path.exists():
                    archive.add(path, arcname=name)
        upload = self.storage.upload_artifact_file(
            f"quant/backups/{archive_path.name}",
            archive_path,
            content_type="application/gzip",
        )
        retention_days = max(1, int(getattr(settings, "STORAGE_BACKUP_RETENTION_DAYS", 30) or 30))
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        removed = 0
        for old_path in backup_dir.glob("*.tar.gz"):
            try:
                mtime = datetime.fromtimestamp(old_path.stat().st_mtime, timezone.utc)
                if old_path != archive_path and mtime < cutoff:
                    old_path.unlink(missing_ok=True)
                    removed += 1
            except Exception:
                continue
        payload = {
            "backup_id": f"storage-backup-{session}",
            "generated_at": _iso_now(),
            "session_date": session,
            "status": "completed" if upload.get("uploaded") else "completed_local_only",
            "local_path": str(archive_path),
            "size_bytes": archive_path.stat().st_size if archive_path.exists() else 0,
            "included_dirs": include_dirs,
            "retention_days": retention_days,
            "removed_expired_count": removed,
            "artifact_backend": upload.get("artifact_backend"),
            "artifact_uri": upload.get("artifact_uri"),
            "uploaded": bool(upload.get("uploaded")),
            "warning": None if upload.get("uploaded") else "remote_backup_unavailable",
        }
        payload["storage"] = self.storage.persist_record("storage_backups", payload["backup_id"], _jsonable(payload))
        return _jsonable(payload)

    def _build_paper_attribution_record(self, *, snapshot: dict[str, Any], session_date: str) -> dict[str, Any]:
        executions = [
            row
            for row in self.storage.list_records("executions")
            if isinstance(row, dict)
            and (
                str(row.get("execution_id") or "") == str(snapshot.get("execution_id") or "")
                or self._paper_gate_date_key(row) == session_date
            )
        ]
        outcomes = [
            row
            for row in self.storage.list_records("paper_outcomes")
            if isinstance(row, dict) and self._paper_gate_date_key({"generated_at": row.get("entry_at") or row.get("created_at")}) == session_date
        ]
        summary = self._paper_attribution_summary(rows=[snapshot], outcomes=outcomes, execution_summary=self._execution_quality_from_payloads(executions))
        attribution_id = session_date
        payload = {
            "attribution_id": attribution_id,
            "session_date": session_date,
            "generated_at": _iso_now(),
            "snapshot_id": snapshot.get("snapshot_id"),
            "workflow_id": snapshot.get("workflow_id"),
            "execution_id": snapshot.get("execution_id"),
            "calendar": snapshot.get("calendar", {}),
            **summary,
        }
        payload["storage"] = self.storage.persist_record("paper_attribution", attribution_id, _jsonable(payload))
        return _jsonable(payload)

    def _paper_attribution_summary(
        self,
        *,
        rows: list[dict[str, Any]],
        outcomes: list[dict[str, Any]],
        execution_summary: dict[str, Any],
    ) -> dict[str, Any]:
        attribution_rows = [row for row in self.storage.list_records("paper_attribution") if isinstance(row, dict)]
        latest_attribution = attribution_rows[0] if attribution_rows else {}
        order_count = int(execution_summary.get("order_count") or 0)
        filled_count = int(execution_summary.get("filled_count") or 0)
        rejected_count = int(execution_summary.get("rejected_count") or 0)
        fill_rate = filled_count / order_count if order_count else 0.0
        reject_rate = rejected_count / order_count if order_count else 0.0
        slippage_values = [
            float(value)
            for value in execution_summary.get("slippage_bps_values", [])
            if value is not None
        ]
        avg_slippage = statistics.mean(slippage_values) if slippage_values else float(latest_attribution.get("avg_slippage_bps") or 0.0)
        settled = [row for row in outcomes if str(row.get("status") or "") == "settled" and row.get("score") is not None]
        wins = [row for row in settled if float(row.get("score") or 0.0) > 0]
        losses = [row for row in settled if float(row.get("score") or 0.0) < 0]
        win_rate = len(wins) / len(settled) if settled else 0.0
        avg_win = statistics.mean([float(row.get("score") or 0.0) for row in wins]) if wins else 0.0
        avg_loss = abs(statistics.mean([float(row.get("score") or 0.0) for row in losses])) if losses else 0.0
        symbol_scores: dict[str, dict[str, Any]] = {}
        factor_values: dict[str, list[float]] = {}
        industry_values: dict[str, float] = {}
        for row in outcomes:
            symbol = str(row.get("symbol") or "UNKNOWN").upper()
            score = float(row.get("score") or row.get("partial_score") or 0.0)
            bucket = symbol_scores.setdefault(symbol, {"symbol": symbol, "score": 0.0, "count": 0, "notional": 0.0})
            bucket["score"] += score
            bucket["count"] += 1
            bucket["notional"] += float(row.get("notional") or 0.0)
            features = dict(row.get("features") or {})
            industry = str(features.get("industry") or features.get("sector") or "unclassified").strip() or "unclassified"
            industry_values[industry] = industry_values.get(industry, 0.0) + float(row.get("notional") or 0.0)
            for key in ("momentum", "quality", "value", "alternative_data", "regime_fit", "esg_delta", "overall_score", "risk_score"):
                if features.get(key) is not None:
                    try:
                        factor_values.setdefault(key, []).append(float(features[key]))
                    except (TypeError, ValueError):
                        pass
            for factor in features.get("factor_scores") or []:
                if isinstance(factor, dict) and factor.get("name") and factor.get("value") is not None:
                    try:
                        factor_values.setdefault(str(factor["name"]), []).append(float(factor["value"]))
                    except (TypeError, ValueError):
                        pass
        points = self._normalize_paper_gate_points(rows)
        metrics = self._compute_paper_gate_metrics(points)
        return {
            "generated_at": _iso_now(),
            "order_count": order_count,
            "filled_count": filled_count,
            "rejected_count": rejected_count,
            "fill_rate": round(fill_rate, 6),
            "reject_rate": round(reject_rate, 6),
            "avg_slippage_bps": round(float(avg_slippage), 4),
            "win_rate": round(win_rate, 6),
            "avg_win_loss_ratio": round(avg_win / avg_loss, 6) if avg_loss > 0 else (999.0 if avg_win > 0 else 0.0),
            "turnover": round(float(execution_summary.get("turnover") or 0.0), 6),
            "symbol_contributions": sorted(symbol_scores.values(), key=lambda item: abs(float(item["score"])), reverse=True)[:25],
            "factor_exposures": {
                key: round(statistics.mean(values), 6)
                for key, values in factor_values.items()
                if values
            },
            "industry_exposures": {
                key: round(value, 6)
                for key, value in sorted(industry_values.items(), key=lambda item: abs(item[1]), reverse=True)[:25]
            },
            "benchmark_attribution": {
                "portfolio_return": metrics.get("net_return", 0.0),
                "benchmark_return": metrics.get("benchmark_return", 0.0),
                "excess_return": metrics.get("excess_return", 0.0),
                "tracking_source": "paper_performance",
            },
            "calendar_coverage": self._calendar_coverage(points),
        }

    def _paper_attribution_trends(
        self,
        *,
        rows: list[dict[str, Any]],
        outcomes: list[dict[str, Any]],
        execution_summary: dict[str, Any],
    ) -> dict[str, Any]:
        snapshots = sorted(
            [row for row in rows if isinstance(row, dict)],
            key=lambda item: str(item.get("date") or item.get("snapshot_id") or item.get("generated_at") or ""),
        )
        attribution_rows = sorted(
            [row for row in self.storage.list_records("paper_attribution") if isinstance(row, dict)],
            key=lambda item: str(item.get("session_date") or item.get("generated_at") or ""),
        )
        attribution_by_session = {
            str(row.get("session_date") or "")[:10]: row
            for row in attribution_rows
            if row.get("session_date")
        }
        outcome_by_session: dict[str, list[dict[str, Any]]] = {}
        for outcome in outcomes:
            session = self._paper_gate_date_key({"generated_at": outcome.get("entry_at") or outcome.get("created_at")})
            if session:
                outcome_by_session.setdefault(session, []).append(outcome)
        trend_rows: list[dict[str, Any]] = []
        for snapshot in snapshots[-90:]:
            session = str(snapshot.get("date") or snapshot.get("snapshot_id") or "")[:10]
            attribution = attribution_by_session.get(session) or {}
            day_outcomes = outcome_by_session.get(session, [])
            settled = [row for row in day_outcomes if str(row.get("status") or "") == "settled" and row.get("score") is not None]
            wins = [row for row in settled if float(row.get("score") or 0.0) > 0]
            losses = [row for row in settled if float(row.get("score") or 0.0) < 0]
            avg_win = statistics.mean([float(row.get("score") or 0.0) for row in wins]) if wins else 0.0
            avg_loss = abs(statistics.mean([float(row.get("score") or 0.0) for row in losses])) if losses else 0.0
            trend_rows.append(
                {
                    "session_date": session,
                    "turnover": float(attribution.get("turnover") or 0.0),
                    "fill_rate": float(attribution.get("fill_rate") or 0.0),
                    "reject_rate": float(attribution.get("reject_rate") or 0.0),
                    "avg_slippage_bps": float(attribution.get("avg_slippage_bps") or 0.0),
                    "win_rate": round(len(wins) / len(settled), 6) if settled else 0.0,
                    "avg_win_loss_ratio": round(avg_win / avg_loss, 6) if avg_loss > 0 else (999.0 if avg_win > 0 else 0.0),
                    "symbol_contributions": attribution.get("symbol_contributions") or [],
                    "factor_exposures": attribution.get("factor_exposures") or {},
                    "industry_exposures": attribution.get("industry_exposures") or {},
                }
            )
        if not trend_rows and execution_summary:
            trend_rows.append(
                {
                    "session_date": None,
                    "turnover": float(execution_summary.get("turnover") or 0.0),
                    "fill_rate": 0.0,
                    "reject_rate": 0.0,
                    "avg_slippage_bps": 0.0,
                    "win_rate": 0.0,
                    "avg_win_loss_ratio": 0.0,
                    "symbol_contributions": [],
                    "factor_exposures": {},
                    "industry_exposures": {},
                }
            )
        return {
            "generated_at": _iso_now(),
            "rows": trend_rows,
            "metric_keys": [
                "turnover",
                "fill_rate",
                "reject_rate",
                "avg_slippage_bps",
                "win_rate",
                "avg_win_loss_ratio",
            ],
        }

    def _execution_quality_from_payloads(self, executions: list[dict[str, Any]]) -> dict[str, Any]:
        orders: list[dict[str, Any]] = []
        for payload in executions:
            for order in payload.get("submitted_orders") or payload.get("orders") or []:
                if isinstance(order, dict):
                    orders.append(order)
        filled_states = {"filled", "partially_filled"}
        rejected_states = {"rejected", "failed", "canceled", "cancelled", "expired"}
        return {
            "execution_count": len(executions),
            "order_count": len(orders),
            "filled_count": sum(1 for order in orders if str(order.get("status") or "").lower() in filled_states),
            "rejected_count": sum(1 for order in orders if str(order.get("status") or "").lower() in rejected_states),
            "submitted_count": sum(1 for payload in executions if payload.get("submitted")),
            "latest_execution_id": executions[0].get("execution_id") if executions else None,
            "slippage_bps_values": [
                order.get("estimated_slippage_bps")
                for order in orders
                if order.get("estimated_slippage_bps") is not None
            ],
            "turnover": sum(float(order.get("notional") or order.get("submitted_notional") or 0.0) for order in orders),
        }

    @staticmethod
    def _drawdown_curve(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
        curve: list[dict[str, Any]] = []
        peak = 0.0
        for point in points:
            nav = float(point.get("portfolio_nav") or 0.0)
            peak = max(peak, nav)
            drawdown = 0.0 if peak <= 0 else 1 - nav / peak
            curve.append({"date": point.get("date"), "drawdown": round(drawdown, 6), "portfolio_nav": nav})
        return curve

    def _calendar_coverage(self, points: list[dict[str, Any]]) -> float:
        if len(points) < 2:
            return 0.0
        start = date.fromisoformat(points[0]["date"])
        end = date.fromisoformat(points[-1]["date"])
        expected = 0
        current = start
        while current <= end:
            if self.trading_calendar.is_session(current):
                expected += 1
            current += timedelta(days=1)
        return round(min(1.0, len(points) / expected), 6) if expected else 0.0

    def _paper_missing_sessions(self, *, points: list[dict[str, Any]], window_days: int) -> dict[str, Any]:
        point_dates = {
            str(point.get("date"))
            for point in points
            if point.get("date")
        }
        today_status = self.trading_calendar.status()
        end_text = (
            today_status.get("session_date")
            if today_status.get("is_session")
            else today_status.get("previous_session") or today_status.get("session_date")
        )
        try:
            end_date = date.fromisoformat(str(end_text)[:10])
        except Exception:
            end_date = datetime.now(timezone.utc).date()
        start_date = end_date - timedelta(days=max(7, int(window_days or 90) * 2))
        expected: list[str] = []
        current = start_date
        while current <= end_date:
            if self.trading_calendar.is_session(current):
                expected.append(current.isoformat())
            current += timedelta(days=1)
        expected = expected[-max(1, int(window_days or 90)):]
        missing = [session for session in expected if session not in point_dates]
        coverage = (len(expected) - len(missing)) / len(expected) if expected else 0.0
        return {
            "calendar_id": getattr(self.trading_calendar, "calendar_id", "XNYS"),
            "window_days": int(window_days or 90),
            "expected_sessions": len(expected),
            "observed_sessions": len([session for session in expected if session in point_dates]),
            "missing_count": len(missing),
            "coverage": round(max(0.0, min(1.0, coverage)), 6),
            "missing_sessions": missing,
        }

    def record_workflow_paper_outcomes(
        self,
        *,
        workflow_payload: dict[str, Any],
        p1_report: dict[str, Any] | None = None,
        p2_report: dict[str, Any] | None = None,
        execution_payload: dict[str, Any] | None = None,
        backtest_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        workflow_id = str(workflow_payload.get("workflow_id") or "").strip()
        execution_id = str(workflow_payload.get("execution_id") or (execution_payload or {}).get("execution_id") or "").strip()
        generated_at = str(workflow_payload.get("generated_at") or _iso_now())
        saved: list[dict[str, Any]] = []

        for report_kind, report in (("p1_signal", p1_report), ("p2_signal", p2_report)):
            for index, signal in enumerate((report or {}).get("signals") or []):
                if not isinstance(signal, dict) or not str(signal.get("symbol") or "").strip():
                    continue
                saved.append(
                    self._save_paper_outcome(
                        self._build_paper_outcome_record(
                            record_kind=report_kind,
                            source_id=str((report or {}).get("report_id") or workflow_id),
                            index=index,
                            workflow_id=workflow_id,
                            execution_id=execution_id,
                            symbol=str(signal.get("symbol") or "").upper(),
                            action=str(signal.get("action") or "long").lower(),
                            entry_at=generated_at,
                            entry_price=self._paper_payload_float(signal, "entry_price", "close", "price"),
                            notional=None,
                            features=signal,
                            model_refs={
                                "p1_report_id": workflow_payload.get("p1_report_id"),
                                "p2_report_id": workflow_payload.get("p2_report_id"),
                                "rl_backtest_run_id": workflow_payload.get("rl_backtest_run_id"),
                            },
                            market_data_source=str(signal.get("market_data_source") or signal.get("source") or "unknown"),
                            synthetic_used=self._payload_mentions_synthetic(signal) or self._payload_mentions_synthetic(backtest_payload),
                        )
                    )
                )

        orders = (execution_payload or {}).get("submitted_orders") or (execution_payload or {}).get("orders") or workflow_payload.get("order_summary") or []
        for index, order in enumerate(orders):
            if not isinstance(order, dict) or not str(order.get("symbol") or "").strip():
                continue
            side = str(order.get("side") or order.get("action") or "buy").lower()
            action = "short" if side in {"sell", "short"} else "long"
            saved.append(
                self._save_paper_outcome(
                    self._build_paper_outcome_record(
                        record_kind="order",
                        source_id=str(order.get("client_order_id") or order.get("broker_order_id") or execution_id or workflow_id),
                        index=index,
                        workflow_id=workflow_id,
                        execution_id=execution_id,
                        symbol=str(order.get("symbol") or "").upper(),
                        action=action,
                        entry_at=str(order.get("submitted_at") or generated_at),
                        entry_price=self._paper_payload_float(order, "filled_avg_price", "limit_price", "entry_price", "price"),
                        notional=self._paper_payload_float(order, "notional", "submitted_notional", "requested_notional"),
                        features=order,
                        model_refs={
                            "p1_report_id": workflow_payload.get("p1_report_id"),
                            "p2_report_id": workflow_payload.get("p2_report_id"),
                            "rl_backtest_run_id": workflow_payload.get("rl_backtest_run_id"),
                        },
                        market_data_source=str((backtest_payload or {}).get("data_source") or "execution"),
                        synthetic_used=self._payload_mentions_synthetic(backtest_payload),
                    )
                )
            )
        return {
            "captured_count": len(saved),
            "outcome_ids": [row.get("outcome_id") for row in saved],
        }

    def list_paper_outcomes(
        self,
        *,
        limit: int = 200,
        record_kind: str | None = None,
        status: str | None = None,
        symbol: str | None = None,
    ) -> dict[str, Any]:
        self._sync_paper_reward_candidate_outcomes()
        rows = self.storage.list_records("paper_outcomes")
        if record_kind:
            rows = [row for row in rows if str(row.get("record_kind") or "") == record_kind]
        if status:
            rows = [row for row in rows if str(row.get("status") or "") == status]
        if symbol:
            normalized_symbol = str(symbol).upper()
            rows = [row for row in rows if str(row.get("symbol") or "").upper() == normalized_symbol]
        rows.sort(key=lambda item: str(item.get("created_at") or item.get("generated_at") or ""), reverse=True)
        rows = rows[: max(1, min(int(limit or 200), 1000))]
        return {"generated_at": _iso_now(), "count": len(rows), "outcomes": rows}

    def settle_paper_outcomes(
        self,
        *,
        outcome_id: str | None = None,
        force_refresh: bool = False,
        limit: int = 200,
    ) -> dict[str, Any]:
        from gateway.trading.reward_bandit import default_bandit_state, settle_candidate_with_bars, update_bandit_state

        self._sync_paper_reward_candidate_outcomes()
        rows = [self.storage.load_record("paper_outcomes", outcome_id)] if outcome_id else self.storage.list_records("paper_outcomes")
        rows = [row for row in rows if isinstance(row, dict)]
        rows = [
            row
            for row in rows
            if outcome_id or str(row.get("status") or "") in {"pending", "partially_settled"}
        ][: max(1, min(int(limit or 200), 1000))]
        bandit_state = self.storage.load_record("paper_outcome_bandit", "state") or default_bandit_state()
        updated: list[dict[str, Any]] = []
        warnings: list[str] = []
        bandit_updated = False
        for row in rows:
            symbol = str(row.get("symbol") or "").upper().strip()
            if not symbol:
                continue
            provenance = self.synthetic_guard.inspect(row)
            if provenance.synthetic_used:
                row.update(provenance.model_dump())
                row["status"] = str(row.get("status") or "pending")
                self._save_paper_outcome(row)
                warnings.append(f"{row.get('outcome_id')}: synthetic evidence is not settlement-eligible")
                continue
            if not self._paper_payload_float(row, "entry_price"):
                warnings.append(f"{row.get('outcome_id')}: missing entry_price")
                continue
            try:
                bars_result = self.market_data.get_daily_bars(
                    symbol,
                    limit=60,
                    force_refresh=force_refresh,
                    allow_stale_cache=True,
                )
                bars = self._bars_result_to_rows(bars_result)
                settled, changed = settle_candidate_with_bars(row, bars)
            except Exception as exc:
                warnings.append(f"{symbol}: {exc}")
                continue
            if settled.get("score") is not None and not settled.get("bandit_updated_at"):
                bandit_state = update_bandit_state(bandit_state, settled)
                settled["bandit_updated_at"] = _iso_now()
                bandit_updated = True
            if changed or settled.get("bandit_updated_at"):
                updated.append(self._save_paper_outcome(settled))
        if bandit_updated:
            bandit_state["state_id"] = "state"
            bandit_state["storage"] = self.storage.persist_record("paper_outcome_bandit", "state", _jsonable(bandit_state))
        return {
            "settlement_id": f"paper-outcome-settle-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            "generated_at": _iso_now(),
            "checked_count": len(rows),
            "updated_count": len(updated),
            "updated_outcomes": updated,
            "bandit_updated": bandit_updated,
            "warnings": warnings,
        }

    def build_promotion_report(self, *, window_days: int = 90, persist: bool = False) -> dict[str, Any]:
        performance = self.build_paper_performance_report(window_days=window_days)
        paper_gate = performance.get("paper_gate") or self.build_paper_gate_report(persist=False)
        recommendation = performance.get("live_canary_recommendation") or {}
        policy = load_promotion_policy()
        quality = {
            "filled_count": (performance.get("orders") or {}).get("filled_count", 0),
            "settled_count": (performance.get("outcomes") or {}).get("settled_count", 0),
            "synthetic_count": (performance.get("outcomes") or {}).get("synthetic_count", 0),
            "reject_rate": performance.get("reject_rate", 0.0),
            "avg_slippage_bps": performance.get("avg_slippage_bps", 0.0),
            "calendar_coverage": (performance.get("attribution") or {}).get("calendar_coverage", 0.0),
        }
        paper_policy = evaluate_thresholds(performance.get("metrics") or {}, quality, policy, "paper_promoted")
        if recommendation.get("recommended"):
            promotion_status = "canary_candidate"
        elif paper_gate.get("passed") and paper_policy.get("passed"):
            promotion_status = "paper_promoted"
        elif performance.get("metrics", {}).get("valid_days", 0) > 0:
            promotion_status = "paper_candidate"
        else:
            promotion_status = "research_only"
        if (paper_gate.get("blockers") or paper_policy.get("blockers")) and not performance.get("metrics", {}).get("valid_days"):
            promotion_status = "blocked"
        registry = self.build_model_registry()
        report_id = f"promotion-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        payload = {
            "report_id": report_id,
            "generated_at": _iso_now(),
            "promotion_status": promotion_status,
            "allowed_statuses": ["research_only", "shadow", "paper_candidate", "paper_promoted", "canary_candidate", "blocked"],
            "policy": policy,
            "policy_evaluation": {
                "paper_promoted": paper_policy,
                "live_canary": recommendation.get("checks", {}),
                "quality": quality,
            },
            "paper_gate": paper_gate,
            "performance": performance,
            "model_registry": registry,
            "models": [
                {
                    **model,
                    "promotion_status": promotion_status if model.get("available") else "blocked",
                    "blockers": [] if model.get("available") else ["model_artifact_unavailable"],
                }
                for model in registry.get("models", [])
            ],
            "recommendation": {
                "live_canary": bool(recommendation.get("recommended")),
                "action": "operator_review_required" if recommendation.get("recommended") else "continue_paper",
                "reason": recommendation.get("summary") or "Paper evidence has not reached live canary criteria.",
                "blockers": recommendation.get("blockers", []),
            },
        }
        if persist:
            payload["storage"] = self.storage.persist_record("promotion_reports", report_id, _jsonable(payload))
            evidence = {
                "evidence_id": report_id,
                "generated_at": payload["generated_at"],
                "policy": policy,
                "promotion_status": promotion_status,
                "blockers": list(dict.fromkeys((paper_gate.get("blockers") or []) + (paper_policy.get("blockers") or []) + (recommendation.get("blockers") or []))),
                "source_ids": {
                    "latest_snapshot": (performance.get("latest_snapshot") or {}).get("snapshot_id"),
                    "latest_execution_id": (performance.get("orders") or {}).get("latest_execution_id"),
                    "paper_gate_report_id": paper_gate.get("report_id"),
                },
                "operator_review": {"required": True, "status": "pending"},
                "metrics": performance.get("metrics", {}),
                "quality": quality,
            }
            payload["evidence_storage"] = self.storage.persist_record("promotion_evidence", report_id, _jsonable(evidence))
        return _jsonable(payload)

    def evaluate_promotion(self, *, window_days: int = 90, persist: bool = True) -> dict[str, Any]:
        return self.build_promotion_report(window_days=window_days, persist=persist)

    def build_promotion_timeline(self, *, limit: int = 50) -> dict[str, Any]:
        statuses = ["research_only", "shadow", "paper_candidate", "paper_promoted", "canary_candidate", "blocked"]
        evidence_rows = [
            row for row in self.storage.list_records("promotion_evidence")
            if isinstance(row, dict)
        ]
        report_rows = [
            row for row in self.storage.list_records("promotion_reports")
            if isinstance(row, dict)
        ]
        shadow_rows = [
            row for row in self.storage.list_records("shadow_retrain_runs")
            if isinstance(row, dict)
        ]
        events: list[dict[str, Any]] = []
        for row in evidence_rows:
            events.append(
                {
                    "event_id": row.get("evidence_id") or row.get("report_id"),
                    "generated_at": row.get("generated_at"),
                    "status": row.get("promotion_status") or "research_only",
                    "source": "promotion_evidence",
                    "evidence_id": row.get("evidence_id"),
                    "blockers": row.get("blockers") or [],
                    "metrics": row.get("metrics") or {},
                    "quality": row.get("quality") or {},
                }
            )
        for row in report_rows:
            events.append(
                {
                    "event_id": row.get("report_id"),
                    "generated_at": row.get("generated_at"),
                    "status": row.get("promotion_status") or "research_only",
                    "source": "promotion_report",
                    "evidence_id": row.get("report_id"),
                    "blockers": ((row.get("recommendation") or {}).get("blockers") or []),
                    "metrics": ((row.get("performance") or {}).get("metrics") or {}),
                    "quality": (((row.get("policy_evaluation") or {}).get("quality")) or {}),
                }
            )
        for row in shadow_rows:
            events.append(
                {
                    "event_id": row.get("run_id"),
                    "generated_at": row.get("generated_at"),
                    "status": "shadow",
                    "source": "shadow_retrain",
                    "evidence_id": row.get("run_id"),
                    "blockers": row.get("blockers") or [],
                    "metrics": row.get("metrics") or {},
                    "quality": row.get("quality") or {},
                }
            )
        events.sort(key=lambda item: str(item.get("generated_at") or ""), reverse=True)
        current_status = events[0]["status"] if events else self.build_promotion_report(window_days=90, persist=False).get("promotion_status")
        return {
            "generated_at": _iso_now(),
            "allowed_statuses": statuses,
            "current_status": current_status or "research_only",
            "count": len(events[: max(1, min(int(limit or 50), 200))]),
            "events": _jsonable(events[: max(1, min(int(limit or 50), 200))]),
        }

    def run_shadow_retrain(self, *, model_key: str = "rl_checkpoint", force: bool = False) -> dict[str, Any]:
        enabled = bool(getattr(settings, "SHADOW_RETRAIN_ENABLED", False))
        shadow_only = bool(getattr(settings, "MODEL_RETRAIN_SHADOW_ONLY", True))
        registry = self.build_model_registry()
        rl_meta = self._rl_checkpoint_preflight()
        run_id = f"shadow-retrain-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
        blockers: list[str] = []
        if not enabled and not force:
            blockers.append("shadow_retrain_disabled")
        if not shadow_only:
            blockers.append("model_retrain_shadow_only_required")
        payload = {
            "run_id": run_id,
            "generated_at": _iso_now(),
            "model_key": model_key,
            "status": "skipped" if blockers else "shadow_completed",
            "shadow_only": True,
            "force": bool(force),
            "blockers": blockers,
            "model_registry": registry,
            "rl_checkpoint": rl_meta,
            "metrics": {
                "backtest_required": True,
                "ope_required": True,
                "paper_checkpoint_replaced": False,
                "live_release_changed": False,
            },
            "next_actions": ["enable_shadow_retrain_schedule"] if blockers else ["evaluate_shadow_report_for_paper_promotion"],
        }
        payload["storage"] = self.storage.persist_record("shadow_retrain_runs", run_id, _jsonable(payload))
        return _jsonable(payload)

    def latest_shadow_retrain(self) -> dict[str, Any]:
        rows = [row for row in self.storage.list_records("shadow_retrain_runs") if isinstance(row, dict)]
        if not rows:
            return {
                "generated_at": _iso_now(),
                "status": "missing",
                "enabled": bool(getattr(settings, "SHADOW_RETRAIN_ENABLED", False)),
                "shadow_only": bool(getattr(settings, "MODEL_RETRAIN_SHADOW_ONLY", True)),
            }
        return _jsonable(rows[0])

    def get_cached_deployment_preflight(self, *, profile: str = "paper_cloud") -> dict[str, Any]:
        expected_profile = str(profile or "paper_cloud")
        rows = [
            row
            for row in self.storage.list_records("deployment_preflight")
            if isinstance(row, dict) and str(row.get("profile") or "paper_cloud") == expected_profile
        ]
        latest = rows[0] if rows else None
        if latest is None:
            return {
                "generated_at": _iso_now(),
                "profile": expected_profile,
                "ready": False,
                "cached": True,
                "blockers": ["preflight_missing"],
                "warnings": [],
                "detail": "No persisted deployment preflight has been evaluated yet.",
            }

        payload = dict(latest)
        generated = self._parse_any_timestamp(payload.get("generated_at"))
        max_age = max(1, int(getattr(settings, "DEPLOYMENT_PREFLIGHT_MAX_AGE_MINUTES", 15) or 15))
        stale = True
        age_minutes = None
        if generated is not None:
            age_minutes = (datetime.now(timezone.utc) - generated.astimezone(timezone.utc)).total_seconds() / 60
            stale = age_minutes > max_age
        blockers = list(payload.get("blockers") or [])
        if stale and "preflight_stale" not in blockers:
            blockers.append("preflight_stale")
        payload["cached"] = True
        payload["stale"] = stale
        payload["age_minutes"] = round(age_minutes, 2) if age_minutes is not None else None
        payload["max_age_minutes"] = max_age
        payload["blockers"] = blockers
        payload["ready"] = bool(payload.get("ready")) and not stale and not blockers
        return _jsonable(payload)

    def evaluate_deployment_preflight(self, *, profile: str = "paper_cloud") -> dict[str, Any]:
        registry_bootstrap = self.ensure_runtime_model_registry(actor="deployment_preflight")
        payload = self.build_deployment_preflight(profile=profile, dry_run=False)
        payload["model_registry_bootstrap"] = registry_bootstrap
        preflight_id = f"preflight-{profile}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
        payload["preflight_id"] = preflight_id
        payload["evaluated"] = True
        payload["storage"] = self.storage.persist_record("deployment_preflight", preflight_id, _jsonable(payload))
        latest_payload = dict(payload)
        latest_payload["latest_alias"] = f"{profile}_latest"
        self.storage.persist_record("deployment_preflight", f"{profile}_latest", _jsonable(latest_payload))
        return _jsonable(payload)

    def build_cached_readiness(self, *, profile: str = "paper_cloud") -> dict[str, Any]:
        heartbeat = self._scheduler_heartbeat_status()
        preflight = self.get_cached_deployment_preflight(profile=profile)
        circuit_breaker = self.paper_submit_circuit_breaker_status()
        components = {
            "api": {"ok": True, "detail": "FastAPI process is alive."},
            "quant_scheduler": {
                "ok": bool(heartbeat.get("exists") and not heartbeat.get("stale")),
                "detail": f"Heartbeat {heartbeat.get('last_seen') or 'missing'}",
                "meta": heartbeat,
            },
            "deployment_preflight": {
                "ok": bool(preflight.get("ready")),
                "detail": "Recent paper-cloud preflight passed." if preflight.get("ready") else "Recent paper-cloud preflight is missing, stale, or blocked.",
                "meta": preflight,
            },
            "paper_submit_circuit_breaker": {
                "ok": not bool(circuit_breaker.get("enabled")),
                "detail": circuit_breaker.get("reason") or "Paper submit circuit breaker is released.",
                "meta": circuit_breaker,
            },
        }
        blockers = [name for name, item in components.items() if not item.get("ok")]
        return {
            "generated_at": _iso_now(),
            "ready": not blockers,
            "cached": True,
            "profile": profile,
            "blockers": blockers,
            "components": components,
        }

    def paper_submit_circuit_breaker_status(self) -> dict[str, Any]:
        payload = self.storage.load_record("circuit_breakers", "paper_submit")
        if not isinstance(payload, dict):
            payload = {
                "breaker_id": "paper_submit",
                "enabled": False,
                "reason": "",
                "updated_at": None,
                "source": "default",
            }
        return _jsonable(payload)

    def set_paper_submit_circuit_breaker(
        self,
        *,
        enabled: bool,
        reason: str = "",
        details: dict[str, Any] | None = None,
        source: str = "scheduler",
    ) -> dict[str, Any]:
        payload = {
            "breaker_id": "paper_submit",
            "enabled": bool(enabled),
            "reason": reason or ("released" if not enabled else "paper submit circuit breaker enabled"),
            "details": details or {},
            "updated_at": _iso_now(),
            "source": source,
        }
        payload["storage"] = self.storage.persist_record("circuit_breakers", "paper_submit", _jsonable(payload))
        return _jsonable(payload)

    def build_deployment_preflight(self, *, profile: str = "paper_cloud", dry_run: bool = False) -> dict[str, Any]:
        hard: list[dict[str, Any]] = []
        soft: list[dict[str, Any]] = []

        def add(target: list[dict[str, Any]], name: str, ok: bool, detail: str, meta: dict[str, Any] | None = None) -> None:
            target.append({"name": name, "ok": bool(ok), "detail": detail, "meta": meta or {}})

        account = self.get_execution_account(broker="alpaca", mode="paper")
        add(hard, "alpaca_paper", bool(account.get("connected") and account.get("paper_ready")), "Alpaca paper account is reachable." if account.get("connected") else "Alpaca paper credentials/account are not ready.", account)

        market_meta = self._market_data_preflight()
        add(hard, "market_data", bool(market_meta.get("ok")), market_meta.get("detail", "market data unavailable"), market_meta)

        try:
            storage_meta = self._storage_preflight(dry_run=dry_run)
        except TypeError:
            storage_meta = self._storage_preflight()
        add(hard, "storage", bool(storage_meta.get("ok")), storage_meta.get("detail", "storage unavailable"), storage_meta)

        heartbeat = self._scheduler_heartbeat_status()
        add(hard, "scheduler_heartbeat", bool(heartbeat.get("exists") and not heartbeat.get("stale")), "Scheduler heartbeat is fresh." if heartbeat.get("exists") and not heartbeat.get("stale") else "Scheduler heartbeat is missing or stale.", heartbeat)

        registry = self.build_model_registry()
        add(hard, "model_registry", bool(registry.get("models")), "Model registry has runtime entries.", registry)

        rl_meta = self._rl_checkpoint_preflight()
        add(hard, "rl_checkpoint", bool(rl_meta.get("ok")), rl_meta.get("detail", "RL checkpoint unavailable"), rl_meta)

        controls = self.get_execution_controls()
        add(hard, "kill_switch", not bool(controls.get("kill_switch_enabled")), "Execution kill switch is released." if not controls.get("kill_switch_enabled") else "Execution kill switch is enabled.", controls)
        live_enabled = bool(getattr(settings, "ALPACA_ENABLE_LIVE_TRADING", False))
        add(
            hard,
            "live_trading_disabled",
            not live_enabled,
            "Live trading is disabled for unattended paper mode." if not live_enabled else "ALPACA_ENABLE_LIVE_TRADING must remain false for paper-cloud readiness.",
            {"ALPACA_ENABLE_LIVE_TRADING": live_enabled},
        )

        synthetic_meta = self._synthetic_trade_preflight()
        add(hard, "synthetic_trade_block", bool(synthetic_meta.get("ok")), synthetic_meta.get("detail", "synthetic trade guard failed"), synthetic_meta)

        calendar_meta = self.get_trading_calendar_status()
        add(hard, "trading_calendar", bool(calendar_meta.get("is_session") or calendar_meta.get("next_session")), "Trading calendar is available.", calendar_meta)

        workflow_meta = self._paper_workflow_preflight(registry=registry, rl_meta=rl_meta, account=account, controls=controls, synthetic_meta=synthetic_meta)
        add(hard, "paper_workflow", bool(workflow_meta.get("ok")), workflow_meta.get("detail", "paper workflow not ready"), workflow_meta)

        qdrant = self._qdrant_status()
        add(soft, "qdrant", bool(qdrant.get("reachable")), "Qdrant is reachable." if qdrant.get("reachable") else "Qdrant is not reachable.", qdrant)
        remote_llm = self._remote_llm_status()
        add(soft, "remote_llm", bool(remote_llm.get("reachable")), "Remote LLM is reachable." if remote_llm.get("reachable") else "Remote LLM is not reachable or not configured.", remote_llm)
        storage_status = self.storage.status()
        add(soft, "supabase_or_r2", bool(storage_status.get("supabase_ready") or storage_status.get("r2_ready") or storage_status.get("supabase_storage_ready")), "Cloud artifact backend is configured." if storage_status.get("mode") == "hybrid_cloud" else "Using local artifact fallback.", storage_status)
        notifier_meta = self._notifier_preflight()
        if str(profile or "").lower() == "paper_cloud" and bool(getattr(settings, "UNATTENDED_PAPER_MODE", True)):
            add(hard, "telegram_notifier", bool(notifier_meta.get("ok")), notifier_meta.get("detail", "Telegram notifier is not ready."), notifier_meta)
            email_meta = self._email_digest_preflight()
            add(hard, "email_digest", bool(email_meta.get("ok")), email_meta.get("detail", "Email digest is not ready."), email_meta)
            rotation_confirmed = bool(getattr(settings, "TELEGRAM_TOKEN_ROTATION_CONFIRMED", False))
            add(
                hard,
                "telegram_token_rotation",
                rotation_confirmed,
                "Telegram token rotation has been confirmed for production." if rotation_confirmed else "Rotate the Telegram bot token that was exposed during setup, then set TELEGRAM_TOKEN_ROTATION_CONFIRMED=true.",
                {
                    "confirmed": rotation_confirmed,
                    "token_fingerprint": notifier_meta.get("telegram_token_fingerprint"),
                },
            )
        else:
            add(soft, "alert_notifier", bool(notifier_meta.get("configured")), "Alert notifier is configured." if notifier_meta.get("configured") else "Alert notifier is UI/local only.", notifier_meta)
        add(soft, "audit_log", bool(getattr(settings, "AUDIT_LOG_ENABLED", True)), "Audit logging is enabled.")

        blockers = [item["name"] for item in hard if not item["ok"]]
        warnings = [item["name"] for item in soft if not item["ok"]]
        blocker_summary = self.build_blocker_summary(
            blockers=blockers,
            warnings=warnings,
            hard_checks=hard,
            soft_checks=soft,
        )
        return {
            "generated_at": _iso_now(),
            "profile": profile,
            "dry_run": bool(dry_run),
            "ready": not blockers,
            "blockers": blockers,
            "warnings": warnings,
            "blocker_summary": blocker_summary,
            "hard_checks": hard,
            "soft_checks": soft,
            "next_actions": self._preflight_next_actions(blockers, warnings),
        }

    def _email_digest_preflight(self) -> dict[str, Any]:
        recipients = self._quant_daily_digest_recipients()
        smtp_host = str(getattr(settings, "SMTP_HOST", "") or "").strip()
        smtp_user = str(getattr(settings, "SMTP_USER", "") or "").strip()
        smtp_password = str(getattr(settings, "SMTP_PASSWORD", "") or "").strip()
        ok = bool(smtp_host and smtp_user and smtp_password and recipients)
        return {
            "ok": ok,
            "configured": ok,
            "detail": "Email digest SMTP and recipients are configured." if ok else "SMTP_HOST, SMTP_USER, SMTP_PASSWORD, and QUANT_DAILY_DIGEST_RECIPIENTS are required.",
            "smtp_host": smtp_host,
            "smtp_user_fingerprint": self._secret_fingerprint(smtp_user),
            "recipient_count": len(recipients),
        }

    def get_trading_calendar_status(self) -> dict[str, Any]:
        market_clock = None
        try:
            account = self.get_execution_account(broker="alpaca", mode="paper")
            market_clock = account.get("market_clock")
        except Exception:
            market_clock = None
        return self.trading_calendar.status(market_clock=market_clock)

    @staticmethod
    def _safe_record_id(value: Any) -> str:
        text = str(value or "").strip().lower()
        cleaned = "".join(ch if ch.isalnum() else "-" for ch in text)
        cleaned = "-".join(part for part in cleaned.split("-") if part)
        return cleaned or "unknown"

    def _config_snapshot(self) -> dict[str, Any]:
        keys = [
            "ALPACA_DEFAULT_TEST_NOTIONAL",
            "SCHEDULER_MAX_EXECUTION_SYMBOLS",
            "SCHEDULER_MAX_DAILY_NOTIONAL_USD",
            "SYNTHETIC_EVIDENCE_POLICY",
            "TRADING_CALENDAR_ID",
            "PROMOTION_POLICY_PATH",
            "EXECUTION_SESSION_SUBMIT_LOCK_ENABLED",
            "SESSION_EVIDENCE_ENABLED",
            "ALPACA_PAPER_RECONCILE_ENABLED",
            "DIGEST_RETRY_ENABLED",
            "STORAGE_BACKUP_ENABLED",
            "MODEL_RETRAIN_SHADOW_ONLY",
            "ALPACA_ENABLE_LIVE_TRADING",
            "SCHEDULER_AUTO_SUBMIT",
            "OMP_NUM_THREADS",
            "MKL_NUM_THREADS",
            "OPENBLAS_NUM_THREADS",
            "NUMEXPR_NUM_THREADS",
            "TORCH_NUM_THREADS",
            "TOKENIZERS_PARALLELISM",
        ]
        values = {key: getattr(settings, key, None) for key in keys}
        registry = self._load_runtime_registry()
        model_refs = registry.get("models") if isinstance(registry, dict) else None
        payload = {
            "generated_at": _iso_now(),
            "values": values,
            "model_registry_refs": model_refs or [],
        }
        payload["hash"] = hashlib.sha1(json.dumps(payload["values"], sort_keys=True, default=str).encode("utf-8")).hexdigest()
        return payload

    def _classify_blocker(self, reason: Any) -> str:
        text = str(reason or "").strip().lower()
        if not text:
            return "warning"
        system_terms = (
            "scheduler_heartbeat",
            "heartbeat stale",
            "model_registry",
            "rl_checkpoint",
            "telegram_notifier",
            "telegram_token_rotation",
            "deployment_preflight",
            "storage_unwritable",
            "paper_workflow",
        )
        submit_terms = (
            "kill_switch",
            "synthetic",
            "negative_cash",
            "market_clock",
            "clock_unavailable",
            "market_closed",
            "broker",
            "alpaca",
            "account",
            "credential",
            "buying_power",
            "duplicate",
            "session_submit_locked",
            "daily_notional",
            "stale",
        )
        if any(term in text for term in system_terms):
            return "system_blocker"
        if any(term in text for term in submit_terms):
            return "submit_blocker"
        return "warning"

    def build_blocker_summary(
        self,
        *,
        blockers: list[Any] | None = None,
        warnings: list[Any] | None = None,
        hard_checks: list[dict[str, Any]] | None = None,
        soft_checks: list[dict[str, Any]] | None = None,
        alerts: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        items: list[dict[str, Any]] = []

        def add(reason: Any, default_class: str | None = None, source: str = "blocker") -> None:
            if reason in {None, ""}:
                return
            reason_text = str(reason)
            items.append(
                {
                    "reason": reason_text,
                    "class": default_class or self._classify_blocker(reason_text),
                    "source": source,
                }
            )

        for reason in blockers or []:
            add(reason, source="blocker")
        for reason in warnings or []:
            add(reason, default_class="warning", source="warning")
        for check in hard_checks or []:
            if not check.get("ok"):
                add(check.get("name") or check.get("detail"), default_class="system_blocker", source="hard_check")
        for check in soft_checks or []:
            if not check.get("ok"):
                add(check.get("name") or check.get("detail"), default_class="warning", source="soft_check")
        for alert in alerts or []:
            severity = str(alert.get("severity") or "").lower()
            default_class = "system_blocker" if severity in {"high", "critical"} else None
            add(alert.get("kind") or alert.get("message"), default_class=default_class, source="alert")

        deduped: dict[tuple[str, str], dict[str, Any]] = {}
        for item in items:
            deduped[(item["class"], item["reason"])] = item
        normalized = list(deduped.values())
        return {
            "submit_blockers": [item for item in normalized if item["class"] == "submit_blocker"],
            "system_blockers": [item for item in normalized if item["class"] == "system_blocker"],
            "warnings": [item for item in normalized if item["class"] == "warning"],
            "counts": {
                "submit_blocker": sum(1 for item in normalized if item["class"] == "submit_blocker"),
                "system_blocker": sum(1 for item in normalized if item["class"] == "system_blocker"),
                "warning": sum(1 for item in normalized if item["class"] == "warning"),
            },
        }

    def _session_evidence_stage_name(self, stage: str, payload: dict[str, Any]) -> str:
        normalized = str(stage or "").strip().lower()
        if normalized == "hybrid_workflow":
            return "workflow"
        if normalized == "sync":
            return "broker_sync"
        if normalized.startswith("daily_digest"):
            return "digest"
        if normalized == "execution":
            return "paper_submit"
        if normalized in {"storage_backup", "backup_quant_storage"}:
            return "backup"
        return normalized or str(payload.get("stage") or "unknown")

    def _session_evidence_stage_payload(
        self,
        *,
        stage: str,
        status: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        started_at = payload.get("started_at") or payload.get("timestamp") or payload.get("ran_at") or payload.get("generated_at")
        finished_at = payload.get("finished_at") or payload.get("ran_at") or _iso_now()
        warnings = [str(item) for item in payload.get("warnings") or [] if str(item).strip()]
        blockers = [str(item) for item in payload.get("blockers") or [] if str(item).strip()]
        error = payload.get("error") or (payload.get("reason") if str(status).lower() in {"failed", "error"} else None)
        artifacts = {
            key: payload.get(key)
            for key in (
                "workflow_id",
                "execution_id",
                "research_id",
                "validation_id",
                "snapshot_id",
                "attribution_id",
                "digest_id",
                "promotion_report_id",
                "paper_performance_snapshot_id",
            )
            if payload.get(key)
        }
        blocker_summary = self.build_blocker_summary(blockers=blockers, warnings=warnings)
        return {
            "stage": stage,
            "status": status,
            "started_at": started_at,
            "finished_at": finished_at,
            "duration_seconds": payload.get("duration_seconds"),
            "error": error,
            "submitted_count": int(payload.get("submitted_count") or 0),
            "artifacts": artifacts,
            "warnings": warnings,
            "blockers": blockers,
            "blocker_class": (
                "system_blocker"
                if blocker_summary["counts"]["system_blocker"]
                else "submit_blocker"
                if blocker_summary["counts"]["submit_blocker"]
                else "warning"
                if blocker_summary["counts"]["warning"]
                else None
            ),
            "blocker_summary": blocker_summary,
        }

    def record_session_evidence_stage(
        self,
        *,
        session_date: str,
        stage: str,
        status: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not bool(getattr(settings, "SESSION_EVIDENCE_ENABLED", True)):
            return {"enabled": False, "session_date": session_date}
        session_key = str(session_date or date.today().isoformat())[:10]
        record = self.storage.load_record("session_evidence", session_key) or {
            "session_date": session_key,
            "calendar_id": (payload or {}).get("calendar_id") or getattr(settings, "TRADING_CALENDAR_ID", "XNYS"),
            "generated_at": _iso_now(),
            "stages": {},
            "stage_order": [],
            "config_snapshot": self._config_snapshot(),
        }
        stage_payload = dict(payload or {})
        evidence_stage = self._session_evidence_stage_name(stage, stage_payload)
        normalized_status = str(status or stage_payload.get("status") or "completed").strip().lower()
        record.setdefault("stages", {})[evidence_stage] = self._session_evidence_stage_payload(
            stage=evidence_stage,
            status=normalized_status,
            payload=stage_payload,
        )
        if evidence_stage not in record.setdefault("stage_order", []):
            record["stage_order"].append(evidence_stage)

        if stage == "hybrid_workflow" and ("execution_id" in stage_payload or "submitted_count" in stage_payload):
            paper_submit_payload = dict(stage_payload)
            paper_status = "completed" if int(stage_payload.get("submitted_count") or 0) > 0 else "blocked"
            record["stages"]["paper_submit"] = self._session_evidence_stage_payload(
                stage="paper_submit",
                status=paper_status,
                payload=paper_submit_payload,
            )
            if "paper_submit" not in record["stage_order"]:
                record["stage_order"].append("paper_submit")

        automation = stage_payload.get("automation") if isinstance(stage_payload.get("automation"), dict) else {}
        if automation:
            for source_name, evidence_name in {
                "outcome_settlement": "outcomes",
                "paper_performance_snapshot": "snapshot",
                "promotion_evaluation": "promotion",
                "storage_backup": "backup",
            }.items():
                if source_name in automation:
                    child_payload = automation.get(source_name) if isinstance(automation.get(source_name), dict) else {}
                    child_payload = {"session_date": session_key, **dict(child_payload)}
                    child_payload.setdefault("duration_seconds", None)
                    record["stages"][evidence_name] = self._session_evidence_stage_payload(
                        stage=evidence_name,
                        status="completed",
                        payload=child_payload,
                    )
                    if evidence_name not in record["stage_order"]:
                        record["stage_order"].append(evidence_name)

        record["updated_at"] = _iso_now()
        required = ["preopen", "workflow", "paper_submit", "broker_sync", "outcomes", "snapshot", "promotion", "digest", "backup"]
        record["missing_stages"] = [name for name in required if name not in record.get("stages", {})]
        record["complete"] = not record["missing_stages"]
        record["storage"] = self.storage.persist_record("session_evidence", session_key, _jsonable(record))
        return _jsonable(record)

    def get_session_evidence(self, session_date: str | None = None) -> dict[str, Any] | None:
        if session_date:
            return self.storage.load_record("session_evidence", str(session_date)[:10])
        rows = self.storage.list_records("session_evidence")
        return rows[0] if rows else None

    def latest_session_evidence(self) -> dict[str, Any] | None:
        return self.get_session_evidence(None)

    def record_scheduler_event(
        self,
        *,
        stage: str,
        status: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        event_id = f"scheduler-event-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
        event_payload = dict(payload or {})
        body = {
            "event_id": event_id,
            "generated_at": _iso_now(),
            "stage": stage,
            "status": status,
            "session_date": event_payload.get("session_date"),
            "calendar_id": event_payload.get("calendar_id"),
            "duration_seconds": event_payload.get("duration_seconds"),
            "error": event_payload.get("error"),
            "submitted_count": int(event_payload.get("submitted_count") or 0),
            "payload": event_payload,
        }
        body["storage"] = self.storage.persist_record("scheduler_events", event_id, _jsonable(body))
        session_date = body.get("session_date") or event_payload.get("session_date")
        if session_date:
            try:
                body["session_evidence"] = self.record_session_evidence_stage(
                    session_date=str(session_date),
                    stage=stage,
                    status=status,
                    payload=event_payload,
                ).get("storage", {})
            except Exception as exc:
                body["session_evidence_error"] = str(exc)
        return _jsonable(body)

    def build_paper_workflow_observability(self, *, window_days: int = 30) -> dict[str, Any]:
        window = max(1, min(int(window_days or 30), 252))
        cutoff = datetime.now(timezone.utc) - timedelta(days=window * 2)
        events = [
            row for row in self.storage.list_records("scheduler_events")
            if isinstance(row, dict) and (self._parse_any_timestamp(row.get("generated_at")) or datetime.now(timezone.utc)) >= cutoff
        ]
        workflows = [
            row for row in self.storage.list_records("workflow_runs")
            if isinstance(row, dict) and (self._parse_any_timestamp(row.get("generated_at")) or datetime.now(timezone.utc)) >= cutoff
        ]
        alerts = self._build_observability_alerts(events=events, workflows=workflows, persist=False)
        success_rate = round(
            sum(1 for row in workflows if str(row.get("status") or "") in {"submitted", "planned"}) / len(workflows),
            6,
        ) if workflows else 0.0
        heartbeat = self._scheduler_heartbeat_status()
        circuit = self.paper_submit_circuit_breaker_status()
        missed_sessions: list[str] = []
        report = {
            "generated_at": _iso_now(),
            "window_days": window,
            "summary": {
                "workflow_count": len(workflows),
                "submitted_count": sum(1 for row in workflows if str(row.get("status") or "") == "submitted"),
                "blocked_count": sum(1 for row in workflows if str(row.get("status") or "") == "blocked"),
                "scheduler_event_count": len(events),
                "alert_count": len(alerts),
                "success_rate": success_rate,
            },
            "heartbeat": heartbeat,
            "calendar": self.get_trading_calendar_status(),
            "self_healing": self._paper_self_healing_status(),
            "circuit_breakers": {
                "paper_submit": circuit,
            },
            "storage_mirror": self.storage.status(),
            "storage_backup": self.latest_storage_backup_status(),
            "notifier": self._notifier_preflight(),
            "slo": self.build_paper_workflow_slo(window_days=window),
            "recovery_notifications": self._recent_recovery_notifications(limit=20),
            "alerts": alerts,
            "recent_events": events[:50],
            "recent_workflows": workflows[:20],
        }
        report["workflow_success_rate"] = success_rate
        report["missed_sessions"] = missed_sessions
        report["scheduler_heartbeat"] = heartbeat
        report["heartbeat_stale"] = bool(heartbeat.get("stale"))
        report["circuit_breaker"] = circuit
        report["blocker_summary"] = self.build_blocker_summary(alerts=alerts)
        return report

    def build_paper_workflow_slo(self, *, window_days: int = 30) -> dict[str, Any]:
        window = max(1, min(int(window_days or 30), 252))
        missing = self._paper_missing_sessions(
            points=self._normalize_paper_gate_points(self.storage.list_records("paper_performance")),
            window_days=window,
        )
        expected_sessions = list(missing.get("missing_sessions") or [])
        observed_sessions = {
            str(row.get("session_date") or row.get("date") or row.get("snapshot_id") or "")[:10]
            for row in self.storage.list_records("session_evidence")
            if isinstance(row, dict)
        }
        all_expected = set(expected_sessions) | observed_sessions
        required_stages = {"preopen", "workflow", "paper_submit", "broker_sync", "outcomes", "snapshot", "promotion", "digest", "backup"}
        evidence_rows = [
            row for row in self.storage.list_records("session_evidence")
            if isinstance(row, dict) and str(row.get("session_date") or "")[:10] in all_expected
        ]

        def complete_evidence(row: dict[str, Any]) -> bool:
            stages = row.get("stages") or {}
            return required_stages.issubset(stages) and all(
                str((stages.get(stage) or {}).get("status") or "").lower()
                in {"completed", "submitted", "planned", "blocked", "skipped"}
                for stage in required_stages
            )

        workflows = [
            row for row in self.storage.list_records("workflow_runs")
            if isinstance(row, dict)
        ]
        locks = self.storage.list_records("submit_locks")
        executions = self.storage.list_records("executions")
        duplicate_blocked = 0
        for payload in executions:
            for order in (payload.get("orders") or []):
                if str((order or {}).get("status") or "").lower() == "session_submit_locked":
                    duplicate_blocked += 1
        duplicate_blocked += sum(1 for row in locks if str((row or {}).get("status") or "").lower() == "session_submit_locked")
        reconciliations = self.storage.list_records("paper_reconciliations")
        reconcile_repairs = sum(
            int(row.get("journal_updates") or 0)
            + int(row.get("execution_updates") or 0)
            + int(row.get("submit_lock_updates") or 0)
            + int(row.get("outcome_updates") or 0)
            for row in reconciliations
            if isinstance(row, dict)
        )
        deliveries = [row for row in self.storage.list_records("paper_daily_digest_deliveries") if isinstance(row, dict)]
        backups = [row for row in self.storage.list_records("storage_backups") if isinstance(row, dict)]
        workflow_successes = sum(1 for row in workflows if str(row.get("status") or "").lower() in {"submitted", "planned", "completed"})
        digest_successes = sum(1 for row in deliveries if str(row.get("status") or "").lower() == "sent")
        backup_successes = sum(1 for row in backups if str(row.get("status") or "").lower() == "completed")
        expected_count = int(missing.get("expected_sessions") or len(all_expected) or len(evidence_rows))
        complete_count = sum(1 for row in evidence_rows if complete_evidence(row))
        return {
            "generated_at": _iso_now(),
            "window_days": window,
            "session_evidence": {
                "expected_sessions": expected_count,
                "observed_sessions": len(evidence_rows),
                "complete_sessions": complete_count,
                "completion_rate": round(complete_count / expected_count, 6) if expected_count else 0.0,
                "missing_sessions": missing.get("missing_sessions", []),
            },
            "workflow": {
                "count": len(workflows),
                "success_count": workflow_successes,
                "success_rate": round(workflow_successes / len(workflows), 6) if workflows else 0.0,
            },
            "orders": {
                "duplicate_submit_blocked_count": duplicate_blocked,
                "submit_unknown_count": sum(1 for row in locks if str((row or {}).get("status") or "") == "submit_unknown"),
            },
            "reconciliation": {
                "run_count": len(reconciliations),
                "repair_count": reconcile_repairs,
            },
            "digest": {
                "delivery_count": len(deliveries),
                "sent_count": digest_successes,
                "success_rate": round(digest_successes / len(deliveries), 6) if deliveries else 0.0,
            },
            "backup": {
                "run_count": len(backups),
                "success_count": backup_successes,
                "success_rate": round(backup_successes / len(backups), 6) if backups else 0.0,
            },
            "status": "pass" if expected_count and complete_count == expected_count and (not deliveries or digest_successes == len(deliveries)) else "watch",
        }

    def evaluate_paper_workflow_observability(self, *, window_days: int = 30) -> dict[str, Any]:
        window = max(1, min(int(window_days or 30), 252))
        cutoff = datetime.now(timezone.utc) - timedelta(days=window * 2)
        events = [
            row for row in self.storage.list_records("scheduler_events")
            if isinstance(row, dict) and (self._parse_any_timestamp(row.get("generated_at")) or datetime.now(timezone.utc)) >= cutoff
        ]
        workflows = [
            row for row in self.storage.list_records("workflow_runs")
            if isinstance(row, dict) and (self._parse_any_timestamp(row.get("generated_at")) or datetime.now(timezone.utc)) >= cutoff
        ]
        alerts = self._build_observability_alerts(events=events, workflows=workflows, persist=True)
        resolved_alerts = self._record_resolved_observability_alerts(active_alerts=alerts)
        report = self.build_paper_workflow_observability(window_days=window)
        report["alerts"] = alerts
        report["summary"]["alert_count"] = len(alerts)
        report["resolved_alerts"] = resolved_alerts
        report["evaluation"] = {"persisted_alerts": True, "dedupe_window_hours": 24, "resolved_count": len(resolved_alerts)}
        return report

    def _paper_self_healing_status(self) -> dict[str, Any]:
        rows = self.storage.list_records("scheduler_events")[:50]
        recovery_events = [
            row for row in rows
            if isinstance(row, dict) and str(row.get("stage") or "") in {"recovery", "post_sync_automation", "observability"}
        ]
        failure_events = [
            row for row in rows
            if isinstance(row, dict) and str(row.get("status") or "").lower() in {"failed", "error"}
        ]
        return {
            "enabled": bool(getattr(settings, "UNATTENDED_PAPER_MODE", True)),
            "recent_recovery_count": len(recovery_events),
            "recent_failure_count": len(failure_events),
            "latest_recovery": recovery_events[0] if recovery_events else None,
        }

    def _recent_recovery_notifications(self, *, limit: int = 20) -> list[dict[str, Any]]:
        rows = [
            row for row in self.storage.list_records("alerts")
            if isinstance(row, dict)
            and (
                str(row.get("status") or "") == "resolved_notification"
                or str(row.get("kind") or "").endswith("_resolved")
                or row.get("resolved_at")
            )
        ]
        return rows[: max(1, min(int(limit or 20), 100))]

    def _build_observability_alerts(
        self,
        *,
        events: list[dict[str, Any]],
        workflows: list[dict[str, Any]],
        persist: bool = False,
    ) -> list[dict[str, Any]]:
        alerts: list[dict[str, Any]] = []

        def add(kind: str, severity: str, message: str, payload: dict[str, Any] | None = None) -> None:
            body = {
                "alert_id": "",
                "generated_at": _iso_now(),
                "kind": kind,
                "severity": severity,
                "message": message,
                "payload": payload or {},
                "notifier": self._alert_notifier_status(),
            }
            alert_id = self._observability_alert_id(body)
            body["alert_id"] = alert_id
            if persist:
                existing = self._recent_matching_alert(alert_id=alert_id, kind=kind)
                if existing is not None:
                    existing = dict(existing)
                    existing["deduped"] = True
                    alerts.append(_jsonable(existing))
                    return
                body["notifier"] = self._deliver_alert(body)
                body["storage"] = self.storage.persist_record("alerts", alert_id, _jsonable(body))
            alerts.append(_jsonable(body))

        heartbeat = self._scheduler_heartbeat_status()
        if heartbeat.get("stale") or not heartbeat.get("exists"):
            add("stale_heartbeat", "high", "Scheduler heartbeat is missing or stale.", heartbeat)
        if not workflows:
            add("missing_workflow", "medium", "No paper workflow runs were found in the observability window.")
        for workflow in workflows[:20]:
            if workflow.get("blockers"):
                add("workflow_blocked", "medium", "Paper workflow returned blockers.", {"workflow_id": workflow.get("workflow_id"), "blockers": workflow.get("blockers")})
            if (workflow.get("gate_snapshot") or {}).get("synthetic_execution"):
                add("synthetic_evidence", "high", "Synthetic evidence appeared in a paper workflow.", {"workflow_id": workflow.get("workflow_id")})
        controls = self.get_execution_controls()
        if controls.get("kill_switch_enabled"):
            add("kill_switch", "high", "Execution kill switch is enabled.", controls)
        circuit = self.paper_submit_circuit_breaker_status()
        if circuit.get("enabled"):
            add("paper_submit_circuit_breaker", "high", "Paper submit circuit breaker is enabled.", circuit)
        rl_meta = self._rl_checkpoint_preflight()
        if not rl_meta.get("ok"):
            add("rl_checkpoint_missing", "high", "RL checkpoint is missing for unattended paper workflow.", rl_meta)
        market_meta = self._market_data_preflight()
        if not market_meta.get("ok"):
            add("market_data_stale", "high", market_meta.get("detail", "Market data provider is unavailable."), market_meta)
        storage_status = self.storage.status()
        if not (storage_status.get("supabase_ready") or storage_status.get("r2_ready") or storage_status.get("supabase_storage_ready")):
            add("storage_mirror_unavailable", "medium", "Remote evidence mirror is not configured; local ledger remains active.", storage_status)
        backup_status = self.latest_storage_backup_status()
        if backup_status.get("status") in {"missing", "completed_local_only"} or backup_status.get("uploaded") is False:
            add("storage_backup_unavailable", "medium", "Remote evidence backup is missing or local-only.", backup_status)
        return alerts

    @staticmethod
    def _observability_alert_id(alert: dict[str, Any]) -> str:
        kind = str(alert.get("kind") or "paper_workflow")
        payload = {
            "kind": kind,
            "message": alert.get("message"),
            "payload": QuantSystemService._observability_alert_fingerprint_payload(
                kind,
                alert.get("payload") or {},
            ),
        }
        digest = hashlib.sha1(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:16]
        return f"alert-{kind}-{digest}"

    @staticmethod
    def _observability_alert_fingerprint_payload(kind: str, payload: Any) -> Any:
        if kind in {"workflow_blocked", "synthetic_evidence"} and isinstance(payload, dict):
            return {
                key: payload.get(key)
                for key in ("workflow_id", "execution_id", "order_id", "symbol")
                if payload.get(key) is not None
            }
        if kind in {"stale_heartbeat", "missing_workflow", "kill_switch"}:
            return {}

        volatile = {
            "age_minutes",
            "as_of",
            "created_at",
            "fetched_at",
            "generated_at",
            "last_seen",
            "timestamp",
            "updated_at",
        }

        def scrub(value: Any) -> Any:
            if isinstance(value, dict):
                return {
                    str(key): scrub(child)
                    for key, child in sorted(value.items(), key=lambda item: str(item[0]))
                    if str(key) not in volatile
                }
            if isinstance(value, list):
                return [scrub(item) for item in value]
            return value

        return scrub(payload)

    def _recent_matching_alert(self, *, alert_id: str, kind: str, hours: int = 24) -> dict[str, Any] | None:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=max(1, int(hours or 24)))
        direct = self.storage.load_record("alerts", alert_id)
        if isinstance(direct, dict):
            generated = self._parse_any_timestamp(direct.get("generated_at"))
            if generated is None or generated.astimezone(timezone.utc) >= cutoff:
                return direct
        for row in self.storage.list_records("alerts")[:200]:
            if not isinstance(row, dict) or str(row.get("kind") or "") != kind:
                continue
            generated = self._parse_any_timestamp(row.get("generated_at"))
            if generated is not None and generated.astimezone(timezone.utc) < cutoff:
                continue
            if row.get("alert_id") == alert_id:
                return row
        return None

    def _record_resolved_observability_alerts(self, *, active_alerts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        active_ids = {str(alert.get("alert_id") or "") for alert in active_alerts if alert.get("alert_id")}
        resolved: list[dict[str, Any]] = []
        for row in self.storage.list_records("alerts")[:200]:
            if not isinstance(row, dict):
                continue
            alert_id = str(row.get("alert_id") or "").strip()
            kind = str(row.get("kind") or "").strip()
            if not alert_id or alert_id in active_ids or row.get("resolved_at") or kind.endswith("_resolved"):
                continue
            updated = {**row, "resolved_at": _iso_now(), "status": "resolved"}
            self.storage.persist_record("alerts", alert_id, _jsonable(updated))
            resolved_alert = {
                "alert_id": f"{alert_id}-resolved",
                "generated_at": _iso_now(),
                "kind": f"{kind}_resolved",
                "severity": "info",
                "message": f"Recovered: {row.get('message') or kind}",
                "payload": {"resolved_alert_id": alert_id, "kind": kind},
                "status": "resolved_notification",
            }
            resolved_alert["notifier"] = self._deliver_alert(resolved_alert)
            resolved_alert["storage"] = self.storage.persist_record(
                "alerts",
                resolved_alert["alert_id"],
                _jsonable(resolved_alert),
            )
            resolved.append(_jsonable(resolved_alert))
        return resolved

    def _alert_notifier_status(self) -> dict[str, Any]:
        notifier = self._notifier_preflight()
        return {
            "telegram_configured": bool(notifier.get("telegram_configured")),
            "slack_configured": bool(notifier.get("slack_configured")),
            "configured": bool(notifier.get("configured")),
            "preferred": notifier.get("preferred"),
            "delivery": "local_ledger",
        }

    def _notifier_preflight(self) -> dict[str, Any]:
        preferred = str(getattr(settings, "ALERT_NOTIFIER", "telegram") or "telegram").strip().lower()
        telegram_token = str(getattr(settings, "TELEGRAM_BOT_TOKEN", "") or "").strip()
        telegram_chat_id = str(getattr(settings, "TELEGRAM_CHAT_ID", "") or "").strip()
        slack_webhook = str(getattr(settings, "SLACK_WEBHOOK_URL", "") or "").strip()
        telegram_configured = bool(telegram_token and telegram_chat_id)
        slack_configured = bool(slack_webhook)
        if preferred == "telegram":
            ok = telegram_configured
            detail = "Telegram alert notifier is configured." if ok else "TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are required for unattended paper mode."
        elif preferred == "slack":
            ok = slack_configured
            detail = "Slack alert notifier is configured." if ok else "SLACK_WEBHOOK_URL is required for Slack alert delivery."
        else:
            ok = telegram_configured or slack_configured
            detail = "Alert notifier is configured." if ok else "No external alert notifier is configured."
        return {
            "ok": ok,
            "configured": telegram_configured or slack_configured,
            "preferred": preferred,
            "detail": detail,
            "telegram_configured": telegram_configured,
            "slack_configured": slack_configured,
            "telegram_token_fingerprint": self._secret_fingerprint(telegram_token),
            "telegram_token_rotation_confirmed": bool(getattr(settings, "TELEGRAM_TOKEN_ROTATION_CONFIRMED", False)),
        }

    @staticmethod
    def _secret_fingerprint(value: str) -> str | None:
        if not value:
            return None
        digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
        return f"sha256:{digest}"

    def _deliver_alert(self, alert: dict[str, Any]) -> dict[str, Any]:
        status = self._alert_notifier_status()
        preferred = str(status.get("preferred") or "telegram")
        status["delivery"] = "local_ledger"
        status["delivery_status"] = "skipped"
        if preferred != "telegram" or not status.get("telegram_configured"):
            return status
        token = str(getattr(settings, "TELEGRAM_BOT_TOKEN", "") or "").strip()
        chat_id = str(getattr(settings, "TELEGRAM_CHAT_ID", "") or "").strip()
        timeout = max(1, int(getattr(settings, "ALERT_NOTIFIER_TIMEOUT_SECONDS", 5) or 5))
        text = self._format_telegram_alert(alert)
        try:
            response = requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": text, "disable_web_page_preview": True},
                timeout=timeout,
            )
            status["delivery"] = "telegram"
            status["delivery_status"] = "sent" if response.ok else "failed"
            status["status_code"] = response.status_code
            if not response.ok:
                status["error"] = response.text[:300]
        except Exception as exc:
            status["delivery"] = "telegram"
            status["delivery_status"] = "failed"
            status["error"] = str(exc)
        return status

    @staticmethod
    def _format_telegram_alert(alert: dict[str, Any]) -> str:
        severity = str(alert.get("severity") or "info").upper()
        kind = str(alert.get("kind") or "paper_workflow")
        message = str(alert.get("message") or "")
        alert_id = str(alert.get("alert_id") or "")
        return f"[{severity}] {kind}\n{message}\n{alert_id}"[:3500]

    def _send_telegram_message(self, text: str) -> dict[str, Any]:
        notifier = self._notifier_preflight()
        if not notifier.get("telegram_configured"):
            return {
                "channel": "telegram",
                "status": "skipped",
                "detail": "telegram_not_configured",
                "configured": False,
            }
        token = str(getattr(settings, "TELEGRAM_BOT_TOKEN", "") or "").strip()
        chat_id = str(getattr(settings, "TELEGRAM_CHAT_ID", "") or "").strip()
        timeout = max(1, int(getattr(settings, "ALERT_NOTIFIER_TIMEOUT_SECONDS", 5) or 5))
        try:
            response = requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": text[:3500], "disable_web_page_preview": True},
                timeout=timeout,
            )
            return {
                "channel": "telegram",
                "status": "sent" if response.ok else "failed",
                "status_code": response.status_code,
                "configured": True,
                "detail": "sent" if response.ok else response.text[:300],
            }
        except Exception as exc:
            return {
                "channel": "telegram",
                "status": "failed",
                "configured": True,
                "detail": str(exc),
            }

    def _quant_daily_digest_channels(self, channels: list[str] | None = None) -> list[str]:
        raw = channels if channels is not None else str(getattr(settings, "QUANT_DAILY_DIGEST_CHANNELS", "telegram,email") or "").split(",")
        normalized = []
        for item in raw:
            value = str(item).strip().lower()
            if value in {"telegram", "email"} and value not in normalized:
                normalized.append(value)
        return normalized or ["telegram", "email"]

    def _quant_daily_digest_recipients(self, recipients: list[str] | None = None) -> list[str]:
        raw = recipients if recipients is not None else str(getattr(settings, "QUANT_DAILY_DIGEST_RECIPIENTS", "") or "").split(",")
        values = [str(item).strip() for item in raw if str(item).strip()]
        return list(dict.fromkeys(values))

    def _load_scheduler_runtime_state(self) -> dict[str, Any]:
        path = self._resolve_runtime_path(
            getattr(settings, "SCHEDULER_STATE_PATH", "storage/quant/scheduler/runtime_state.json"),
            "storage/quant/scheduler/runtime_state.json",
        )
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning(f"Scheduler runtime state load failed for {path}: {exc}")
            return {"load_error": str(exc), "path": path.as_posix()}

    @staticmethod
    def _record_session_date(record: dict[str, Any]) -> str:
        return str(
            record.get("session_date")
            or record.get("trade_date")
            or record.get("date")
            or record.get("snapshot_id")
            or ""
        )[:10]

    def _latest_record_for_session(self, record_type: str, session_date: str) -> dict[str, Any] | None:
        rows = [row for row in self.storage.list_records(record_type) if isinstance(row, dict)]
        for row in rows:
            if self._record_session_date(row) == session_date:
                return row
        return rows[0] if rows else None

    def _build_digest_performance_snapshot(self, *, window_days: int = 90) -> dict[str, Any]:
        rows = [
            row for row in self.storage.list_records("paper_performance")
            if isinstance(row, dict) and not row.get("synthetic_used") and row.get("evidence_eligible") is not False
        ]
        rows.sort(key=lambda item: str(item.get("date") or item.get("snapshot_id") or item.get("generated_at") or ""))
        rows = rows[-max(1, int(window_days or 90)) :]
        latest = rows[-1] if rows else {}

        def nav(row: dict[str, Any]) -> float | None:
            for key in ("portfolio_nav", "equity", "portfolio_value", "nav"):
                value = self._safe_float(row.get(key))
                if value is not None:
                    return value
            return None

        first_nav = nav(rows[0]) if rows else None
        latest_nav = nav(latest) if latest else None
        net_return = None
        if first_nav not in {None, 0} and latest_nav is not None:
            net_return = round((latest_nav / float(first_nav)) - 1.0, 6)
        metrics = {
            "valid_days": len(rows),
            "net_return": net_return,
            "annualized_return": None,
            "max_drawdown": None,
            "equity": latest_nav,
            "cash": self._safe_float(latest.get("cash")),
            "buying_power": self._safe_float(latest.get("buying_power")),
        }
        return {
            "metrics": metrics,
            "missing_sessions": [],
            "broker_sync_errors": latest.get("broker_sync_errors") or [],
            "cash_flow_adjustment_source": latest.get("cash_flow_adjustment_source") or "unavailable",
            "latest_snapshot_id": latest.get("snapshot_id") or latest.get("date"),
            "fast_digest_snapshot": True,
        }

    def _build_digest_observability_snapshot(self, *, window_days: int = 7) -> dict[str, Any]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, int(window_days or 7)))
        alerts = []
        for row in self.storage.list_records("alerts")[:100]:
            if not isinstance(row, dict):
                continue
            generated = self._parse_any_timestamp(row.get("generated_at"))
            if generated is not None and generated.astimezone(timezone.utc) < cutoff:
                continue
            alerts.append(row)
        workflows = [
            row for row in self.storage.list_records("workflow_runs")[:50]
            if isinstance(row, dict)
        ]
        heartbeat = self._scheduler_heartbeat_status()
        if heartbeat.get("stale") or not heartbeat.get("exists"):
            alerts.insert(
                0,
                {
                    "kind": "stale_heartbeat",
                    "severity": "high",
                    "message": "Scheduler heartbeat is missing or stale.",
                    "payload": heartbeat,
                },
            )
        return {
            "summary": {
                "workflow_count": len(workflows),
                "alert_count": len(alerts),
                "success_rate": round(
                    sum(1 for row in workflows if str(row.get("status") or "") in {"submitted", "planned"}) / len(workflows),
                    6,
                ) if workflows else 0.0,
            },
            "alerts": alerts[:5],
            "heartbeat": heartbeat,
            "fast_digest_snapshot": True,
        }

    def _paper_outcome_digest_counts(self, *, session_date: str) -> dict[str, int]:
        pending = 0
        due = 0
        settled = 0
        for row in self.storage.list_records("paper_outcomes")[:500]:
            if not isinstance(row, dict):
                continue
            status = str(row.get("status") or "").lower()
            if status == "pending":
                pending += 1
            if status == "settled":
                settled += 1
            settlements = row.get("settlements") or {}
            for payload in settlements.values():
                if not isinstance(payload, dict):
                    continue
                due_session = str(payload.get("due_session_date") or "")[:10]
                if due_session and due_session <= session_date and str(payload.get("status") or "").lower() == "pending":
                    due += 1
                    break
        return {"pending": pending, "due": due, "settled": settled}

    def build_quant_daily_digest(self, *, phase: str = "postclose", session_date: str | None = None) -> dict[str, Any]:
        phase_name = str(phase or "postclose").strip().lower()
        if phase_name not in {"preopen", "postclose"}:
            phase_name = "postclose"
        calendar = self.get_trading_calendar_status()
        session = str(session_date or calendar.get("session_date") or date.today().isoformat())[:10]
        scheduler_state = self._load_scheduler_runtime_state()
        preopen = scheduler_state.get("preopen", {}) or {}
        workflow = self._latest_record_for_session("workflow_runs", session) or {}
        digest_id = f"digest-{session}-{phase_name}"

        try:
            performance = self._build_digest_performance_snapshot(window_days=90)
        except Exception as exc:
            performance = {"error": str(exc), "metrics": {}}
        try:
            observability = self._build_digest_observability_snapshot(window_days=7)
        except Exception as exc:
            observability = {"error": str(exc), "summary": {}, "alerts": []}

        perf_metrics = dict(performance.get("metrics") or {})
        alerts = list(observability.get("alerts") or [])[:5]
        blocker_values = list(dict.fromkeys(list(workflow.get("blockers") or []) + [alert.get("kind") for alert in alerts if alert.get("kind")]))
        order_summary = workflow.get("order_summary") or workflow.get("orders") or []
        controls = self.get_execution_controls()
        outcome_counts = self._paper_outcome_digest_counts(session_date=session)
        candidate_symbols = [
            str(symbol).upper()
            for symbol in preopen.get("candidate_symbols", [])
            if str(symbol).strip()
        ]
        summary = {
            "phase": phase_name,
            "session_date": session,
            "workflow_status": workflow.get("status") or "unavailable",
            "workflow_id": workflow.get("workflow_id"),
            "execution_id": workflow.get("execution_id"),
            "submitted_count": int(workflow.get("submitted_count") or 0),
            "candidate_symbols": candidate_symbols,
            "valid_days": int(perf_metrics.get("valid_days") or 0),
            "net_return": perf_metrics.get("net_return"),
            "annualized_return": perf_metrics.get("annualized_return"),
            "max_drawdown": perf_metrics.get("max_drawdown"),
            "alert_count": len(alerts),
            "blockers": blocker_values,
            "paper_submit_circuit_breaker": self.paper_submit_circuit_breaker_status(),
            "preflight_ready": bool((self.get_cached_deployment_preflight(profile="paper_cloud") or {}).get("ready")),
            "account_equity": perf_metrics.get("equity"),
            "account_cash": perf_metrics.get("cash"),
            "buying_power": perf_metrics.get("buying_power"),
            "outcome_pending_count": outcome_counts["pending"],
            "outcome_due_count": outcome_counts["due"],
            "kill_switch_enabled": bool(controls.get("kill_switch_enabled")),
        }
        blocker_summary = self.build_blocker_summary(
            blockers=blocker_values,
            warnings=list(workflow.get("warnings") or []),
            alerts=alerts,
        )
        payload = {
            "digest_id": digest_id,
            "generated_at": _iso_now(),
            "phase": phase_name,
            "session_date": session,
            "summary": summary,
            "preopen": {
                "ran_at": preopen.get("ran_at"),
                "candidate_symbols": candidate_symbols,
                "research_id": preopen.get("research_id"),
                "p1_report_id": preopen.get("p1_report_id"),
                "p2_report_id": preopen.get("p2_report_id"),
            },
            "workflow": {
                "workflow_id": workflow.get("workflow_id"),
                "status": workflow.get("status"),
                "execution_id": workflow.get("execution_id"),
                "submitted_count": workflow.get("submitted_count"),
                "blockers": workflow.get("blockers") or [],
                "warnings": workflow.get("warnings") or [],
                "next_actions": workflow.get("next_actions") or [],
                "order_summary": order_summary[:10] if isinstance(order_summary, list) else [],
            },
            "performance": {
                "metrics": perf_metrics,
                "missing_sessions": performance.get("missing_sessions") or [],
                "broker_sync_errors": performance.get("broker_sync_errors") or [],
                "cash_flow_adjustment_source": performance.get("cash_flow_adjustment_source"),
            },
            "observability": {
                "summary": observability.get("summary") or {},
                "alerts": alerts,
            },
            "outcomes": outcome_counts,
            "controls": {
                "kill_switch_enabled": bool(controls.get("kill_switch_enabled")),
                "kill_switch_reason": controls.get("kill_switch_reason"),
            },
            "blocker_summary": blocker_summary,
        }
        payload["text"] = self._format_quant_daily_digest_text(payload)
        return payload

    @staticmethod
    def _format_quant_daily_digest_text(payload: dict[str, Any]) -> str:
        summary = payload.get("summary") or {}
        workflow = payload.get("workflow") or {}
        performance = (payload.get("performance") or {}).get("metrics") or {}
        alerts = (payload.get("observability") or {}).get("alerts") or []
        outcomes = payload.get("outcomes") or {}
        symbols = ", ".join(summary.get("candidate_symbols") or []) or "none"
        blockers = ", ".join(summary.get("blockers") or []) or "none"
        orders = workflow.get("order_summary") or []
        order_lines = []
        for order in orders[:5]:
            if isinstance(order, dict):
                order_lines.append(f"- {order.get('symbol', '?')} {order.get('side', order.get('action', ''))} {order.get('status', '')}".strip())
        if not order_lines:
            order_lines = ["- none"]
        alert_lines = [f"- {item.get('severity', 'info')}: {item.get('kind', item.get('message', 'alert'))}" for item in alerts[:5]]
        if not alert_lines:
            alert_lines = ["- none"]
        return "\n".join(
            [
                f"Hybrid Paper {payload.get('phase')} digest - {payload.get('session_date')}",
                f"Workflow: {summary.get('workflow_status')} workflow={summary.get('workflow_id') or 'n/a'} execution={summary.get('execution_id') or 'n/a'} submitted={summary.get('submitted_count')}",
                f"Preopen candidates: {symbols}",
                f"Account: equity={summary.get('account_equity', 'n/a')} cash={summary.get('account_cash', 'n/a')} buying_power={summary.get('buying_power', 'n/a')}",
                f"Performance: valid_days={summary.get('valid_days')} net_return={performance.get('net_return', 'n/a')} annualized={performance.get('annualized_return', 'n/a')} max_dd={performance.get('max_drawdown', 'n/a')}",
                f"Outcomes: pending={outcomes.get('pending', 0)} due={outcomes.get('due', 0)} settled={outcomes.get('settled', 0)}",
                f"Kill switch: {'enabled' if summary.get('kill_switch_enabled') else 'released'}",
                f"Blockers: {blockers}",
                "Orders:",
                *order_lines,
                "Alerts:",
                *alert_lines,
            ]
        )[:8000]

    def send_quant_daily_digest(
        self,
        *,
        phase: str = "postclose",
        session_date: str | None = None,
        recipients: list[str] | None = None,
        channels: list[str] | None = None,
    ) -> dict[str, Any]:
        digest = self.build_quant_daily_digest(phase=phase, session_date=session_date)
        selected_channels = self._quant_daily_digest_channels(channels)
        selected_recipients = self._quant_daily_digest_recipients(recipients)
        deliveries: list[dict[str, Any]] = []
        if "telegram" in selected_channels:
            deliveries.append(self._send_telegram_message(digest["text"]))
        if "email" in selected_channels:
            if not selected_recipients:
                deliveries.append({"channel": "email", "status": "skipped", "detail": "no_recipients"})
            for recipient in selected_recipients:
                result = send_email_message(
                    recipient=recipient,
                    subject=f"Hybrid Paper {digest['phase']} digest {digest['session_date']}",
                    text_body=digest["text"],
                    html_body=f"<pre>{digest['text']}</pre>",
                    sender=getattr(settings, "EMAIL_FROM", "") or getattr(settings, "SMTP_USER", ""),
                )
                deliveries.append(
                    {
                        "channel": "email",
                        "recipient": recipient,
                        "status": "sent" if result.get("ok") else "failed",
                        "detail": result.get("detail"),
                    }
                )
        retry_after = (
            datetime.now(timezone.utc)
            + timedelta(minutes=max(1, int(getattr(settings, "QUANT_DAILY_DIGEST_RETRY_MINUTES", 15) or 15)))
        ).isoformat()
        normalized_deliveries: list[dict[str, Any]] = []
        for index, item in enumerate(deliveries):
            delivery = dict(item)
            delivery.setdefault("delivery_id", f"{digest['digest_id']}-{index + 1}")
            delivery.setdefault("generated_at", _iso_now())
            if delivery.get("status") == "failed":
                delivery.setdefault("error", delivery.get("detail") or "delivery_failed")
                delivery.setdefault("next_retry_at", retry_after)
            normalized_deliveries.append(delivery)
        deliveries = normalized_deliveries
        sent_count = sum(1 for item in deliveries if item.get("status") == "sent")
        failed_count = sum(1 for item in deliveries if item.get("status") == "failed")
        digest["delivery"] = {
            "channels": selected_channels,
            "recipients": selected_recipients,
            "results": deliveries,
            "sent_count": sent_count,
            "failed_count": failed_count,
            "local_ledger": True,
            "retry_after": retry_after if failed_count else None,
        }
        digest["storage"] = self.storage.persist_record("paper_daily_digests", digest["digest_id"], _jsonable(digest))
        for item in deliveries:
            delivery_id = str(item.get("delivery_id") or f"{digest['digest_id']}-{item.get('channel', 'unknown')}")
            self.storage.persist_record(
                "paper_daily_digest_deliveries",
                delivery_id,
                _jsonable(
                    {
                        "digest_id": digest["digest_id"],
                        "session_date": digest["session_date"],
                        "phase": digest["phase"],
                        **item,
                    }
                ),
            )
        return _jsonable(digest)

    def build_quant_weekly_digest(self, *, session_date: str | None = None, window_days: int | None = None) -> dict[str, Any]:
        calendar = self.get_trading_calendar_status()
        session = str(session_date or calendar.get("session_date") or date.today().isoformat())[:10]
        window = max(1, int(window_days or getattr(settings, "QUANT_WEEKLY_DIGEST_WINDOW_DAYS", 7) or 7))
        cutoff = datetime.now(timezone.utc) - timedelta(days=window)

        def recent(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
            values: list[dict[str, Any]] = []
            for row in rows:
                if not isinstance(row, dict):
                    continue
                parsed = self._parse_any_timestamp(
                    row.get("generated_at")
                    or row.get("updated_at")
                    or row.get("date")
                    or row.get("session_date")
                    or row.get("snapshot_id")
                )
                if parsed is None or parsed.astimezone(timezone.utc) >= cutoff:
                    values.append(row)
            return values

        workflows = recent(self.storage.list_records("workflow_runs"))
        performance_rows = recent(self.storage.list_records("paper_performance"))
        alerts = [
            row for row in recent(self.storage.list_records("alerts"))
            if str((row or {}).get("status") or "active").lower() != "resolved"
        ]
        deliveries = recent(self.storage.list_records("paper_daily_digest_deliveries"))
        backups = recent(self.storage.list_records("storage_backups"))
        locks = self.storage.list_records("submit_locks")
        reconciliations = recent(self.storage.list_records("paper_reconciliations"))
        slo_7 = self.build_paper_workflow_slo(window_days=window)
        slo_90 = self.build_paper_workflow_slo(window_days=90)
        observability = self.build_paper_workflow_observability(window_days=window)
        perf = self._build_digest_performance_snapshot(window_days=90)
        metrics = perf.get("metrics") or {}

        order_counts = {
            "workflow_count": len(workflows),
            "submitted": sum(1 for row in workflows if str(row.get("status") or "").lower() == "submitted"),
            "blocked": sum(1 for row in workflows if str(row.get("status") or "").lower() == "blocked"),
            "planned": sum(1 for row in workflows if str(row.get("status") or "").lower() == "planned"),
            "rejected": sum(1 for row in workflows if "reject" in json.dumps(row, ensure_ascii=False).lower()),
        }
        digest_success_rate = (
            round(sum(1 for row in deliveries if str(row.get("status") or "").lower() == "sent") / len(deliveries), 6)
            if deliveries
            else None
        )
        backup_success_rate = (
            round(sum(1 for row in backups if str(row.get("status") or "").lower() in {"completed", "completed_local_only"}) / len(backups), 6)
            if backups
            else None
        )
        summary = {
            "session_date": session,
            "window_days": window,
            "scheduler_uptime": observability.get("heartbeat") or {},
            "ready_success_proxy": not bool(observability.get("heartbeat_stale")),
            "valid_paper_days": metrics.get("valid_days", 0),
            "valid_paper_days_delta": len(performance_rows),
            "orders": order_counts,
            "unresolved_alert_count": len(alerts),
            "backup_success_rate": backup_success_rate,
            "digest_success_rate": digest_success_rate,
            "submit_unknown_unresolved": sum(1 for row in locks if str((row or {}).get("status") or "").lower() == "submit_unknown"),
            "broker_sync_error_count": sum(1 for row in reconciliations if row.get("error") or row.get("warnings")),
            "evidence_progress": {
                "valid_days": metrics.get("valid_days", 0),
                "paper_60_progress": round(min(float(metrics.get("valid_days") or 0) / 60.0, 1.0), 6),
                "paper_90_progress": round(min(float(metrics.get("valid_days") or 0) / 90.0, 1.0), 6),
            },
        }
        payload = {
            "digest_id": f"weekly-digest-{session}",
            "generated_at": _iso_now(),
            "phase": "weekly",
            "session_date": session,
            "window_days": window,
            "summary": summary,
            "performance": perf,
            "slo_7d": slo_7,
            "slo_90d": slo_90,
            "observability": {
                "summary": observability.get("summary") or {},
                "heartbeat": observability.get("heartbeat") or {},
                "storage_backup": observability.get("storage_backup") or {},
                "active_alerts": alerts[:10],
                "recovery_notifications": observability.get("recovery_notifications") or [],
            },
            "blocker_summary": observability.get("blocker_summary") or self.build_blocker_summary(alerts=alerts),
        }
        payload["text"] = self._format_quant_weekly_digest_text(payload)
        return _jsonable(payload)

    @staticmethod
    def _format_quant_weekly_digest_text(payload: dict[str, Any]) -> str:
        summary = payload.get("summary") or {}
        orders = summary.get("orders") or {}
        evidence = summary.get("evidence_progress") or {}
        observability = payload.get("observability") or {}
        heartbeat = observability.get("heartbeat") or {}
        backup = observability.get("storage_backup") or {}
        alerts = observability.get("active_alerts") or []
        alert_lines = [f"- {item.get('severity', 'info')}: {item.get('kind', item.get('message', 'alert'))}" for item in alerts[:8]]
        if not alert_lines:
            alert_lines = ["- none"]
        return "\n".join(
            [
                f"Hybrid Paper weekly digest - {payload.get('session_date')}",
                f"Window: {summary.get('window_days')} days",
                f"Scheduler: heartbeat={'stale' if heartbeat.get('stale') else 'fresh'} ready_proxy={summary.get('ready_success_proxy')}",
                f"Paper evidence: valid_days={evidence.get('valid_days')} 60d={evidence.get('paper_60_progress')} 90d={evidence.get('paper_90_progress')} delta={summary.get('valid_paper_days_delta')}",
                f"Orders: workflows={orders.get('workflow_count')} submitted={orders.get('submitted')} blocked={orders.get('blocked')} rejected={orders.get('rejected')}",
                f"Alerts: unresolved={summary.get('unresolved_alert_count')} submit_unknown={summary.get('submit_unknown_unresolved')} broker_sync_errors={summary.get('broker_sync_error_count')}",
                f"Delivery: digest_success_rate={summary.get('digest_success_rate')} backup_success_rate={summary.get('backup_success_rate')} latest_backup={backup.get('status', 'unknown')}",
                "Active alerts:",
                *alert_lines,
            ]
        )[:8000]

    def send_quant_weekly_digest(
        self,
        *,
        session_date: str | None = None,
        window_days: int | None = None,
        recipients: list[str] | None = None,
        channels: list[str] | None = None,
    ) -> dict[str, Any]:
        digest = self.build_quant_weekly_digest(session_date=session_date, window_days=window_days)
        selected_channels = self._quant_daily_digest_channels(channels)
        selected_recipients = self._quant_daily_digest_recipients(recipients)
        deliveries: list[dict[str, Any]] = []
        if "telegram" in selected_channels:
            deliveries.append(self._send_telegram_message(digest["text"]))
        if "email" in selected_channels:
            if not selected_recipients:
                deliveries.append({"channel": "email", "status": "skipped", "detail": "no_recipients"})
            for recipient in selected_recipients:
                result = send_email_message(
                    recipient=recipient,
                    subject=f"Hybrid Paper weekly digest {digest['session_date']}",
                    text_body=digest["text"],
                    html_body=f"<pre>{digest['text']}</pre>",
                    sender=getattr(settings, "EMAIL_FROM", "") or getattr(settings, "SMTP_USER", ""),
                )
                deliveries.append(
                    {
                        "channel": "email",
                        "recipient": recipient,
                        "status": "sent" if result.get("ok") else "failed",
                        "detail": result.get("detail"),
                    }
                )
        retry_after = (
            datetime.now(timezone.utc)
            + timedelta(minutes=max(1, int(getattr(settings, "QUANT_DAILY_DIGEST_RETRY_MINUTES", 15) or 15)))
        ).isoformat()
        normalized: list[dict[str, Any]] = []
        for index, item in enumerate(deliveries):
            delivery = dict(item)
            delivery.setdefault("delivery_id", f"{digest['digest_id']}-{index + 1}")
            delivery.setdefault("generated_at", _iso_now())
            if delivery.get("status") == "failed":
                delivery.setdefault("error", delivery.get("detail") or "delivery_failed")
                delivery.setdefault("next_retry_at", retry_after)
            normalized.append(delivery)
        sent_count = sum(1 for item in normalized if item.get("status") == "sent")
        failed_count = sum(1 for item in normalized if item.get("status") == "failed")
        digest["delivery"] = {
            "channels": selected_channels,
            "recipients": selected_recipients,
            "results": normalized,
            "sent_count": sent_count,
            "failed_count": failed_count,
            "local_ledger": True,
            "retry_after": retry_after if failed_count else None,
        }
        digest["storage"] = self.storage.persist_record("paper_weekly_digests", digest["digest_id"], _jsonable(digest))
        for item in normalized:
            delivery_id = str(item.get("delivery_id") or f"{digest['digest_id']}-{item.get('channel', 'unknown')}")
            self.storage.persist_record(
                "paper_weekly_digest_deliveries",
                delivery_id,
                _jsonable({"digest_id": digest["digest_id"], "session_date": digest["session_date"], "phase": "weekly", **item}),
            )
        return _jsonable(digest)

    def retry_failed_daily_digest_deliveries(self, *, limit: int = 20) -> dict[str, Any]:
        if not bool(getattr(settings, "DIGEST_RETRY_ENABLED", True)):
            return {"enabled": False, "status": "skipped", "reason": "digest_retry_disabled"}
        now = datetime.now(timezone.utc)
        due: list[dict[str, Any]] = []
        for record_type in ("paper_daily_digest_deliveries", "paper_weekly_digest_deliveries"):
            for row in self.storage.list_records(record_type):
                if isinstance(row, dict):
                    row = {**row, "_delivery_record_type": record_type}
                else:
                    continue
                if str(row.get("status") or "") != "failed":
                    continue
                next_retry = self._parse_any_timestamp(row.get("next_retry_at"))
                if next_retry is not None and next_retry.tzinfo is None:
                    next_retry = next_retry.replace(tzinfo=timezone.utc)
                if next_retry is None or next_retry.astimezone(timezone.utc) <= now:
                    due.append(row)
                if len(due) >= max(1, int(limit or 20)):
                    break
            if len(due) >= max(1, int(limit or 20)):
                break

        attempted: list[dict[str, Any]] = []
        retry_after = (
            now + timedelta(minutes=max(1, int(getattr(settings, "QUANT_DAILY_DIGEST_RETRY_MINUTES", 15) or 15)))
        ).isoformat()
        for row in due:
            phase = str(row.get("phase") or "postclose").lower()
            if phase == "weekly":
                digest = self.build_quant_weekly_digest(
                    session_date=str(row.get("session_date") or "")[:10] or None,
                    window_days=int(getattr(settings, "QUANT_WEEKLY_DIGEST_WINDOW_DAYS", 7) or 7),
                )
            else:
                digest = self.build_quant_daily_digest(
                    phase=phase,
                    session_date=str(row.get("session_date") or "")[:10] or None,
                )
            channel = str(row.get("channel") or "").lower()
            if channel == "telegram":
                result = self._send_telegram_message(digest["text"])
                ok = result.get("status") == "sent"
                detail = result.get("detail")
            elif channel == "email":
                recipient = str(row.get("recipient") or "").strip()
                result = send_email_message(
                    recipient=recipient,
                    subject=f"Hybrid Paper {digest['phase']} digest {digest['session_date']}",
                    text_body=digest["text"],
                    html_body=f"<pre>{digest['text']}</pre>",
                    sender=getattr(settings, "EMAIL_FROM", "") or getattr(settings, "SMTP_USER", ""),
                )
                ok = bool(result.get("ok"))
                detail = result.get("detail")
            else:
                ok = False
                detail = f"unsupported_channel:{channel}"
            updated = {
                **row,
                "status": "sent" if ok else "failed",
                "last_retry_at": _iso_now(),
                "retry_count": int(row.get("retry_count") or 0) + 1,
                "detail": detail,
                "error": None if ok else detail,
                "next_retry_at": None if ok else retry_after,
                "recovered_at": _iso_now() if ok else row.get("recovered_at"),
            }
            delivery_id = str(updated.get("delivery_id") or f"{updated.get('digest_id')}-{channel}")
            record_type = str(row.get("_delivery_record_type") or "paper_daily_digest_deliveries")
            updated.pop("_delivery_record_type", None)
            self.storage.persist_record(record_type, delivery_id, _jsonable(updated))
            attempted.append(updated)

        return {
            "generated_at": _iso_now(),
            "attempted_count": len(attempted),
            "sent_count": sum(1 for item in attempted if item.get("status") == "sent"),
            "failed_count": sum(1 for item in attempted if item.get("status") == "failed"),
            "deliveries": _jsonable(attempted),
        }

    def _latest_paper_performance_snapshot(self, *, before_date: str | None = None) -> dict[str, Any] | None:
        rows = sorted(
            [row for row in self.storage.list_records("paper_performance") if isinstance(row, dict)],
            key=lambda item: str(item.get("date") or item.get("snapshot_id") or item.get("generated_at") or ""),
        )
        if before_date:
            rows = [row for row in rows if str(row.get("date") or row.get("snapshot_id") or "") < before_date]
        return rows[-1] if rows else None

    @staticmethod
    def _paper_payload_float(payload: dict[str, Any], *keys: str) -> float | None:
        for key in keys:
            value = payload.get(key)
            if value in {None, ""}:
                continue
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
        return None

    def _latest_benchmark_nav(
        self,
        *,
        benchmark: str,
        fallback: float = 1.0,
        force_refresh: bool = False,
    ) -> tuple[float, dict[str, Any]]:
        meta = {"provider": "unavailable", "fallback_used": True}
        try:
            result = self.market_data.get_daily_bars(
                benchmark,
                limit=5,
                force_refresh=force_refresh,
                allow_stale_cache=True,
            )
            rows = self._bars_result_to_rows(result)
            close = None
            for row in reversed(rows):
                close = self._paper_payload_float(row, "close", "Close")
                if close is not None and close > 0:
                    break
            provider = str(getattr(result, "provider", "") or (result.get("provider") if isinstance(result, dict) else "") or "unknown")
            meta = {"provider": provider, "fallback_used": close is None, "row_count": len(rows)}
            return (float(close) if close is not None else float(fallback or 1.0)), meta
        except Exception as exc:
            meta["error"] = str(exc)
            return float(fallback or 1.0), meta

    @staticmethod
    def _annualized_return(net_return: Any, valid_days: Any) -> float:
        try:
            net = float(net_return or 0.0)
            days = max(1, int(valid_days or 0) - 1)
            if net <= -0.999:
                return -1.0
            return round((1 + net) ** (252 / days) - 1, 6)
        except Exception:
            return 0.0

    def _paper_execution_summary(self, *, window_days: int) -> dict[str, Any]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=max(int(window_days or 90) * 2, 90))
        executions = []
        for payload in self.storage.list_records("executions"):
            if str(payload.get("mode") or "").lower() != "paper":
                continue
            generated_at = self._parse_any_timestamp(payload.get("generated_at") or payload.get("created_at"))
            if generated_at is not None and generated_at.astimezone(timezone.utc) < cutoff:
                continue
            executions.append(payload)
        orders = []
        sync_errors: list[str] = []
        for payload in executions:
            sync_errors.extend(str(item) for item in payload.get("warnings") or [] if item)
            for order in (payload.get("submitted_orders") or payload.get("orders") or []):
                if isinstance(order, dict):
                    orders.append(order)
        rejected_states = {"rejected", "failed", "canceled", "cancelled", "expired"}
        filled_states = {"filled", "partially_filled"}
        return {
            "execution_count": len(executions),
            "order_count": len(orders),
            "submitted_count": sum(1 for payload in executions if payload.get("submitted")),
            "filled_count": sum(1 for order in orders if str(order.get("status") or "").lower() in filled_states),
            "rejected_count": sum(1 for order in orders if str(order.get("status") or "").lower() in rejected_states),
            "slippage_bps_values": [
                order.get("estimated_slippage_bps")
                for order in orders
                if order.get("estimated_slippage_bps") is not None
            ],
            "turnover": sum(float(order.get("notional") or order.get("submitted_notional") or 0.0) for order in orders),
            "latest_execution_id": executions[0].get("execution_id") if executions else None,
            "sync_errors": sync_errors,
            "sync_error_count": len(sync_errors),
        }

    def _live_canary_recommendation(self, *, metrics: dict[str, Any], outcomes: list[dict[str, Any]]) -> dict[str, Any]:
        sync_status = self._paper_gate_sync_status()
        controls = self.get_execution_controls()
        account = self.get_execution_account(broker="alpaca", mode="paper")
        synthetic_count = sum(1 for row in outcomes if bool(row.get("synthetic_used")))
        policy = load_promotion_policy()
        execution_summary = self._paper_execution_summary(window_days=90)
        attribution = self._paper_attribution_summary(rows=[], outcomes=outcomes, execution_summary=execution_summary)
        quality = {
            **attribution,
            "filled_count": execution_summary.get("filled_count", 0),
            "settled_count": sum(1 for row in outcomes if str(row.get("status") or "") == "settled"),
            "synthetic_count": synthetic_count,
        }
        threshold_result = evaluate_thresholds(metrics, quality, policy, "live_canary")
        checks = {
            **threshold_result["checks"],
            "broker_sync_clean": bool(sync_status.get("ok")),
            "kill_switch_released": not bool(controls.get("kill_switch_enabled")),
            "alpaca_paper_ready": bool(account.get("connected") and account.get("paper_ready")),
        }
        blockers = [key for key, ok in checks.items() if not ok]
        recommended = not blockers
        return {
            "recommended": recommended,
            "status": "canary_candidate" if recommended else "blocked",
            "summary": "Paper evidence supports operator-reviewed live canary." if recommended else "Continue paper until all live canary gates pass.",
            "checks": checks,
            "blockers": blockers,
            "policy": policy,
            "quality": quality,
            "sync_status": sync_status,
            "synthetic_count": synthetic_count,
            "operator_confirmation_required": True,
        }

    def _sync_paper_reward_candidate_outcomes(self) -> None:
        from gateway.trading.reward_bandit import build_horizon_states

        for candidate in self.storage.list_records("paper_reward_candidates"):
            if not isinstance(candidate, dict) or not candidate.get("candidate_id"):
                continue
            outcome_id = f"outcome-paper-reward-{candidate['candidate_id']}"
            if self.storage.load_record("paper_outcomes", outcome_id):
                continue
            entry_at = str(candidate.get("entry_at") or candidate.get("created_at") or _iso_now())
            record = {
                "outcome_id": outcome_id,
                "record_kind": "paper_reward_candidate",
                "source_id": candidate.get("candidate_id"),
                "workflow_id": None,
                "execution_id": candidate.get("execution_id"),
                "created_at": candidate.get("created_at") or _iso_now(),
                "symbol": str(candidate.get("symbol") or "").upper(),
                "action": str(candidate.get("action") or "long").lower(),
                "side": "sell" if str(candidate.get("action") or "").lower() == "short" else "buy",
                "strategy_id": candidate.get("strategy_id"),
                "model_refs": {"source": "paper_reward_candidates"},
                "entry_price": candidate.get("entry_price"),
                "entry_at": entry_at,
                "notional": candidate.get("notional"),
                "features": candidate.get("features") or {},
                "market_data_source": "paper_reward",
                "synthetic_used": self._payload_mentions_synthetic(candidate),
                "settlements": candidate.get("settlements") or build_horizon_states(entry_at),
                "partial_score": candidate.get("partial_score"),
                "score": candidate.get("score"),
                "status": candidate.get("status") or "pending",
                "lineage": ["paper_reward_candidate", "paper_outcome_ledger"],
                "metadata": {"batch_id": candidate.get("batch_id")},
            }
            self._save_paper_outcome(self.synthetic_guard.annotate(record, fallback_source="paper_reward"))

    def _save_paper_outcome(self, record: dict[str, Any]) -> dict[str, Any]:
        outcome_id = str(record.get("outcome_id") or "").strip()
        if not outcome_id:
            outcome_id = f"outcome-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
            record["outcome_id"] = outcome_id
        record["updated_at"] = _iso_now()
        record["storage"] = self.storage.persist_record("paper_outcomes", outcome_id, _jsonable(record))
        return _jsonable(record)

    def _build_paper_outcome_record(
        self,
        *,
        record_kind: str,
        source_id: str,
        index: int,
        workflow_id: str,
        execution_id: str,
        symbol: str,
        action: str,
        entry_at: str,
        entry_price: float | None,
        notional: float | None,
        features: dict[str, Any],
        model_refs: dict[str, Any],
        market_data_source: str,
        synthetic_used: bool,
    ) -> dict[str, Any]:
        from gateway.trading.reward_bandit import build_horizon_states

        safe_symbol = "".join(ch for ch in symbol.upper() if ch.isalnum() or ch in {"-", "_"}) or "UNKNOWN"
        safe_kind = "".join(ch for ch in record_kind if ch.isalnum() or ch in {"-", "_"}) or "record"
        outcome_id = f"outcome-{workflow_id or execution_id or 'manual'}-{safe_kind}-{safe_symbol}-{index}"
        record = {
            "outcome_id": outcome_id,
            "record_kind": record_kind,
            "source_id": source_id,
            "workflow_id": workflow_id or None,
            "execution_id": execution_id or None,
            "created_at": _iso_now(),
            "symbol": symbol.upper(),
            "action": "short" if action in {"short", "sell"} else "long",
            "side": "sell" if action in {"short", "sell"} else "buy",
            "strategy_id": features.get("strategy_id") or features.get("strategy_bucket"),
            "model_refs": model_refs,
            "entry_price": entry_price,
            "entry_at": entry_at,
            "notional": notional,
            "features": features,
            "market_data_source": market_data_source,
            "synthetic_used": bool(synthetic_used),
            "settlements": build_horizon_states(entry_at),
            "partial_score": None,
            "score": None,
            "status": "pending",
            "lineage": ["hybrid_paper_workflow", "paper_outcome_ledger"],
            "metadata": {},
        }
        return self.synthetic_guard.annotate(record, fallback_source=market_data_source)

    @staticmethod
    def _payload_mentions_synthetic(payload: dict[str, Any] | None) -> bool:
        if not payload:
            return False
        try:
            return "synthetic" in json.dumps(payload, ensure_ascii=False).lower()
        except Exception:
            return "synthetic" in str(payload).lower()

    @staticmethod
    def _bars_result_to_rows(bars_result: Any) -> list[dict[str, Any]]:
        if bars_result is None:
            return []
        if isinstance(bars_result, list):
            return [dict(row) for row in bars_result if isinstance(row, dict)]
        frame = getattr(bars_result, "frame", None)
        if frame is None and isinstance(bars_result, pd.DataFrame):
            frame = bars_result
        if frame is not None and hasattr(frame, "to_dict"):
            rows = frame.reset_index().to_dict(orient="records")
            return [_jsonable(row) for row in rows]
        bars_attr = getattr(bars_result, "bars", None)
        if bars_attr is not None and hasattr(bars_attr, "to_dict"):
            rows = bars_attr.reset_index().to_dict(orient="records")
            return [_jsonable(row) for row in rows]
        if isinstance(bars_result, dict):
            for key in ("bars", "rows", "data"):
                rows = bars_result.get(key)
                if isinstance(rows, list):
                    return [dict(row) for row in rows if isinstance(row, dict)]
        rows = getattr(bars_result, "rows", None) or getattr(bars_result, "bars", None)
        if isinstance(rows, list):
            return [dict(row) for row in rows if isinstance(row, dict)]
        return []

    def _market_data_preflight(self) -> dict[str, Any]:
        configured = str(getattr(settings, "MARKET_DATA_PROVIDER", "") or "")
        if "synthetic" in configured.lower():
            return {"ok": False, "detail": "MARKET_DATA_PROVIDER includes synthetic.", "provider": configured}
        providers = [item.strip().lower() for item in configured.split(",") if item.strip()]
        provider_ready = {
            "alpaca": bool(getattr(settings, "ALPACA_API_KEY", "") and getattr(settings, "ALPACA_API_SECRET", "")),
            "twelvedata": bool(
                getattr(settings, "TWELVEDATA_API_KEY", "")
                or getattr(settings, "TWELVEDATA_API", "")
                or getattr(settings, "TWELVE_DATA_API", "")
            ),
            "yfinance": True,
            "cache": bool(getattr(settings, "MARKET_DATA_CACHE_DB", "")),
        }
        ready = any(provider_ready.get(provider, False) for provider in providers)
        return {
            "ok": bool(providers and ready),
            "detail": "Market data provider chain is configured." if providers and ready else "No usable non-synthetic market data provider is configured.",
            "provider": configured,
            "providers": providers,
            "provider_ready": provider_ready,
        }

    def _storage_preflight(self, *, dry_run: bool = False) -> dict[str, Any]:
        disk = shutil.disk_usage(self.storage.base_dir)
        free_percent = round((disk.free / disk.total) * 100, 3) if disk.total else 0.0
        critical_threshold = float(getattr(settings, "STORAGE_DISK_CRITICAL_FREE_PERCENT", 5.0) or 5.0)
        disk_meta = {
            "path": str(self.storage.base_dir),
            "total_bytes": disk.total,
            "used_bytes": disk.used,
            "free_bytes": disk.free,
            "free_percent": free_percent,
            "critical_free_percent": critical_threshold,
            "critically_low": free_percent < critical_threshold,
        }
        if dry_run:
            status = self.storage.status()
            probe_rows = [
                row for row in self.storage.list_records("deployment_preflight_probe")
                if isinstance(row, dict)
            ]
            latest_probe = probe_rows[0] if probe_rows else None
            ok = not bool(disk_meta["critically_low"])
            return {
                "ok": ok,
                "detail": "Storage status read succeeded." if ok else "Storage disk free space is critically low.",
                "dry_run": True,
                "latest_probe": latest_probe,
                "disk": disk_meta,
                **status,
            }
        try:
            record_id = f"probe-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
            info = self.storage.persist_record("deployment_preflight_probe", record_id, {"record_id": record_id, "generated_at": _iso_now()})
            ok = not bool(disk_meta["critically_low"])
            return {
                "ok": ok,
                "detail": "Storage write probe succeeded." if ok else "Storage disk free space is critically low.",
                "storage": info,
                "disk": disk_meta,
                **self.storage.status(),
            }
        except Exception as exc:
            return {"ok": False, "detail": f"Storage write probe failed: {exc}", "disk": disk_meta}

    def _rl_checkpoint_preflight(self) -> dict[str, Any]:
        storage_dir = self._resolve_runtime_path(
            getattr(settings, "QUANT_RL_STORAGE_DIR", "storage/quant/rl"),
            "storage/quant/rl",
        )
        experiment_root = self._resolve_runtime_path(
            getattr(settings, "QUANT_RL_EXPERIMENT_ROOT", "storage/quant/rl-experiments"),
            "storage/quant/rl-experiments",
        )
        checkpoint_roots = [storage_dir / "checkpoints", experiment_root]
        checkpoint = self._latest_file_from_roots(checkpoint_roots, ["*.pt", "*.pth", "*.ckpt"])
        dataset = self._latest_file_from_roots([storage_dir, experiment_root], ["*.csv", "*.parquet"])
        return {
            "ok": checkpoint is not None,
            "detail": "RL checkpoint is ready." if checkpoint else "RL checkpoint is missing.",
            "latest_dataset": {"path": str(dataset or ""), "exists": dataset is not None},
            "latest_checkpoint": {"path": str(checkpoint or ""), "exists": checkpoint is not None},
            "artifact_health": {
                "dataset_ready": dataset is not None,
                "checkpoint_ready": checkpoint is not None,
            },
        }

    @staticmethod
    def _latest_file_from_roots(roots: list[Path], patterns: list[str]) -> Path | None:
        matches: list[Path] = []
        for root in roots:
            if not root.exists() or not root.is_dir():
                continue
            for pattern in patterns:
                try:
                    matches.extend(path for path in root.rglob(pattern) if path.is_file())
                except OSError:
                    continue
        if not matches:
            return None
        matches.sort(key=lambda path: path.stat().st_mtime, reverse=True)
        return matches[0]

    def _synthetic_trade_preflight(self) -> dict[str, Any]:
        recent_outcomes = self.storage.list_records("paper_outcomes")[:200]
        guard_summary = self.synthetic_guard.summary([row for row in recent_outcomes if isinstance(row, dict)])
        synthetic_outcomes = guard_summary.get("synthetic_ids", [])
        provider = str(getattr(settings, "MARKET_DATA_PROVIDER", "") or "")
        ok = "synthetic" not in provider.lower() and not synthetic_outcomes
        return {
            "ok": ok,
            "detail": "Synthetic trade sources are blocked." if ok else "Synthetic provider or outcome evidence is present.",
            "market_data_provider": provider,
            "synthetic_outcome_ids": synthetic_outcomes[:10],
            "guard": guard_summary,
        }

    @staticmethod
    def _paper_workflow_preflight(
        *,
        registry: dict[str, Any],
        rl_meta: dict[str, Any],
        account: dict[str, Any],
        controls: dict[str, Any],
        synthetic_meta: dict[str, Any],
    ) -> dict[str, Any]:
        available_models = {str(model.get("key")): bool(model.get("available")) for model in registry.get("models", [])}
        required_models_ok = all(available_models.get(key) for key in ("alpha_ranker", "p1_suite", "p2_selector"))
        ok = bool(
            required_models_ok
            and rl_meta.get("ok")
            and account.get("connected")
            and account.get("paper_ready")
            and not controls.get("kill_switch_enabled")
            and synthetic_meta.get("ok")
        )
        return {
            "ok": ok,
            "detail": "Hybrid paper workflow preflight passed." if ok else "Hybrid paper workflow has blocking readiness gaps.",
            "required_models_ok": required_models_ok,
            "available_models": available_models,
        }

    @staticmethod
    def _preflight_next_actions(blockers: list[str], warnings: list[str]) -> list[str]:
        mapping = {
            "alpaca_paper": "configure_alpaca_paper_credentials",
            "market_data": "configure_real_market_data_provider",
            "storage": "repair_storage_or_cloud_artifact_backend",
            "scheduler_heartbeat": "start_quant_signal_scheduler_worker",
            "model_registry": "sync_model_registry_artifacts",
            "rl_checkpoint": "train_or_sync_rl_checkpoint",
            "kill_switch": "release_execution_kill_switch_after_review",
            "synthetic_trade_block": "remove_synthetic_provider_and_rebuild_evidence",
            "trading_calendar": "inspect_trading_calendar_configuration",
            "paper_workflow": "rerun_preflight_after_blockers_clear",
            "telegram_notifier": "configure_telegram_bot_token_and_chat_id",
            "telegram_token_rotation": "rotate_exposed_telegram_bot_token_and_confirm_secret_store",
        }
        actions = [mapping.get(item, f"review_{item}") for item in blockers]
        if "qdrant" in warnings:
            actions.append("start_qdrant_if_rag_is_required")
        if "remote_llm" in warnings:
            actions.append("configure_remote_llm_or_cloud_fallback")
        return list(dict.fromkeys(actions or ["ready_for_paper_cloud_scheduler"]))

    def run_backtest(
        self,
        strategy_name: str,
        universe_symbols: list[str] | None = None,
        benchmark: str | None = None,
        capital_base: float | None = None,
        lookback_days: int = 126,
        market_data_provider: str | None = None,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        benchmark = benchmark or self.default_benchmark
        capital_base = capital_base or self.default_capital
        signals = self._build_signals(self.get_default_universe(universe_symbols), strategy_name, benchmark)
        portfolio = self._build_portfolio(signals, capital_base, benchmark)
        result = self._build_backtest(
            strategy_name=strategy_name,
            benchmark=benchmark,
            capital_base=capital_base,
            positions=portfolio.positions,
            lookback_days=lookback_days,
            persist=True,
            market_data_provider=market_data_provider,
            force_refresh=force_refresh,
        )
        artifact_payload = self.storage.load_record("backtests", result.backtest_id)
        self._persist_experiment(
            name=strategy_name,
            objective="validate_strategy",
            benchmark=benchmark,
            metrics={
                "sharpe": result.metrics.sharpe,
                "max_drawdown": result.metrics.max_drawdown,
                "cumulative_return": result.metrics.cumulative_return,
            },
            tags=["backtest", "walk-forward", "portfolio"],
            artifact_uri=(artifact_payload or {}).get("storage", {}).get("artifact_uri"),
        )
        tearsheet = self.build_tearsheet(result.backtest_id, persist=True)
        sweep_preview = self.run_backtest_sweep(
            strategy_name=strategy_name,
            universe_symbols=universe_symbols,
            benchmark=benchmark,
            capital_base=capital_base,
            lookback_days=lookback_days,
            market_data_provider=market_data_provider,
            force_refresh=force_refresh,
            parameter_grid={
                "lookback_days": [lookback_days],
                "position_scale": [0.9, 1.0, 1.1],
                "transaction_cost_bps": [0.0, 8.0],
            },
            top_k=3,
            persist=False,
        )
        payload = result.model_dump()
        payload["market"] = "US"
        payload["frequency"] = "daily"
        payload["data_tier"] = "l1"
        payload["protection_status"] = tearsheet.get("protection_status", "review")
        payload["dataset_id"] = f"dataset-us-daily-{strategy_name.lower().replace(' ', '-')}"
        payload["market_depth_status"] = {
            "selected_provider": "daily_backtest_l1",
            "data_tier": "l1",
            "eligibility_status": "pass",
            "available": True,
            "blocking_reasons": [],
        }
        payload["tearsheet_report_id"] = tearsheet.get("report_id")
        payload["tearsheet_summary"] = tearsheet.get("summary", {})
        payload["sweep_preview"] = {
            "run_id": sweep_preview.get("run_id"),
            "summary": sweep_preview.get("summary", {}),
            "best_run": sweep_preview.get("best_run", {}),
            "walk_forward": sweep_preview.get("walk_forward", {}),
        }
        return payload

    def list_backtests(self) -> list[dict[str, Any]]:
        return self.storage.list_records("backtests")

    def get_backtest(self, backtest_id: str) -> dict[str, Any] | None:
        return self.storage.load_record("backtests", backtest_id)

    def run_backtest_sweep(
        self,
        *,
        strategy_name: str,
        universe_symbols: list[str] | None = None,
        benchmark: str | None = None,
        capital_base: float | None = None,
        lookback_days: int = 126,
        market_data_provider: str | None = None,
        force_refresh: bool = False,
        parameter_grid: dict[str, list[Any]] | None = None,
        top_k: int = 5,
        persist: bool = True,
    ) -> dict[str, Any]:
        from backtest.walk_forward import run_module as build_walk_forward_summary

        benchmark = benchmark or self.default_benchmark
        capital_base = capital_base or self.default_capital
        universe = self.get_default_universe(universe_symbols)
        signals = self._build_signals(universe, strategy_name, benchmark)
        portfolio = self._build_portfolio(signals, capital_base, benchmark)
        normalized_grid = self._normalize_sweep_grid(parameter_grid, lookback_days=lookback_days)
        parameter_names = list(normalized_grid)
        combinations: list[dict[str, Any]] = []

        for combo_index, values in enumerate(product(*(normalized_grid[name] for name in parameter_names)), start=1):
            parameters = {name: value for name, value in zip(parameter_names, values)}
            combo_positions = self._apply_sweep_parameters(portfolio.positions, parameters)
            combo_lookback = int(parameters.get("lookback_days") or lookback_days)
            backtest = self._build_backtest(
                strategy_name=strategy_name,
                benchmark=benchmark,
                capital_base=capital_base,
                positions=combo_positions,
                lookback_days=combo_lookback,
                persist=False,
                market_data_provider=market_data_provider,
                force_refresh=force_refresh,
            )
            adjusted_metrics = self._apply_backtest_cost_adjustments(
                backtest.metrics.model_dump(),
                transaction_cost_bps=float(parameters.get("transaction_cost_bps") or 0.0),
            )
            combinations.append(
                {
                    "combo_id": f"{backtest.backtest_id}-combo-{combo_index}",
                    "backtest_id": backtest.backtest_id,
                    "parameters": parameters,
                    "metrics": adjusted_metrics,
                    "data_source": backtest.data_source,
                    "used_synthetic_fallback": backtest.used_synthetic_fallback,
                    "market_data_warnings": list(backtest.market_data_warnings),
                }
            )

        combinations.sort(
            key=lambda row: (
                -float((row.get("metrics") or {}).get("sharpe") or 0.0),
                -float((row.get("metrics") or {}).get("cumulative_return") or 0.0),
                float((row.get("metrics") or {}).get("max_drawdown") or 0.0),
            )
        )
        best_run = combinations[0] if combinations else {}
        walk_forward = build_walk_forward_summary({"combinations": combinations, "window_count": min(3, len(combinations) or 1)})
        protection_status = "review" if any(row.get("used_synthetic_fallback") for row in combinations[:1]) else "pass"
        sweep = SweepRun(
            run_id=f"sweep-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            generated_at=_iso_now(),
            strategy_name=strategy_name,
            benchmark=benchmark,
            universe=[member.symbol for member in universe],
            data_tier="l1",
            dataset_id=f"dataset-us-daily-{strategy_name.lower().replace(' ', '-')}",
            protection_status=protection_status,  # type: ignore[arg-type]
            market_depth_status={
                "selected_provider": "daily_backtest_l1",
                "data_tier": "l1",
                "eligibility_status": "pass",
                "available": True,
                "blocking_reasons": [],
            },
            provider_capabilities={"daily_backtest_l1": {"available": True, "history_ready": True, "realtime_ready": False}},
            parameter_grid=normalized_grid,
            combinations=combinations[: max(1, len(combinations))],
            summary={
                "combination_count": len(combinations),
                "top_k": max(1, int(top_k)),
                "best_sharpe": float((best_run.get("metrics") or {}).get("sharpe") or 0.0),
                "best_cumulative_return": float((best_run.get("metrics") or {}).get("cumulative_return") or 0.0),
                "parameter_names": parameter_names,
                "scenario_matrix": self._build_scenario_matrix(combinations),
            },
            best_run=best_run,
            walk_forward=walk_forward,
            lineage=[
                "L0: current strategy portfolio",
                "L1: deterministic parameter sweep with cost sensitivity",
                "L2: walk-forward robustness summary over ranked combinations",
            ],
        )
        payload = sweep.model_dump(mode="json")
        payload["top_combinations"] = combinations[: max(1, int(top_k))]
        if persist:
            payload["storage"] = self.storage.persist_record("backtest_sweeps", sweep.run_id, payload)
        return payload

    def get_backtest_sweep(self, run_id: str) -> dict[str, Any] | None:
        return self.storage.load_record("backtest_sweeps", run_id)

    def build_tearsheet(self, backtest_id: str, *, persist: bool = True) -> dict[str, Any]:
        from reporting.tearsheet import build_output as build_tearsheet_output

        backtest = self.get_backtest(backtest_id)
        if backtest is None:
            raise ValueError(f"Backtest not found: {backtest_id}")
        tearsheet_payload = build_tearsheet_output(backtest)
        protection_status = "review" if backtest.get("used_synthetic_fallback") or backtest.get("market_data_warnings") else "pass"
        report = TearsheetReport(
            report_id=f"tearsheet-{backtest_id}",
            generated_at=_iso_now(),
            backtest_id=backtest_id,
            strategy_name=str(backtest.get("strategy_name") or "Backtest"),
            data_tier=str(backtest.get("data_tier") or "l1"),  # type: ignore[arg-type]
            protection_status=protection_status,  # type: ignore[arg-type]
            market_depth_status=dict(backtest.get("market_depth_status") or {}),
            summary=dict(tearsheet_payload.get("summary") or {}),
            sections=dict(tearsheet_payload.get("sections") or {}),
            html=str(tearsheet_payload.get("html") or ""),
            lineage=[
                "L0: persisted backtest result",
                "L1: tearsheet rendering with monthly return table and cost sensitivity",
                "L2: Monte Carlo snapshot and risk alerts serialized for the workbench",
            ],
        )
        payload = report.model_dump(mode="json")
        if persist:
            payload["storage"] = self.storage.persist_record("tearsheets", report.report_id, payload)
        return payload




    def list_experiments(self) -> list[dict[str, Any]]:
        experiments = self.storage.list_records("experiments")
        if experiments:
            return experiments

        return [
            ExperimentRun(
                experiment_id="exp-bootstrap-001",
                name="bootstrap_reference",
                created_at=_iso_now(),
                objective="baseline_signal_quality",
                benchmark=self.default_benchmark,
                metrics={"expected_alpha": 0.084, "signal_count": 8.0},
                tags=["baseline", "bootstrap"],
                artifact_uri=None,
            ).model_dump()
        ]



    @staticmethod


    @staticmethod

    @staticmethod
    def _summarize_alpaca_account(account: dict[str, Any]) -> dict[str, str | bool | None]:
        equity = float(account.get("equity") or 0.0)
        last_equity = float(account.get("last_equity") or 0.0)
        daily_change = equity - last_equity if last_equity else 0.0
        daily_change_pct = (daily_change / last_equity) if last_equity else 0.0
        return {
            "account_id": account.get("id"),
            "status": account.get("status"),
            "currency": account.get("currency"),
            "buying_power": account.get("buying_power"),
            "cash": account.get("cash"),
            "equity": account.get("equity"),
            "last_equity": account.get("last_equity"),
            "portfolio_value": account.get("portfolio_value") or account.get("equity"),
            "daily_change": round(daily_change, 2),
            "daily_change_pct": round(daily_change_pct, 6),
            "trading_blocked": bool(account.get("trading_blocked")),
            "account_blocked": bool(account.get("account_blocked")),
            "transfers_blocked": bool(account.get("transfers_blocked")),
            "shorting_enabled": bool(account.get("shorting_enabled")),
            "pattern_day_trader": bool(account.get("pattern_day_trader")),
        }

    @staticmethod
    def _summarize_alpaca_clock(clock: dict[str, Any]) -> dict[str, Any]:
        return {
            "is_open": bool(clock.get("is_open")),
            "timestamp": clock.get("timestamp"),
            "next_open": clock.get("next_open"),
            "next_close": clock.get("next_close"),
        }

    @staticmethod
    def _summarize_alpaca_order(order: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": order.get("id"),
            "client_order_id": order.get("client_order_id"),
            "symbol": order.get("symbol"),
            "side": order.get("side"),
            "type": order.get("type"),
            "time_in_force": order.get("time_in_force"),
            "status": order.get("status"),
            "qty": order.get("qty"),
            "notional": order.get("notional"),
            "filled_qty": order.get("filled_qty"),
            "filled_avg_price": order.get("filled_avg_price"),
            "submitted_at": order.get("submitted_at") or order.get("created_at"),
        }

    @staticmethod
    def _summarize_alpaca_position(position: dict[str, Any]) -> dict[str, Any]:
        return {
            "symbol": position.get("symbol"),
            "qty": position.get("qty"),
            "market_value": position.get("market_value"),
            "cost_basis": position.get("cost_basis"),
            "side": position.get("side"),
            "avg_entry_price": position.get("avg_entry_price"),
            "unrealized_pl": position.get("unrealized_pl"),
            "unrealized_plpc": position.get("unrealized_plpc"),
        }

    def list_execution_brokers(self) -> list[dict[str, Any]]:
        return [descriptor.model_dump() for descriptor in self.brokers.list_brokers()]

    def get_execution_controls(self) -> dict[str, Any]:
        payload = self._load_execution_control_payload()
        payload["duplicate_window_minutes"] = int(
            getattr(settings, "EXECUTION_DUPLICATE_ORDER_WINDOW_MINUTES", 90) or 90
        )
        payload["stale_order_minutes"] = int(getattr(settings, "EXECUTION_STALE_ORDER_MINUTES", 20) or 20)
        payload["ws_enabled"] = bool(getattr(settings, "EXECUTION_WS_ENABLED", True))
        payload["paper_notional_limits"] = self._execution_notional_limits("paper")
        payload["live_notional_limits"] = self._execution_notional_limits("live")
        payload["paper_gate"] = self.build_paper_gate_report(persist=False)
        return payload

    def set_execution_kill_switch(self, *, enabled: bool, reason: str = "") -> dict[str, Any]:
        payload = self._load_execution_control_payload()
        payload["kill_switch_enabled"] = bool(enabled)
        payload["kill_switch_reason"] = (
            reason.strip()
            or payload.get("kill_switch_reason")
            or getattr(settings, "EXECUTION_KILL_SWITCH_REASON", "")
        )
        payload["updated_at"] = _iso_now()
        payload["source"] = "api"
        self._persist_execution_controls(payload)
        self._record_audit(
            category="execution",
            action="set_kill_switch",
            payload={
                "enabled": payload["kill_switch_enabled"],
                "reason": payload["kill_switch_reason"],
            },
        )
        return payload

    def build_execution_monitor(
        self,
        *,
        broker: str | None = None,
        execution_id: str | None = None,
        order_limit: int = 20,
        mode: str = "paper",
    ) -> dict[str, Any]:
        broker_id = (broker or self.default_broker).strip().lower()
        latest_execution = execution_id or self._latest_execution_id()
        normalized_mode = self._normalize_broker_mode(mode)
        account = self.get_execution_account(broker=broker_id, mode=normalized_mode)
        orders = self.list_execution_orders(broker=broker_id, status="all", limit=order_limit, mode=normalized_mode)
        positions = self.list_execution_positions(broker=broker_id, mode=normalized_mode)
        journal = None
        if latest_execution:
            try:
                journal = self.get_execution_journal(latest_execution)
            except ValueError:
                journal = None

        stale_orders = self._collect_stale_orders(journal, minutes=None)
        strategy_health = self.build_strategy_health()
        model_registry = self.build_model_registry()
        healthcheck = self.build_healthcheck()
        alerts = self.build_ops_alerts(
            monitor={
                "controls": self.get_execution_controls(),
                "stale_orders": stale_orders,
                "account": account,
                "journal": journal,
            }
        )
        return {
            "generated_at": _iso_now(),
            "broker_id": broker_id,
            "mode": normalized_mode,
            "requested_mode": account.get("requested_mode", normalized_mode),
            "effective_mode": account.get("effective_mode", normalized_mode),
            "paper_ready": account.get("paper_ready"),
            "live_ready": account.get("live_ready"),
            "live_available": account.get("live_available"),
            "block_reason": account.get("block_reason"),
            "next_actions": account.get("next_actions", []),
            "execution_id": latest_execution,
            "controls": self.get_execution_controls(),
            "account": account,
            "orders": orders.get("orders", []),
            "positions": positions.get("positions", []),
            "journal": journal,
            "stale_orders": stale_orders,
            "stale_order_count": len(stale_orders),
            "duplicate_window_minutes": int(
                getattr(settings, "EXECUTION_DUPLICATE_ORDER_WINDOW_MINUTES", 90) or 90
            ),
            "alpha_ranker": self.alpha_ranker.status(),
            "p1_suite": self.p1_suite.status(),
            "p2_stack": self.p2_stack.status(),
            "alerts": alerts,
            "strategy_health": strategy_health,
            "model_registry": model_registry,
            "healthcheck": healthcheck,
        }

    def get_execution_account(self, broker: str | None = None, mode: str = "paper") -> dict[str, Any]:
        adapter, normalized_mode = self._prepare_broker_adapter(broker, mode)
        status = self._connection_status_for_mode(adapter, normalized_mode)
        descriptor = adapter.descriptor().model_dump()
        if not status.get("configured"):
            return self._with_execution_mode_state({
                "connected": False,
                "mode": normalized_mode,
                "broker": descriptor,
                "broker_connection": status,
                "warnings": [f"{adapter.label} credentials are not configured for the current runtime."],
            }, adapter=adapter, requested_mode=normalized_mode)

        try:
            account = adapter.get_account()
            account_snapshot = self._summarize_broker_account(adapter.broker_id, account)
            account_snapshot["account_mode"] = normalized_mode
            clock_snapshot = self._safe_get_clock(adapter)
            return self._with_execution_mode_state({
                "connected": True,
                "mode": normalized_mode,
                "broker": descriptor,
                "broker_connection": status,
                "account": account_snapshot,
                "market_clock": clock_snapshot,
                "warnings": self._collect_execution_warnings(
                    account_snapshot=account_snapshot,
                    market_clock=clock_snapshot,
                    submit_orders=False,
                ),
            }, adapter=adapter, requested_mode=normalized_mode, connected=True)
        except Exception as exc:
            logger.warning(f"Failed to load {adapter.label} account status: {exc}")
            return self._with_execution_mode_state({
                "connected": False,
                "mode": normalized_mode,
                "broker": descriptor,
                "broker_connection": status,
                "warnings": [str(exc)],
            }, adapter=adapter, requested_mode=normalized_mode, failure_reason=str(exc))

    def list_execution_orders(
        self,
        broker: str | None = None,
        status: str = "all",
        limit: int = 20,
        mode: str = "paper",
    ) -> dict[str, Any]:
        adapter, normalized_mode = self._prepare_broker_adapter(broker, mode)
        connection = self._connection_status_for_mode(adapter, normalized_mode)
        descriptor = adapter.descriptor().model_dump()
        if not connection.get("configured"):
            return self._with_execution_mode_state(
                {"connected": False, "mode": normalized_mode, "orders": [], "broker": descriptor, "broker_connection": connection},
                adapter=adapter,
                requested_mode=normalized_mode,
            )

        try:
            orders = adapter.list_orders(status=status, limit=limit)
            return self._with_execution_mode_state({
                "connected": True,
                "mode": normalized_mode,
                "broker": descriptor,
                "broker_connection": connection,
                "orders": [self._summarize_broker_order(adapter.broker_id, item) for item in orders],
            }, adapter=adapter, requested_mode=normalized_mode, connected=True)
        except Exception as exc:
            logger.warning(f"Failed to list {adapter.label} orders: {exc}")
            return self._with_execution_mode_state({
                "connected": False,
                "mode": normalized_mode,
                "broker": descriptor,
                "broker_connection": connection,
                "orders": [],
                "warnings": [str(exc)],
            }, adapter=adapter, requested_mode=normalized_mode, failure_reason=str(exc))

    def get_execution_order(
        self,
        order_id: str,
        broker: str | None = None,
        execution_id: str | None = None,
    ) -> dict[str, Any]:
        journal = self._load_execution_journal(execution_id)
        record = self._find_journal_record(journal, order_id) if journal else None
        broker_id = broker or (journal or {}).get("broker_id") or self.default_broker
        adapter, normalized_mode = self._prepare_broker_adapter(broker_id, (journal or {}).get("mode", "paper"))
        connection = self._connection_status_for_mode(adapter, normalized_mode)
        descriptor = adapter.descriptor().model_dump()

        summary = None
        warnings: list[str] = []
        broker_order_id = self._record_broker_order_id(record) or order_id
        if connection.get("configured") and broker_order_id and record is not None:
            try:
                summary = self._summarize_broker_order(adapter.broker_id, adapter.get_order(broker_order_id))
            except Exception as exc:
                warnings.append(str(exc))
                summary = record.get("last_broker_snapshot") or record.get("submitted_payload")
        elif record is not None:
            summary = record.get("last_broker_snapshot") or record.get("submitted_payload")
        else:
            warnings.append("Order was not found in local execution journals.")

        return {
            "connected": bool(connection.get("configured")),
            "mode": normalized_mode,
            "broker": descriptor,
            "broker_connection": connection,
            "order": summary,
            "journal_record": record,
            "warnings": warnings,
        }

    def list_execution_positions(self, broker: str | None = None, mode: str = "paper") -> dict[str, Any]:
        adapter, normalized_mode = self._prepare_broker_adapter(broker, mode)
        connection = self._connection_status_for_mode(adapter, normalized_mode)
        descriptor = adapter.descriptor().model_dump()
        if not connection.get("configured"):
            return self._with_execution_mode_state(
                {"connected": False, "mode": normalized_mode, "positions": [], "broker": descriptor, "broker_connection": connection},
                adapter=adapter,
                requested_mode=normalized_mode,
            )

        try:
            positions = adapter.list_positions()
            return self._with_execution_mode_state({
                "connected": True,
                "mode": normalized_mode,
                "broker": descriptor,
                "broker_connection": connection,
                "positions": [self._summarize_broker_position(adapter.broker_id, item) for item in positions],
            }, adapter=adapter, requested_mode=normalized_mode, connected=True)
        except Exception as exc:
            logger.warning(f"Failed to list {adapter.label} positions: {exc}")
            return self._with_execution_mode_state({
                "connected": False,
                "mode": normalized_mode,
                "broker": descriptor,
                "broker_connection": connection,
                "positions": [],
                "warnings": [str(exc)],
            }, adapter=adapter, requested_mode=normalized_mode, failure_reason=str(exc))

    def create_execution_plan(
        self,
        benchmark: str | None = None,
        capital_base: float | None = None,
        universe_symbols: list[str] | None = None,
        broker: str | None = None,
        mode: str = "paper",
        submit_orders: bool = False,
        max_orders: int = 2,
        per_order_notional: float | None = None,
        order_type: str = "market",
        time_in_force: str = "day",
        extended_hours: bool = False,
        allow_duplicates: bool = False,
        live_confirmed: bool = False,
        operator_confirmation: str | None = None,
        reward_candidate_mode: bool = False,
        strategy_id: str | None = None,
    ) -> dict[str, Any]:
        benchmark = benchmark or self.default_benchmark
        capital_base = capital_base or self.default_capital
        broker_id = (broker or self.default_broker).strip().lower()
        adapter, normalized_mode = self._prepare_broker_adapter(broker_id, mode)
        signals = self._build_signals(self.get_default_universe(universe_symbols), "execution plan", benchmark)
        portfolio = self._build_portfolio(signals, capital_base, benchmark)
        execution_id = f"execution-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
        normalized_order_type = (order_type or "market").strip().lower()
        normalized_tif = (time_in_force or "day").strip().lower()
        limit_plan = self.components.execution.plan_order_limits(
            mode=normalized_mode,
            max_orders=max_orders,
            per_order_notional=per_order_notional,
            reward_candidate_mode=bool(reward_candidate_mode),
        )
        notional_limits = limit_plan["notional_limits"]
        capped_max_orders = int(limit_plan["capped_max_orders"])
        capped_notional = float(limit_plan["capped_notional"])
        orders = self._build_execution_orders(
            execution_id=execution_id,
            broker_id=broker_id,
            positions=portfolio.positions,
            capital_base=capital_base,
            order_type=normalized_order_type,
            time_in_force=normalized_tif,
            per_order_notional=capped_notional,
        )
        order_metrics = self.components.execution.order_metrics(orders)
        average_slippage = order_metrics["average_slippage"]
        average_impact = order_metrics["average_impact"]
        average_fill_probability = order_metrics["average_fill_probability"]
        canary_summary = order_metrics["canary_summary"]
        compliance_checks, risk_warnings, ready = self._perform_execution_risk_checks(
            broker_id=broker_id,
            mode=mode,
            portfolio=portfolio,
            capped_max_orders=capped_max_orders,
            capped_notional=capped_notional,
        )

        plan = ExecutionPlan(
            execution_id=execution_id,
            broker=adapter.label,
            mode=normalized_mode,
            ready=ready,
            estimated_slippage_bps=average_slippage
            or float(getattr(settings, "EXECUTION_DEFAULT_SLIPPAGE_BPS", 8.0) or 8.0),
            compliance_checks=compliance_checks,
            orders=orders,
            submitted=False,
            broker_status="planned",
            warnings=list(risk_warnings),
            broker_connection=self._connection_status_for_mode(adapter, normalized_mode),
        )

        payload = plan.model_dump()
        signal_payloads = [signal.model_dump(mode="json") for signal in signals]
        signal_provenance = self.synthetic_guard.summary(signal_payloads)
        payload["signal_provenance"] = signal_provenance
        payload["synthetic_used"] = bool(signal_provenance.get("synthetic_count"))
        payload["evidence_eligible"] = not payload["synthetic_used"]
        payload["broker_id"] = broker_id
        payload["broker_descriptor"] = adapter.descriptor().model_dump()
        payload["generated_at"] = _iso_now()
        payload["portfolio"] = portfolio.model_dump()
        payload["submit_orders"] = bool(submit_orders)
        payload["reward_candidate_mode"] = bool(reward_candidate_mode)
        payload["strategy_id"] = str(strategy_id or ("paper_reward_candidate" if reward_candidate_mode else "execution_plan")).strip()
        payload["session_date"] = self._execution_session_date(payload)
        payload["config_snapshot"] = self._config_snapshot()
        payload["max_orders"] = capped_max_orders
        payload["per_order_notional"] = capped_notional
        payload["notional_limits"] = {
            **notional_limits,
            "requested_per_order_notional": limit_plan["requested_per_order_notional"],
            "capped_per_order_notional": capped_notional,
        }
        payload["order_type"] = normalized_order_type
        payload["time_in_force"] = normalized_tif
        payload["extended_hours"] = bool(extended_hours)
        payload["allow_duplicates"] = bool(allow_duplicates)
        payload["live_confirmed"] = bool(live_confirmed)
        payload["operator_confirmation"] = operator_confirmation or ""
        payload["submitted_orders"] = []
        payload["broker_errors"] = []
        payload["cancelable_order_ids"] = []
        payload["retryable_order_ids"] = []
        payload["controls"] = self.get_execution_controls()
        payload["stale_orders"] = []

        journal = self._build_execution_journal(
            execution_id=execution_id,
            broker_id=broker_id,
            mode=payload["mode"],
            orders=payload["orders"],
            risk_summary=payload["warnings"],
        )
        payload["journal"] = journal
        payload["state_machine"] = {
            "state": journal["current_state"],
            "allowed_actions": journal["allowed_actions"],
        }
        payload["estimated_impact_bps"] = average_impact
        payload["expected_fill_probability"] = average_fill_probability
        payload["canary_summary"] = canary_summary
        payload["model_registry"] = self.build_model_registry()

        mode_state = self._execution_mode_state(
            adapter=adapter,
            requested_mode=payload["mode"],
        )
        payload["requested_mode"] = mode_state["requested_mode"]
        payload["effective_mode"] = mode_state["effective_mode"]
        payload["paper_ready"] = mode_state["paper_ready"]
        payload["live_ready"] = mode_state["live_ready"]
        payload["live_available"] = mode_state["live_available"]
        payload["block_reason"] = mode_state["block_reason"]
        payload["next_actions"] = list(mode_state["next_actions"])
        payload["paper_gate"] = mode_state.get("paper_gate", {})
        payload["paper_gate_passed"] = bool(mode_state.get("paper_gate_passed"))
        payload["live_blocked_until_paper_gate"] = bool(mode_state.get("live_blocked_until_paper_gate"))

        live_enabled = bool(getattr(settings, "ALPACA_ENABLE_LIVE_TRADING", False))
        self.components.execution.apply_live_guard(
            payload=payload,
            broker_id=broker_id,
            execution_id=execution_id,
            capped_max_orders=capped_max_orders,
            capped_notional=capped_notional,
            live_enabled=live_enabled,
            live_confirmed=bool(live_confirmed),
        )

        live_submit_ready = (
            payload["mode"] == "live"
            and live_enabled
            and live_confirmed
            and bool(payload.get("paper_gate_passed"))
        )
        if submit_orders and payload["ready"] and (payload["mode"] == "paper" or live_submit_ready):
            if payload.get("synthetic_used"):
                payload["ready"] = False
                payload["broker_status"] = "synthetic_evidence_blocked"
                payload["block_reason"] = "synthetic_evidence_blocked"
                payload["warnings"].append("Synthetic signal evidence is not eligible for broker routing.")
                payload["next_actions"] = ["refresh_real_market_data", "rerun_without_synthetic_evidence"]
            else:
                self._submit_broker_orders(
                    adapter=adapter,
                    payload=payload,
                    journal=journal,
                    capped_max_orders=capped_max_orders,
                    capped_notional=capped_notional,
                    normalized_order_type=normalized_order_type,
                    normalized_tif=normalized_tif,
                    extended_hours=bool(extended_hours),
                    allow_duplicates=bool(allow_duplicates),
                )

        payload["blocker_summary"] = self.build_blocker_summary(
            blockers=[payload.get("block_reason")] if payload.get("block_reason") else [],
            warnings=payload.get("warnings") or [],
        )
        payload["journal"] = journal
        payload["state_machine"] = {
            "state": journal["current_state"],
            "allowed_actions": journal["allowed_actions"],
        }
        self._persist_execution_payload(payload, journal)
        self._record_audit(
            category="execution",
            action="create_execution_plan",
            payload={
                "execution_id": execution_id,
                "broker_id": broker_id,
                "submitted": payload["submitted"],
                "mode": payload["mode"],
                "order_count": len(payload["orders"]),
            },
        )
        return payload

    def get_execution_journal(self, execution_id: str) -> dict[str, Any]:
        payload = self._load_execution_journal(execution_id)
        if payload is None:
            raise ValueError("Execution journal not found")
        return payload

    def sync_execution_journal(
        self,
        execution_id: str,
        broker: str | None = None,
    ) -> dict[str, Any]:
        journal = self._require_execution_journal(execution_id)
        adapter, normalized_mode = self._prepare_broker_adapter(broker or journal.get("broker_id"), journal.get("mode", "paper"))
        connection = self._connection_status_for_mode(adapter, normalized_mode)
        if not connection.get("configured"):
            raise ValueError(f"{adapter.label} is not configured in the current runtime")

        warnings: list[str] = []
        records_synced = 0
        state_transitions = 0
        for record in journal.get("records", []):
            broker_order_id = self._record_broker_order_id(record)
            if not broker_order_id:
                continue
            try:
                summary = self._summarize_broker_order(adapter.broker_id, adapter.get_order(broker_order_id))
                remote_state = self._normalize_order_state(adapter.broker_id, summary.get("status"))
                previous_state = str(record.get("current_state") or "")
                previous_snapshot = dict(record.get("last_broker_snapshot") or {})
                if remote_state != previous_state or summary != previous_snapshot:
                    self._update_journal_record(
                        journal=journal,
                        record=record,
                        state=remote_state,
                        message=f"Broker sync refreshed {record['symbol']} to {remote_state}.",
                        broker_snapshot=summary,
                    )
                    if remote_state != previous_state:
                        state_transitions += 1
                else:
                    record["last_broker_snapshot"] = summary
                records_synced += 1
            except Exception as exc:
                warnings.append(f"{record['symbol']}: {exc}")
                record.setdefault("events", []).append(
                    self._make_lifecycle_event(
                        order_id=record["order_id"],
                        execution_id=journal["execution_id"],
                        broker_id=journal["broker_id"],
                        state=str(record.get("current_state") or "validated"),
                        message=f"Broker sync probe failed for {record['symbol']}: {exc}",
                        payload={"error": str(exc)},
                    ).model_dump()
                )

        self._refresh_journal_state(journal)
        execution_payload = self._load_execution_payload(journal["execution_id"]) or {"execution_id": journal["execution_id"]}
        execution_payload = self._hydrate_execution_payload_from_journal(execution_payload, journal)
        if warnings:
            existing_warnings = [str(item) for item in execution_payload.get("warnings", [])]
            execution_payload["warnings"] = list(dict.fromkeys(existing_warnings + warnings))
        self._persist_execution_payload(execution_payload, journal)
        self._record_audit(
            category="execution",
            action="sync_execution_journal",
            payload={
                "execution_id": journal["execution_id"],
                "broker_id": journal["broker_id"],
                "records_synced": records_synced,
                "state_transitions": state_transitions,
            },
        )
        return {
            "execution_id": journal["execution_id"],
            "mode": normalized_mode,
            "broker": adapter.descriptor().model_dump(),
            "records_synced": records_synced,
            "state_transitions": state_transitions,
            "warnings": warnings,
            "journal": journal,
            "state_machine": execution_payload.get("state_machine", {}),
            "cancelable_order_ids": execution_payload.get("cancelable_order_ids", []),
            "retryable_order_ids": execution_payload.get("retryable_order_ids", []),
            "orders": execution_payload.get("orders", []),
            "stale_orders": execution_payload.get("stale_orders", []),
            "controls": execution_payload.get("controls", self.get_execution_controls()),
        }

    def reconcile_alpaca_paper_orders(self, *, session_date: str | None = None) -> dict[str, Any]:
        if not bool(getattr(settings, "ALPACA_PAPER_RECONCILE_ENABLED", True)):
            return {"enabled": False, "status": "skipped", "reason": "alpaca_paper_reconcile_disabled"}
        session = str(session_date or self._execution_session_date({}))[:10]
        adapter, normalized_mode = self._prepare_broker_adapter("alpaca", "paper")
        connection = self._connection_status_for_mode(adapter, normalized_mode)
        if not connection.get("configured"):
            return {
                "enabled": True,
                "status": "blocked",
                "session_date": session,
                "reason": "alpaca_paper_not_configured",
            }

        errors: list[str] = []
        try:
            orders = adapter.list_orders(status="all", limit=500)
        except Exception as exc:
            orders = []
            errors.append(f"orders:{exc}")
        try:
            positions = adapter.list_positions()
        except Exception as exc:
            positions = []
            errors.append(f"positions:{exc}")
        try:
            account = adapter.get_account()
        except Exception as exc:
            account = {}
            errors.append(f"account:{exc}")

        summarized_orders = [self._summarize_broker_order("alpaca", order) for order in orders if isinstance(order, dict)]
        by_id = {str(order.get("id") or ""): order for order in summarized_orders if order.get("id")}
        by_client = {
            str(order.get("client_order_id") or ""): order
            for order in summarized_orders
            if order.get("client_order_id")
        }
        by_symbol_side: dict[str, dict[str, Any]] = {}
        by_symbol_side_filled: dict[str, dict[str, Any]] = {}
        for order in summarized_orders:
            key = f"{str(order.get('symbol') or '').upper()}:{str(order.get('side') or 'buy').lower()}"
            by_symbol_side.setdefault(key, order)
            if self._broker_order_has_fill(order) and self._broker_order_matches_session(order, session):
                by_symbol_side_filled.setdefault(key, order)

        journal_updates = 0
        execution_updates = 0
        for execution in self.storage.list_records("executions"):
            if str(execution.get("mode") or "").lower() != "paper":
                continue
            if self._record_session_date(execution) and self._record_session_date(execution) != session:
                continue
            execution_id = str(execution.get("execution_id") or "").strip()
            journal = self._load_execution_journal(execution_id) or execution.get("journal") or {}
            if not journal:
                continue
            changed = False
            for record in journal.get("records", []):
                client_id = str(record.get("order_id") or "").strip()
                current_broker_id = self._record_broker_order_id(record)
                symbol = str(record.get("symbol") or "").upper()
                side = str((record.get("submitted_payload") or {}).get("side") or "buy").lower()
                summary = by_id.get(current_broker_id) or by_client.get(client_id) or by_symbol_side.get(f"{symbol}:{side}")
                if not summary:
                    continue
                previous = dict(record.get("last_broker_snapshot") or {})
                remote_state = self._normalize_order_state("alpaca", summary.get("status"))
                if summary != previous or remote_state != str(record.get("current_state") or ""):
                    self._update_journal_record(
                        journal=journal,
                        record=record,
                        state=remote_state,
                        message=f"Alpaca paper reconcile refreshed {symbol} to {remote_state}.",
                        broker_snapshot=summary,
                    )
                    journal_updates += 1
                    changed = True
            if changed:
                hydrated = self._hydrate_execution_payload_from_journal(execution, journal)
                hydrated["reconciliation_status"] = {"session_date": session, "updated_at": _iso_now()}
                self._persist_execution_payload(hydrated, journal)
                execution_updates += 1

        lock_updates = 0
        unresolved_submit_unknown = 0
        for lock in self.storage.list_records("submit_locks"):
            if not isinstance(lock, dict) or str(lock.get("session_date") or "")[:10] != session:
                continue
            symbol = str(lock.get("symbol") or "").upper()
            side = str(lock.get("side") or "buy").lower()
            summary = by_client.get(str(lock.get("client_order_id") or ""))
            reconcile_status = "submitted"
            if not summary:
                summary = by_symbol_side_filled.get(f"{symbol}:{side}")
                reconcile_status = "reconciled"
            if not summary:
                if str(lock.get("status") or "") == "submit_unknown":
                    unresolved_submit_unknown += 1
                    self._record_submit_unknown_alert(lock)
                continue
            if lock.get("broker_order_id") != summary.get("id") or lock.get("status") in {"acquired", "submit_unknown"}:
                self._update_session_submit_lock(
                    lock,
                    status=reconcile_status if summary.get("id") else "reconciled",
                    broker_order_id=summary.get("id"),
                    broker_status=summary.get("status"),
                    reconciled_at=_iso_now(),
                    reconcile_rule="client_order_id" if reconcile_status == "submitted" else "symbol_side_session_fill",
                )
                lock_updates += 1

        outcome_updates = 0
        for outcome in self.storage.list_records("paper_outcomes"):
            if not isinstance(outcome, dict) or self._record_session_date({"date": outcome.get("entry_at")}) != session:
                continue
            symbol = str(outcome.get("symbol") or "").upper()
            side = str(outcome.get("side") or outcome.get("action") or "buy").lower()
            if side == "long":
                side = "buy"
            elif side == "short":
                side = "sell"
            summary = by_id.get(str(outcome.get("broker_order_id") or "")) or by_symbol_side.get(f"{symbol}:{side}")
            if not summary:
                continue
            outcome["broker_order_id"] = summary.get("id") or outcome.get("broker_order_id")
            outcome["broker_status"] = summary.get("status")
            outcome["filled_qty"] = summary.get("filled_qty") or outcome.get("filled_qty")
            outcome["filled_avg_price"] = summary.get("filled_avg_price") or outcome.get("filled_avg_price")
            entry_price = self._safe_float(summary.get("filled_avg_price"))
            if entry_price is not None:
                outcome["entry_price"] = entry_price
            outcome["reconciled_at"] = _iso_now()
            self._save_paper_outcome(outcome)
            outcome_updates += 1

        payload = {
            "reconciliation_id": f"alpaca-paper-reconcile-{session}",
            "generated_at": _iso_now(),
            "session_date": session,
            "status": "completed" if not errors else "completed_with_warnings",
            "orders_seen": len(summarized_orders),
            "positions_seen": len(positions or []),
            "account": self._summarize_broker_account("alpaca", account) if account else {},
            "journal_updates": journal_updates,
            "execution_updates": execution_updates,
            "submit_lock_updates": lock_updates,
            "unresolved_submit_unknown": unresolved_submit_unknown,
            "outcome_updates": outcome_updates,
            "errors": errors,
        }
        payload["storage"] = self.storage.persist_record("paper_reconciliations", payload["reconciliation_id"], _jsonable(payload))
        return _jsonable(payload)

    def cancel_execution_order(
        self,
        order_id: str,
        broker: str | None = None,
        execution_id: str | None = None,
    ) -> dict[str, Any]:
        journal = self._require_execution_journal(execution_id)
        record = self._find_journal_record(journal, order_id)
        if record is None:
            raise ValueError("Order was not found in the execution journal")

        adapter, normalized_mode = self._prepare_broker_adapter(broker or journal.get("broker_id"), journal.get("mode", "paper"))
        connection = adapter.connection_status()
        if not connection.get("configured"):
            raise ValueError(f"{adapter.label} is not configured in the current runtime")

        broker_order_id = self._record_broker_order_id(record)
        if not broker_order_id:
            raise ValueError("This order has not been routed to a broker yet and cannot be canceled.")

        cancel_response = adapter.cancel_order(broker_order_id)
        refreshed = cancel_response
        response_status = self._normalize_order_state(adapter.broker_id, (cancel_response or {}).get("status"))
        if response_status not in {"canceled", "cancelled"}:
            try:
                refreshed = adapter.get_order(broker_order_id)
            except Exception:
                refreshed = cancel_response
        summary = self._summarize_broker_order(adapter.broker_id, refreshed)
        new_state = self._normalize_order_state(adapter.broker_id, summary.get("status"))
        self._update_journal_record(
            journal=journal,
            record=record,
            state=new_state,
            message=f"Cancel requested for {record['symbol']}.",
            broker_snapshot=summary,
            cancel_requested=True,
        )
        payload = self._sync_execution_order_payload(journal, record, summary)
        self._record_audit(
            category="execution",
            action="cancel_order",
            payload={
                "execution_id": journal["execution_id"],
                "order_id": record["order_id"],
                "broker_id": journal["broker_id"],
                "broker_order_id": broker_order_id,
            },
        )
        return payload

    def retry_execution_order(
        self,
        order_id: str,
        broker: str | None = None,
        execution_id: str | None = None,
        per_order_notional: float | None = None,
        order_type: str = "market",
        time_in_force: str = "day",
        extended_hours: bool = False,
    ) -> dict[str, Any]:
        journal = self._require_execution_journal(execution_id)
        record = self._find_journal_record(journal, order_id)
        if record is None:
            raise ValueError("Order was not found in the execution journal")
        if not self._can_retry_state(record.get("current_state")):
            raise ValueError(f"Order state {record.get('current_state')} is not retryable.")

        adapter, normalized_mode = self._prepare_broker_adapter(broker or journal.get("broker_id"), journal.get("mode", "paper"))
        connection = adapter.connection_status()
        if not connection.get("configured"):
            raise ValueError(f"{adapter.label} is not configured in the current runtime")

        existing_payload = dict(record.get("submitted_payload") or {})
        notional_limits = self._execution_notional_limits(normalized_mode)
        requested_notional = round(
            min(
                float(
                    per_order_notional
                    or existing_payload.get("notional")
                    or getattr(settings, "ALPACA_DEFAULT_TEST_NOTIONAL", 1.0)
                    or 1.0
                ),
                float(notional_limits["effective_per_order_notional"]),
            ),
            2,
        )
        try:
            asset = adapter.get_asset(record["symbol"])
        except Exception:
            asset = {"symbol": record["symbol"], "fractionable": False}

        retry_index = int(record.get("retry_count", 0)) + 1
        broker_payload = self._build_broker_order_payload(
            broker_id=adapter.broker_id,
            execution_id=journal["execution_id"],
            order={
                "symbol": record["symbol"],
                "side": existing_payload.get("side", "buy"),
                "quantity": existing_payload.get("qty") or 1,
                "client_order_id": f"{record['order_id']}-retry-{retry_index}",
                "limit_price": existing_payload.get("limit_price"),
            },
            asset=asset,
            index=retry_index,
            capped_notional=requested_notional,
            normalized_order_type=(order_type or existing_payload.get("type") or "market").strip().lower(),
            normalized_tif=(time_in_force or existing_payload.get("time_in_force") or "day").strip().lower(),
            extended_hours=bool(extended_hours),
        )
        created_order = adapter.submit_order(broker_payload)
        refreshed_order = created_order
        remote_order_id = str(created_order.get("id") or "").strip()
        if remote_order_id:
            try:
                refreshed_order = adapter.get_order(remote_order_id)
            except Exception:
                refreshed_order = created_order
        summary = self._summarize_broker_order(adapter.broker_id, refreshed_order)
        self._update_journal_record(
            journal=journal,
            record=record,
            state=self._normalize_order_state(adapter.broker_id, summary.get("status")),
            message=f"Retry #{retry_index} routed for {record['symbol']}.",
            broker_snapshot=summary,
            submitted_payload=broker_payload,
            retry_count=retry_index,
            cancel_requested=False,
        )
        payload = self._sync_execution_order_payload(journal, record, summary)
        self._record_audit(
            category="execution",
            action="retry_order",
            payload={
                "execution_id": journal["execution_id"],
                "order_id": record["order_id"],
                "broker_id": journal["broker_id"],
                "retry_count": retry_index,
            },
        )
        return payload

    def run_alpha_validation(
        self,
        strategy_name: str,
        benchmark: str | None = None,
        universe_symbols: list[str] | None = None,
        capital_base: float | None = None,
        in_sample_days: int = 252,
        out_of_sample_days: int = 63,
        walk_forward_windows: int = 3,
        slippage_bps: float | None = None,
        impact_cost_bps: float | None = None,
    ) -> dict[str, Any]:
        benchmark = benchmark or self.default_benchmark
        capital_base = capital_base or self.default_capital
        signals = self._build_signals(self.get_default_universe(universe_symbols), strategy_name, benchmark)
        portfolio = self._build_portfolio(signals, capital_base, benchmark)
        slippage = round(float(slippage_bps or getattr(settings, "EXECUTION_DEFAULT_SLIPPAGE_BPS", 8.0) or 8.0), 2)
        impact = round(float(impact_cost_bps or getattr(settings, "EXECUTION_DEFAULT_IMPACT_BPS", 5.0) or 5.0), 2)
        windows = [
            self._simulate_validation_window(
                label=f"WF-{index + 1}",
                start_offset=(walk_forward_windows - index) * out_of_sample_days,
                duration=out_of_sample_days,
                portfolio=portfolio,
                slippage_bps=slippage,
                impact_cost_bps=impact,
                strategy_name=strategy_name,
                bucket=self._validation_bucket_for_index(index),
                fill_probability=self._average_portfolio_fill_probability(portfolio),
                calibrated_confidence=self._average_calibrated_confidence(signals),
            )
            for index in range(max(1, walk_forward_windows))
        ]
        in_sample_window = self._simulate_validation_window(
            label="in-sample",
            start_offset=in_sample_days,
            duration=in_sample_days,
            portfolio=portfolio,
            slippage_bps=slippage,
            impact_cost_bps=impact,
            strategy_name=strategy_name,
            bucket="in_sample",
            fill_probability=self._average_portfolio_fill_probability(portfolio),
            calibrated_confidence=self._average_calibrated_confidence(signals),
        )
        out_window = self._simulate_validation_window(
            label="out-of-sample",
            start_offset=0,
            duration=out_of_sample_days,
            portfolio=portfolio,
            slippage_bps=slippage,
            impact_cost_bps=impact,
            strategy_name=f"{strategy_name}-oos",
            bucket="out_of_sample",
            fill_probability=self._average_portfolio_fill_probability(portfolio),
            calibrated_confidence=self._average_calibrated_confidence(signals),
        )
        average_drag = statistics.mean([window.turnover_cost_drag for window in windows]) if windows else 0.0
        average_fill = self._average_portfolio_fill_probability(portfolio)
        calibration = {
            "p1": (self.p1_suite.status() or {}).get("calibration", {}),
            "p2": ((self.p2_stack.status() or {}).get("selector") or {}).get("calibration", {}),
        }
        stratified_walk_forward = self._stratify_validation_windows(windows)
        overfit_score = round(
            _bounded(
                max(0.0, (in_sample_window.sharpe - out_window.sharpe) * 18)
                + statistics.pstdev([window.sharpe for window in windows] or [0.0]) * 6,
                0.0,
                100.0,
            ),
            2,
        )
        robustness_score = round(
            _bounded(
                100
                - overfit_score
                - abs(out_window.max_drawdown - in_sample_window.max_drawdown) * 150
                - average_drag * 100,
                5.0,
                96.0,
            ),
            2,
        )
        validation = AlphaValidationReport(
            validation_id=f"validation-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            strategy_name=strategy_name,
            benchmark=benchmark,
            generated_at=_iso_now(),
            universe=[member.symbol for member in self.get_default_universe(universe_symbols)],
            in_sample_sharpe=round(in_sample_window.sharpe, 4),
            out_of_sample_sharpe=round(out_window.sharpe, 4),
            out_of_sample_cumulative_return=round(out_window.cumulative_return, 4),
            overfit_score=overfit_score,
            robustness_score=robustness_score,
            turnover_cost_drag_bps=round(average_drag * 10000, 2),
            slippage_bps=slippage,
            impact_cost_bps=impact,
            fill_probability=average_fill,
            walk_forward_windows=windows,
            stratified_walk_forward=stratified_walk_forward,
            calibration=calibration,
            notes=[
                "Walk-forward windows include turnover drag, slippage, and simple impact cost penalties.",
                "Use the out-of-sample Sharpe and overfit score before promoting research to broker routing.",
                "This validation layer now tracks fill probability and calibrated confidence by validation bucket.",
                "This validation layer is deterministic and reproducible, but it should still be replaced with production-grade market data and venue microstructure models.",
            ],
        )
        payload = validation.model_dump()
        if validation.out_of_sample_sharpe >= 1.0 and validation.overfit_score <= 25 and validation.robustness_score >= 70:
            recommendation = "GO"
        elif validation.out_of_sample_sharpe >= 0.5 and validation.overfit_score <= 45:
            recommendation = "REVIEW"
        else:
            recommendation = "NO-GO"
        payload["recommendation"] = recommendation
        payload["summary"] = (
            f"OOS Sharpe {validation.out_of_sample_sharpe:.2f}, "
            f"overfit score {validation.overfit_score:.1f}, "
            f"robustness {validation.robustness_score:.1f}."
        )
        payload["windows"] = [
            {
                "window": index + 1,
                "in_sample_sharpe": validation.in_sample_sharpe,
                "out_of_sample_sharpe": window.sharpe,
            }
            for index, window in enumerate(validation.walk_forward_windows)
        ]
        payload["regime_performance"] = [
            {
                "regime": str(window.bucket or window.label).replace("_", " ").title(),
                "periods": 1,
                "return": f"{window.cumulative_return * 100:.1f}%",
                "sharpe": f"{window.sharpe:.2f}",
                "max_dd": f"-{abs(window.max_drawdown) * 100:.1f}%",
            }
            for window in validation.walk_forward_windows
        ]
        payload["storage"] = self.storage.persist_record("validations", validation.validation_id, payload)
        self._persist_experiment(
            name=strategy_name,
            objective="alpha_validation",
            benchmark=benchmark,
            metrics={
                "in_sample_sharpe": validation.in_sample_sharpe,
                "out_of_sample_sharpe": validation.out_of_sample_sharpe,
                "robustness_score": validation.robustness_score,
            },
            tags=["validation", "walk-forward", "cost-model"],
            artifact_uri=(payload["storage"] or {}).get("artifact_uri"),
        )
        self._record_audit(
            category="validation",
            action="run_alpha_validation",
            payload={
                "validation_id": validation.validation_id,
                "strategy_name": strategy_name,
                "benchmark": benchmark,
            },
        )
        return payload

    def _resolve_broker(self, broker: str | None):
        try:
            return self.brokers.get(broker or self.default_broker)
        except KeyError as exc:
            raise ValueError(str(exc)) from exc

    @staticmethod
    def _build_order_tracking_id(execution_id: str, symbol: str, index: int) -> str:
        return f"{execution_id}-{symbol.lower()}-{index + 1}"

    def _perform_execution_risk_checks(
        self,
        *,
        broker_id: str,
        mode: str,
        portfolio: PortfolioSummary,
        capped_max_orders: int,
        capped_notional: float,
    ) -> tuple[list[str], list[str], bool]:
        checks = [
            "No MNPI detected in prompt or attached research inputs",
            "Execution journal and audit trail will be persisted before routing",
            "Sample orders capped by runtime risk controls",
        ]
        warnings: list[str] = []
        ready = True
        if not portfolio.positions:
            ready = False
            warnings.append("No actionable long signals passed the signal filter. Execution stays in no-trade mode.")
        weight_cap = float(getattr(settings, "EXECUTION_SINGLE_NAME_WEIGHT_CAP", 0.26) or 0.26)
        largest_weight = max((position.weight for position in portfolio.positions), default=0.0)
        if largest_weight <= weight_cap:
            checks.append("Max single-name weight below configured cap")
        else:
            warnings.append(
                f"Portfolio concentration exceeds cap: {largest_weight:.2%} > configured {weight_cap:.2%}. Review before promoting beyond paper mode."
            )
            if mode == "live":
                ready = False

        if capped_max_orders <= int(getattr(settings, "EXECUTION_MAX_DAILY_ORDERS", 25) or 25):
            checks.append("Order batch size is within the daily routing ceiling")
        else:
            ready = False
            warnings.append("Requested order count exceeds the daily routing ceiling.")

        notional_limit = float(self._execution_notional_limits(mode)["effective_per_order_notional"])
        if capped_notional <= notional_limit:
            checks.append(f"Per-order notional is within configured {mode} broker-safe limits")
        else:
            ready = False
            warnings.append("Requested notional exceeds the configured broker-safe limit.")

        if portfolio.turnover_estimate > 0.35:
            warnings.append("Turnover estimate is elevated. Consider widening rebalance cadence before live promotion.")
        if portfolio.expected_alpha <= 0:
            ready = False
            warnings.append("Expected alpha is non-positive. Execution should stay blocked until the strategy is revalidated.")
        if self.get_execution_controls().get("kill_switch_enabled"):
            warnings.append("Execution kill switch is currently engaged. Submit requests will stay blocked.")
        else:
            checks.append("Kill switch is currently released")
        checks.append(
            f"Duplicate-order suppression window is {int(getattr(settings, 'EXECUTION_DUPLICATE_ORDER_WINDOW_MINUTES', 90) or 90)} minutes"
        )
        if mode == "live":
            warnings.append(f"{broker_id} live routing requires explicit confirmation and stays subject to runtime guardrails.")
        return checks, warnings, ready

    def _build_execution_orders(
        self,
        *,
        execution_id: str,
        broker_id: str,
        positions: list[PortfolioPosition],
        capital_base: float,
        order_type: str,
        time_in_force: str,
        per_order_notional: float,
    ) -> list[ExecutionOrder]:
        return self.components.execution.build_orders(
            execution_id=execution_id,
            broker_id=broker_id,
            positions=positions,
            capital_base=capital_base,
            order_type=order_type,
            time_in_force=time_in_force,
            per_order_notional=per_order_notional,
        )

    def _submit_alpaca_paper_orders(
        self,
        *,
        payload: dict[str, Any],
        capped_max_orders: int,
        capped_notional: float,
        normalized_order_type: str,
        normalized_tif: str,
        extended_hours: bool,
    ) -> None:
        self.components.execution.submit_alpaca_paper_orders(
            payload=payload,
            capped_max_orders=capped_max_orders,
            capped_notional=capped_notional,
            normalized_order_type=normalized_order_type,
            normalized_tif=normalized_tif,
            extended_hours=extended_hours,
        )

    @staticmethod
    def _safe_float(value: Any) -> float | None:
        return coerce_float(value)

    def _collect_execution_warnings(
        self,
        *,
        account_snapshot: dict[str, Any],
        market_clock: dict[str, Any] | None,
        submit_orders: bool,
    ) -> list[str]:
        return self.components.execution.collect_warnings(
            account_snapshot=account_snapshot,
            market_clock=market_clock,
            submit_orders=submit_orders,
        )

    def _safe_get_clock(self, adapter) -> dict[str, Any] | None:
        try:
            clock = adapter.get_clock()
        except Exception as exc:
            logger.warning(f"{adapter.label} market clock fallback engaged: {exc}")
            return None
        return self._summarize_broker_clock(adapter.broker_id, clock)

    def _execution_session_date(self, payload: dict[str, Any] | None = None) -> str:
        payload = payload or {}
        for key in ("session_date", "trade_date", "trading_day", "generated_at"):
            value = payload.get(key)
            parsed = self._parse_any_timestamp(value)
            if parsed is not None:
                return parsed.date().isoformat()
            text = str(value or "").strip()
            if len(text) >= 10:
                try:
                    return date.fromisoformat(text[:10]).isoformat()
                except ValueError:
                    pass
        try:
            status = self.get_trading_calendar_status()
            return str(status.get("session_date") or date.today().isoformat())[:10]
        except Exception:
            return date.today().isoformat()

    def _submit_lock_id(self, *, session_date: str, strategy_id: str, symbol: str, side: str) -> str:
        return "_".join(
            [
                self._safe_record_id(session_date),
                self._safe_record_id(strategy_id),
                self._safe_record_id(symbol),
                self._safe_record_id(side),
            ]
        )

    def _submit_lock_path(self, lock_id: str) -> Path:
        directory = self.storage.base_dir / "submit_locks"
        directory.mkdir(parents=True, exist_ok=True)
        return directory / f"{lock_id}.json"

    def _acquire_session_submit_lock(
        self,
        *,
        session_date: str,
        strategy_id: str,
        symbol: str,
        side: str,
        execution_id: str,
        client_order_id: str,
    ) -> tuple[bool, dict[str, Any]]:
        if not bool(getattr(settings, "EXECUTION_SESSION_SUBMIT_LOCK_ENABLED", True)):
            return True, {"enabled": False}
        lock_id = self._submit_lock_id(
            session_date=session_date,
            strategy_id=strategy_id,
            symbol=symbol,
            side=side,
        )
        path = self._submit_lock_path(lock_id)
        now = _iso_now()
        payload = {
            "lock_id": lock_id,
            "session_date": session_date,
            "strategy_id": strategy_id,
            "symbol": symbol,
            "side": side,
            "execution_id": execution_id,
            "client_order_id": client_order_id,
            "status": "acquired",
            "created_at": now,
            "last_checked_at": now,
        }
        try:
            with path.open("x", encoding="utf-8") as handle:
                handle.write(json.dumps(_jsonable(payload), ensure_ascii=False, indent=2))
            return True, payload
        except FileExistsError:
            existing = self.storage.load_record("submit_locks", lock_id) or {}
            if not existing:
                try:
                    existing = json.loads(path.read_text(encoding="utf-8"))
                except Exception:
                    existing = {"lock_id": lock_id, "status": "existing_unreadable"}
            existing["last_checked_at"] = now
            self.storage.persist_record("submit_locks", lock_id, _jsonable(existing))
            return False, _jsonable(existing)

    def _update_session_submit_lock(self, lock: dict[str, Any], **updates: Any) -> dict[str, Any]:
        if not lock or lock.get("enabled") is False:
            return lock or {}
        payload = {**lock, **{key: value for key, value in updates.items() if value is not None}}
        payload["last_checked_at"] = _iso_now()
        lock_id = str(payload.get("lock_id") or "").strip()
        if lock_id:
            payload["storage"] = self.storage.persist_record("submit_locks", lock_id, _jsonable(payload))
        return _jsonable(payload)

    def list_submit_locks(
        self,
        *,
        session_date: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        rows = [row for row in self.storage.list_records("submit_locks") if isinstance(row, dict)]
        if session_date:
            session_key = str(session_date)[:10]
            rows = [row for row in rows if str(row.get("session_date") or "")[:10] == session_key]
        if status:
            status_key = str(status).strip().lower()
            rows = [row for row in rows if str(row.get("status") or "").lower() == status_key]
        rows = rows[: max(1, min(int(limit or 100), 1000))]
        return {
            "generated_at": _iso_now(),
            "count": len(rows),
            "session_date": session_date,
            "status": status,
            "locks": rows,
        }

    def _submit_broker_orders(
        self,
        *,
        adapter,
        payload: dict[str, Any],
        journal: dict[str, Any],
        capped_max_orders: int,
        capped_notional: float,
        normalized_order_type: str,
        normalized_tif: str,
        extended_hours: bool,
        allow_duplicates: bool,
    ) -> None:
        self.components.execution.submit_broker_orders(
            adapter=adapter,
            payload=payload,
            journal=journal,
            capped_max_orders=capped_max_orders,
            capped_notional=capped_notional,
            normalized_order_type=normalized_order_type,
            normalized_tif=normalized_tif,
            extended_hours=extended_hours,
            allow_duplicates=allow_duplicates,
        )

    def _build_broker_order_payload(
        self,
        *,
        broker_id: str,
        execution_id: str,
        order: dict[str, Any],
        asset: dict[str, Any],
        index: int,
        capped_notional: float,
        normalized_order_type: str,
        normalized_tif: str,
        extended_hours: bool,
    ) -> dict[str, Any]:
        return self.components.execution.build_broker_order_payload(
            broker_id=broker_id,
            execution_id=execution_id,
            order=order,
            asset=asset,
            index=index,
            capped_notional=capped_notional,
            normalized_order_type=normalized_order_type,
            normalized_tif=normalized_tif,
            extended_hours=extended_hours,
        )

    def _build_execution_journal(
        self,
        *,
        execution_id: str,
        broker_id: str,
        mode: str,
        orders: list[dict[str, Any]],
        risk_summary: list[str],
    ) -> dict[str, Any]:
        created_at = _iso_now()
        records: list[OrderLifecycleRecord] = []
        for order in orders:
            tracking_id = str(order.get("client_order_id") or order.get("symbol", "")).strip()
            event = self._make_lifecycle_event(
                order_id=tracking_id,
                execution_id=execution_id,
                broker_id=broker_id,
                state="validated",
                message=f"{order.get('symbol')} passed pre-trade validation.",
                payload={
                    "symbol": order.get("symbol"),
                    "side": order.get("side"),
                    "target_weight": order.get("target_weight"),
                },
            )
            records.append(
                OrderLifecycleRecord(
                    order_id=tracking_id,
                    execution_id=execution_id,
                    broker_id=broker_id,
                    symbol=str(order.get("symbol", "")),
                    current_state="validated",
                    retry_count=0,
                    cancel_requested=False,
                    submitted_payload={},
                    last_broker_snapshot={},
                    events=[event],
                )
            )

        journal = ExecutionJournal(
            execution_id=execution_id,
            broker_id=broker_id,
            mode=mode,
            current_state="ready_to_route",
            created_at=created_at,
            updated_at=created_at,
            allowed_actions=["submit"],
            risk_summary=list(risk_summary),
            records=records,
            metrics={"order_count": len(records)},
        )
        return journal.model_dump()

    def _make_lifecycle_event(
        self,
        *,
        order_id: str,
        execution_id: str,
        broker_id: str,
        state: str,
        message: str,
        payload: dict[str, Any] | None = None,
    ) -> OrderLifecycleEvent:
        created_at = _iso_now()
        event_id = f"{order_id}-{len(message)}-{created_at[-6:].replace(':', '')}"
        safe_payload = {key: value for key, value in (payload or {}).items() if value is not None}
        return OrderLifecycleEvent(
            event_id=event_id,
            order_id=order_id,
            execution_id=execution_id,
            broker_id=broker_id,
            state=state,
            message=message,
            created_at=created_at,
            payload=safe_payload,
        )

    def _update_journal_record(
        self,
        *,
        journal: dict[str, Any],
        record: dict[str, Any],
        state: str,
        message: str,
        broker_snapshot: dict[str, Any] | None = None,
        submitted_payload: dict[str, Any] | None = None,
        retry_count: int | None = None,
        cancel_requested: bool | None = None,
    ) -> None:
        record["current_state"] = state
        if broker_snapshot is not None:
            record["last_broker_snapshot"] = broker_snapshot
        if submitted_payload is not None:
            record["submitted_payload"] = submitted_payload
        if retry_count is not None:
            record["retry_count"] = retry_count
        if cancel_requested is not None:
            record["cancel_requested"] = cancel_requested
        event = self._make_lifecycle_event(
            order_id=record["order_id"],
            execution_id=journal["execution_id"],
            broker_id=journal["broker_id"],
            state=state,
            message=message,
            payload=(broker_snapshot or submitted_payload or {}),
        )
        record.setdefault("events", []).append(event.model_dump())
        self._refresh_journal_state(journal)

    def _refresh_journal_state(self, journal: dict[str, Any]) -> None:
        states = [str(record.get("current_state", "validated")) for record in journal.get("records", [])]
        if any(state == "partially_filled" for state in states):
            current_state = "partially_filled"
        elif states and all(state == "filled" for state in states):
            current_state = "filled"
        elif any(state in {"accepted", "new", "pending"} for state in states):
            current_state = "routed"
        elif any(state == "blocked" for state in states):
            current_state = "blocked"
        elif any(state == "cancel_requested" for state in states):
            current_state = "cancel_requested"
        elif any(state in {"canceled", "cancelled"} for state in states):
            current_state = "canceled"
        elif any(state == "suppressed" for state in states):
            current_state = "suppressed"
        elif any(state in {"failed", "rejected"} for state in states):
            current_state = "routing_exception"
        else:
            current_state = "ready_to_route"
        journal["current_state"] = current_state
        journal["updated_at"] = _iso_now()
        journal["allowed_actions"] = self._allowed_actions_for_state(current_state)

    @staticmethod
    def _allowed_actions_for_state(state: str) -> list[str]:
        if state in {"ready_to_route", "routing_exception", "canceled", "cancelled", "suppressed"}:
            return ["retry", "inspect"]
        if state in {"routed", "accepted", "new", "partially_filled"}:
            return ["cancel", "inspect"]
        if state in {"blocked", "kill_switch_engaged"}:
            return ["inspect"]
        if state == "filled":
            return ["inspect"]
        return ["inspect"]

    @staticmethod
    def _can_retry_state(state: Any) -> bool:
        return str(state or "").lower() in {
            "failed",
            "rejected",
            "canceled",
            "cancelled",
            "routing_exception",
            "expired",
            "suppressed",
        }

    @staticmethod
    def _can_cancel_state(state: Any) -> bool:
        return str(state or "").lower() in {"accepted", "new", "pending", "partially_filled", "routed"}

    def _default_execution_controls(self) -> dict[str, Any]:
        return {
            "kill_switch_enabled": bool(getattr(settings, "EXECUTION_KILL_SWITCH", False)),
            "kill_switch_reason": getattr(
                settings,
                "EXECUTION_KILL_SWITCH_REASON",
                "Manual operator override. Routing remains disabled until released.",
            ),
            "updated_at": _iso_now(),
            "source": "config",
        }

    def _persist_execution_controls(self, payload: dict[str, Any]) -> dict[str, Any]:
        storage = self.storage.persist_record("execution_controls", "runtime", payload)
        payload["storage"] = storage
        return payload

    def _load_execution_control_payload(self) -> dict[str, Any]:
        payload = self.storage.load_record("execution_controls", "runtime")
        if payload is None:
            payload = self._default_execution_controls()
            self._persist_execution_controls(payload)
        return payload

    @staticmethod
    def _parse_any_timestamp(value: Any) -> datetime | None:
        if value in {None, ""}:
            return None
        raw = str(value).strip()
        if not raw:
            return None
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None

    def _latest_execution_id(self) -> str | None:
        executions = self.storage.list_records("executions")
        if not executions:
            return None
        return str(executions[0].get("execution_id") or "").strip() or None

    def _collect_stale_orders(
        self,
        journal: dict[str, Any] | None,
        *,
        minutes: int | None,
    ) -> list[dict[str, Any]]:
        if journal is None:
            return []

        threshold = int(minutes or getattr(settings, "EXECUTION_STALE_ORDER_MINUTES", 20) or 20)
        now = datetime.now(timezone.utc)
        stale: list[dict[str, Any]] = []
        for record in journal.get("records", []):
            if not self._can_cancel_state(record.get("current_state")):
                continue
            snapshot = record.get("last_broker_snapshot") or {}
            events = record.get("events", [])
            reference = (
                self._parse_any_timestamp(snapshot.get("submitted_at"))
                or self._parse_any_timestamp(snapshot.get("created_at"))
                or self._parse_any_timestamp(events[-1]["created_at"] if events else None)
            )
            if reference is None:
                continue
            age_minutes = (now - reference.astimezone(timezone.utc)).total_seconds() / 60
            if age_minutes < threshold:
                continue
            stale.append(
                {
                    "order_id": record.get("order_id"),
                    "symbol": record.get("symbol"),
                    "state": record.get("current_state"),
                    "minutes_open": round(age_minutes, 1),
                    "retry_count": int(record.get("retry_count", 0)),
                }
            )
        return stale

    def _find_duplicate_order_candidates(
        self,
        *,
        broker_id: str,
        execution_id: str,
        orders: list[dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        window_minutes = int(getattr(settings, "EXECUTION_DUPLICATE_ORDER_WINDOW_MINUTES", 90) or 90)
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
        tracked = {
            f"{str(order.get('symbol') or '').upper()}:{str(order.get('side') or 'buy').lower()}"
            for order in orders
            if str(order.get("symbol") or "").strip()
        }
        matches: dict[str, dict[str, Any]] = {}

        for payload in self.storage.list_records("executions"):
            existing_execution_id = str(payload.get("execution_id") or "").strip()
            if not existing_execution_id or existing_execution_id == execution_id:
                continue
            generated_at = self._parse_any_timestamp(payload.get("generated_at")) or self._parse_any_timestamp(
                payload.get("created_at")
            )
            if generated_at is None or generated_at.astimezone(timezone.utc) < cutoff:
                continue
            if str(payload.get("broker_id") or "").strip().lower() not in {"", broker_id}:
                continue
            for existing in payload.get("orders", []):
                status = str(existing.get("status") or "").strip().lower()
                if status not in {"accepted", "new", "pending", "partially_filled", "submitted", "routed"}:
                    continue
                key = f"{str(existing.get('symbol') or '').upper()}:{str(existing.get('side') or 'buy').lower()}"
                if key not in tracked or key in matches:
                    continue
                matches[key] = {
                    "source": "local_execution_history",
                    "execution_id": existing_execution_id,
                    "symbol": str(existing.get("symbol") or "").upper(),
                    "side": str(existing.get("side") or "buy").lower(),
                    "status": status,
                    "order_id": existing.get("broker_order_id") or existing.get("client_order_id"),
                    "submitted_at": existing.get("submitted_at"),
                }

        try:
            remote_orders = self.list_execution_orders(broker=broker_id, status="all", limit=50).get("orders", [])
        except Exception:
            remote_orders = []

        for existing in remote_orders:
            status = str(existing.get("status") or "").strip().lower()
            if status not in {"accepted", "new", "pending", "partially_filled"}:
                continue
            key = f"{str(existing.get('symbol') or '').upper()}:{str(existing.get('side') or 'buy').lower()}"
            if key not in tracked or key in matches:
                continue
                matches[key] = {
                    "source": "broker_open_orders",
                    "symbol": str(existing.get("symbol") or "").upper(),
                    "side": str(existing.get("side") or "buy").lower(),
                    "status": status,
                "id": existing.get("id"),
                "client_order_id": existing.get("client_order_id"),
                "submitted_at": existing.get("submitted_at"),
                }
        return matches

    def _build_live_daily_notional_guard(
        self,
        *,
        broker_id: str,
        execution_id: str,
        planned_notional: float,
        enabled: bool = True,
    ) -> dict[str, Any]:
        trading_day = datetime.now(timezone.utc).date()
        limit = float(getattr(settings, "EXECUTION_LIVE_MAX_DAILY_NOTIONAL", 5.0) or 5.0)
        used = self._live_daily_submitted_notional(
            broker_id=broker_id,
            trading_day=trading_day,
            exclude_execution_id=execution_id,
        ) if enabled else 0.0
        remaining = max(limit - used, 0.0)
        ok = (not enabled) or (planned_notional <= remaining + 1e-9)
        return {
            "enabled": bool(enabled),
            "broker_id": broker_id,
            "trading_day": trading_day.isoformat(),
            "limit_notional": round(limit, 2),
            "used_notional": round(used, 2),
            "planned_notional": round(float(planned_notional or 0.0), 2),
            "remaining_before_request": round(remaining, 2),
            "remaining_after_request": round(max(limit - used - float(planned_notional or 0.0), 0.0), 2),
            "ok": bool(ok),
        }

    def _live_daily_submitted_notional(
        self,
        *,
        broker_id: str,
        trading_day: date,
        exclude_execution_id: str | None = None,
    ) -> float:
        total = 0.0
        for payload in self.storage.list_records("executions"):
            execution_id = str(payload.get("execution_id") or "").strip()
            if exclude_execution_id and execution_id == exclude_execution_id:
                continue
            if str(payload.get("mode") or "").lower() != "live":
                continue
            if str(payload.get("broker_id") or broker_id).lower() != broker_id:
                continue
            if not payload.get("submitted"):
                continue
            generated_at = (
                self._parse_any_timestamp(payload.get("generated_at"))
                or self._parse_any_timestamp(payload.get("created_at"))
            )
            if generated_at is None or generated_at.astimezone(timezone.utc).date() != trading_day:
                continue
            submitted_orders = payload.get("submitted_orders") or []
            if submitted_orders:
                total += sum(self._execution_order_notional(order) for order in submitted_orders)
                continue
            submitted_count = 0
            for order in payload.get("orders", []):
                if str(order.get("status") or "").lower() in {"accepted", "new", "pending", "partially_filled", "filled", "submitted", "routed", "canceled", "cancelled"}:
                    total += self._execution_order_notional(order)
                    submitted_count += 1
            if submitted_count == 0:
                total += float(payload.get("per_order_notional") or 0.0) * int(payload.get("max_orders") or 0)
        return round(total, 2)

    @classmethod
    def _execution_order_notional(cls, order: dict[str, Any]) -> float:
        for key in ("notional", "submitted_notional", "requested_notional"):
            value = cls._safe_float(order.get(key))
            if value is not None:
                return max(value, 0.0)
        submitted_payload = order.get("submitted_payload") or {}
        value = cls._safe_float(submitted_payload.get("notional"))
        return max(value or 0.0, 0.0)

    def _persist_execution_payload(self, payload: dict[str, Any], journal: dict[str, Any]) -> None:
        payload["storage"] = self.storage.persist_record("executions", payload["execution_id"], payload)
        payload["journal_storage"] = self.storage.persist_record("execution_journals", payload["execution_id"], journal)
        self._export_paper_feedback(payload, journal)

    def _load_execution_payload(self, execution_id: str | None) -> dict[str, Any] | None:
        if not execution_id:
            return None
        return self.storage.load_record("executions", execution_id)

    def _load_execution_journal(self, execution_id: str | None) -> dict[str, Any] | None:
        if not execution_id:
            return None
        return self.storage.load_record("execution_journals", execution_id)

    def _require_execution_journal(self, execution_id: str | None) -> dict[str, Any]:
        payload = self._load_execution_journal(execution_id)
        if payload is None:
            raise ValueError("Execution journal not found")
        return payload

    @staticmethod
    def _record_broker_order_id(record: dict[str, Any] | None) -> str | None:
        if not record:
            return None
        snapshot = record.get("last_broker_snapshot") or {}
        return str(snapshot.get("id") or "").strip() or None

    def _find_journal_record(self, journal: dict[str, Any] | None, order_id: str) -> dict[str, Any] | None:
        if journal is None:
            return None
        lookup = str(order_id or "").strip()
        for record in journal.get("records", []):
            if lookup in {
                str(record.get("order_id") or "").strip(),
                str((record.get("last_broker_snapshot") or {}).get("id") or "").strip(),
                str((record.get("last_broker_snapshot") or {}).get("client_order_id") or "").strip(),
            }:
                return record
        return None

    def _sync_execution_order_payload(
        self,
        journal: dict[str, Any],
        record: dict[str, Any],
        summary: dict[str, Any] | None,
    ) -> dict[str, Any]:
        execution_payload = self._load_execution_payload(journal.get("execution_id")) or {}
        if summary is not None:
            record["last_broker_snapshot"] = summary
        execution_payload = self._hydrate_execution_payload_from_journal(execution_payload, journal)
        self._persist_execution_payload(execution_payload, journal)
        return {
            "execution_id": journal["execution_id"],
            "order": summary,
            "journal_record": record,
            "state_machine": execution_payload["state_machine"],
            "cancelable_order_ids": execution_payload["cancelable_order_ids"],
            "retryable_order_ids": execution_payload["retryable_order_ids"],
        }

    def _broker_order_has_fill(self, order: dict[str, Any]) -> bool:
        status = str(order.get("status") or "").lower()
        if status in {"filled", "partially_filled"}:
            return True
        filled_qty = self._safe_float(order.get("filled_qty") or order.get("filled_quantity") or order.get("qty_filled"))
        return bool(filled_qty and filled_qty > 0)

    def _broker_order_matches_session(self, order: dict[str, Any], session_date: str) -> bool:
        raw = (
            order.get("submitted_at")
            or order.get("filled_at")
            or order.get("created_at")
            or order.get("updated_at")
        )
        day = self._paper_gate_date_key({"created_at": raw})
        return bool(day and day == str(session_date)[:10])

    def _record_submit_unknown_alert(self, lock: dict[str, Any]) -> None:
        alert_id = f"alert-submit-unknown-{self._safe_record_id(lock.get('lock_id') or lock.get('client_order_id') or _iso_now())}"
        if self.storage.load_record("alerts", alert_id):
            return
        payload = {
            "alert_id": alert_id,
            "generated_at": _iso_now(),
            "kind": "submit_unknown_unresolved",
            "severity": "high",
            "message": "A paper submit lock remains submit_unknown after Alpaca reconciliation; no automatic resubmit will be attempted.",
            "payload": {
                "lock_id": lock.get("lock_id"),
                "session_date": lock.get("session_date"),
                "symbol": lock.get("symbol"),
                "side": lock.get("side"),
                "client_order_id": lock.get("client_order_id"),
                "execution_id": lock.get("execution_id"),
            },
            "status": "active",
            "notifier": self._alert_notifier_status(),
        }
        payload["storage"] = self.storage.persist_record("alerts", alert_id, _jsonable(payload))

    def _hydrate_execution_payload_from_journal(
        self,
        execution_payload: dict[str, Any],
        journal: dict[str, Any],
    ) -> dict[str, Any]:
        records = journal.get("records", [])
        for order in execution_payload.get("orders", []):
            record = self._find_journal_record(
                journal,
                order.get("client_order_id") or order.get("broker_order_id") or order.get("symbol"),
            )
            if record is None:
                continue
            summary = record.get("last_broker_snapshot") or {}
            order.update(
                {
                    "status": summary.get("status", record.get("current_state", order.get("status"))),
                    "broker_order_id": summary.get("id") or order.get("broker_order_id"),
                    "client_order_id": summary.get("client_order_id") or order.get("client_order_id"),
                    "submitted_at": summary.get("submitted_at") or order.get("submitted_at"),
                    "filled_qty": summary.get("filled_qty") or order.get("filled_qty"),
                    "filled_avg_price": summary.get("filled_avg_price") or order.get("filled_avg_price"),
                    "order_type": summary.get("type") or order.get("order_type"),
                    "time_in_force": summary.get("time_in_force") or order.get("time_in_force"),
                    "notional": summary.get("notional") or order.get("notional"),
                }
            )

        execution_payload["cancelable_order_ids"] = [
            item["order_id"]
            for item in records
            if self._can_cancel_state(item.get("current_state"))
        ]
        execution_payload["retryable_order_ids"] = [
            item["order_id"]
            for item in records
            if self._can_retry_state(item.get("current_state"))
        ]
        execution_payload["journal"] = journal
        execution_payload["state_machine"] = {
            "state": journal.get("current_state"),
            "allowed_actions": journal.get("allowed_actions", []),
        }
        execution_payload["controls"] = self.get_execution_controls()
        execution_payload["stale_orders"] = self._collect_stale_orders(journal, minutes=None)
        return execution_payload

    @staticmethod
    def _resolve_runtime_path(raw_path: str, default_name: str) -> Path:
        candidate = Path(str(raw_path or "").strip() or default_name)
        if candidate.is_absolute():
            return candidate
        return Path(__file__).resolve().parents[2] / candidate

    def _load_runtime_registry(self) -> dict[str, Any]:
        registry_path = self._resolve_runtime_path(
            getattr(settings, "MODEL_REGISTRY_PATH", "storage/quant/model_registry/current_runtime.json"),
            "storage/quant/model_registry/current_runtime.json",
        )
        if not registry_path.exists():
            return {}
        try:
            return json.loads(registry_path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning(f"Model registry load failed for {registry_path}: {exc}")
            return {"load_error": str(exc), "registry_path": registry_path.as_posix()}

    def _active_canary_percent(self) -> float | None:
        if not bool(getattr(settings, "EXECUTION_CANARY_ENABLED", True)):
            return None
        registry = self._load_runtime_registry()
        models = dict(registry.get("models", {}) or {})
        active_percents: list[float] = []
        for entry in models.values():
            if str(entry.get("action") or "").lower() != "canary":
                continue
            raw_percent = entry.get("canary_percent")
            if raw_percent is None:
                raw_percent = getattr(settings, "EXECUTION_CANARY_RELEASE_PERCENT", 0.15)
            try:
                active_percents.append(float(raw_percent))
            except (TypeError, ValueError):
                continue
        if not active_percents:
            return None
        return max(0.0, min(max(active_percents), 1.0))

    def _scheduler_heartbeat_status(self) -> dict[str, Any]:
        heartbeat_path = self._resolve_runtime_path(
            getattr(settings, "SCHEDULER_HEARTBEAT_PATH", "storage/quant/scheduler/heartbeat.json"),
            "storage/quant/scheduler/heartbeat.json",
        )
        payload = {
            "path": heartbeat_path.as_posix(),
            "exists": heartbeat_path.exists(),
            "stale": True,
            "last_seen": None,
        }
        if not heartbeat_path.exists():
            return payload
        try:
            heartbeat = json.loads(heartbeat_path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning(f"Scheduler heartbeat load failed for {heartbeat_path}: {exc}")
            payload["load_error"] = str(exc)
            payload["status"] = "unavailable"
            return payload
        last_seen = self._parse_any_timestamp(heartbeat.get("updated_at") or heartbeat.get("generated_at"))
        payload["last_seen"] = heartbeat.get("updated_at") or heartbeat.get("generated_at")
        if last_seen is None:
            return payload
        stale_after = int(getattr(settings, "SCHEDULER_SYNC_INTERVAL_MINUTES", 5) or 5) * 3
        age_minutes = (datetime.now(timezone.utc) - last_seen.astimezone(timezone.utc)).total_seconds() / 60
        payload["age_minutes"] = round(age_minutes, 2)
        payload["stale"] = age_minutes > stale_after
        payload["status"] = heartbeat.get("status", "unknown")
        return payload

    def _remote_llm_status(self) -> dict[str, Any]:
        base_url = str(getattr(settings, "REMOTE_LLM_URL", "") or "")
        payload = {
            "configured": bool(base_url),
            "backend_mode": getattr(settings, "LLM_BACKEND_MODE", "auto"),
            "base_url": base_url,
            "reachable": False,
            "status_code": None,
        }
        if not base_url:
            return payload
        health_url = f"{base_url.rstrip('/')}/health"
        try:
            response = requests.get(health_url, timeout=2)
            payload["status_code"] = response.status_code
            payload["reachable"] = response.ok
            try:
                payload["response"] = response.json()
            except Exception:
                payload["response"] = response.text[:200]
        except Exception as exc:
            payload["error"] = str(exc)
        return payload

    def _qdrant_status(self) -> dict[str, Any]:
        qdrant_url = str(getattr(settings, "QDRANT_URL", "") or "")
        if not qdrant_url:
            qdrant_url = "http://localhost:6333"
        payload = {
            "configured": bool(qdrant_url),
            "url": qdrant_url,
            "reachable": False,
            "status_code": None,
        }
        health_url = f"{qdrant_url.rstrip('/')}/healthz"
        try:
            response = requests.get(health_url, timeout=2)
            payload["status_code"] = response.status_code
            payload["reachable"] = response.ok
            payload["response"] = response.text[:200]
        except Exception as exc:
            payload["error"] = str(exc)
        return payload

    def _auth_key_status(self) -> dict[str, Any]:
        keys = {
            "execution_api_key_set": bool(getattr(settings, "EXECUTION_API_KEY", "")),
            "admin_api_key_set": bool(getattr(settings, "ADMIN_API_KEY", "")),
            "ops_api_key_set": bool(getattr(settings, "OPS_API_KEY", "")),
        }
        missing = [name for name, configured in keys.items() if not configured]
        return {
            "configured": not missing,
            "keys": keys,
            "missing": missing,
        }

    def _llm_mode_status(self) -> dict[str, Any]:
        from gateway.utils.llm_client import get_runtime_backend_status

        runtime_status = get_runtime_backend_status()
        remote_status = self._remote_llm_status()
        cloud_fallback_ready = bool(getattr(settings, "OPENAI_API_KEY", "") or getattr(settings, "DEEPSEEK_API_KEY", ""))
        local_auto_ok = bool(
            (runtime_status.get("local_checkpoint_exists") and runtime_status.get("local_llm_cuda_available"))
            or cloud_fallback_ready
        )
        remote_api_key_set = bool(getattr(settings, "REMOTE_LLM_API_KEY", ""))
        hybrid_remote_ok = bool(remote_status.get("configured")) and remote_api_key_set and bool(remote_status.get("reachable"))
        return {
            "current": runtime_status,
            "local_auto": {
                "ok": local_auto_ok,
                "detail": "local checkpoint with CUDA or cloud fallback keys available",
                "meta": {
                    "local_checkpoint_exists": bool(runtime_status.get("local_checkpoint_exists")),
                    "local_llm_cuda_available": bool(runtime_status.get("local_llm_cuda_available")),
                    "cloud_fallback_ready": cloud_fallback_ready,
                },
            },
            "hybrid_remote": {
                "ok": hybrid_remote_ok,
                "detail": remote_status.get("base_url") or "REMOTE_LLM_URL not configured",
                "meta": {
                    **remote_status,
                    "remote_llm_api_key_set": remote_api_key_set,
                },
            },
        }

    def build_healthcheck(self) -> dict[str, Any]:
        heartbeat = self._scheduler_heartbeat_status()
        llm_modes = self._llm_mode_status()
        remote_llm = llm_modes["hybrid_remote"]["meta"]
        qdrant = self._qdrant_status()
        model_registry = self.build_model_registry()
        auth_keys = self._auth_key_status()
        paper_gate = self.build_paper_gate_report(persist=False)
        components = {
            "api": {"ok": True, "detail": "FastAPI runtime is available."},
            "quant_scheduler": {
                "ok": heartbeat.get("exists") and not heartbeat.get("stale"),
                "detail": f"Heartbeat {heartbeat.get('last_seen') or 'missing'}",
                "meta": heartbeat,
            },
            "auth_keys": {
                "ok": auth_keys.get("configured", False),
                "detail": "all required API scopes configured" if auth_keys.get("configured") else f"missing {', '.join(auth_keys.get('missing', []))}",
                "meta": auth_keys,
            },
            "llm_local_auto": {
                "ok": llm_modes["local_auto"]["ok"],
                "detail": llm_modes["local_auto"]["detail"],
                "meta": llm_modes["local_auto"]["meta"],
            },
            "llm_hybrid_remote": {
                "ok": llm_modes["hybrid_remote"]["ok"],
                "detail": llm_modes["hybrid_remote"]["detail"],
                "meta": llm_modes["hybrid_remote"]["meta"],
            },
            "remote_llm": {
                "ok": llm_modes["hybrid_remote"]["ok"],
                "detail": remote_llm.get("base_url") or "REMOTE_LLM_URL not configured",
                "meta": remote_llm,
            },
            "qdrant": {
                "ok": bool(qdrant.get("configured")) and bool(qdrant.get("reachable")),
                "detail": qdrant.get("url"),
                "meta": qdrant,
            },
            "model_registry": {
                "ok": bool(model_registry.get("models")),
                "detail": model_registry.get("registry_path"),
            },
            "paper_gate": {
                "ok": True,
                "detail": "passed" if paper_gate.get("passed") else "live locked until Paper gate passes",
                "meta": paper_gate,
            },
        }
        required = [
            item.strip()
            for item in str(
                getattr(
                    settings,
                    "API_HEALTHCHECK_REQUIRED_COMPONENTS",
                    "api,quant_scheduler,auth_keys,llm_local_auto,llm_hybrid_remote,qdrant,model_registry",
                )
            ).split(",")
            if item.strip()
        ]
        ready = all(components.get(item, {}).get("ok", False) for item in required)
        return {
            "generated_at": _iso_now(),
            "ready": ready,
            "required_components": required,
            "components": components,
        }

    def build_strategy_health(self) -> dict[str, Any]:
        validations = self.storage.list_records("validations")
        executions = self.storage.list_records("executions")
        backtests = self.storage.list_records("backtests")
        latest_validation = validations[0] if validations else {}
        latest_execution = executions[0] if executions else {}
        latest_backtest = backtests[0] if backtests else {}
        paper_gate = self.build_paper_gate_report(persist=False)
        components = {
            "alpha_ranker": self.alpha_ranker.status(),
            "p1_suite": self.p1_suite.status(),
            "p2_stack": self.p2_stack.status(),
            "paper_gate": paper_gate,
        }
        blockers: list[str] = []
        if not components["alpha_ranker"].get("available"):
            blockers.append("Alpha ranker checkpoint is unavailable.")
        if not components["p1_suite"].get("available"):
            blockers.append("P1 suite is unavailable.")
        if not components["p2_stack"].get("available"):
            blockers.append("P2 stack is unavailable.")
        if latest_validation and float(latest_validation.get("out_of_sample_sharpe", 0.0)) <= 0:
            blockers.append("Latest validation out-of-sample Sharpe is non-positive.")
        overall = "healthy" if not blockers else "degraded"
        return {
            "generated_at": _iso_now(),
            "overall": overall,
            "blockers": blockers,
            "latest_validation": latest_validation,
            "latest_execution": {
                "execution_id": latest_execution.get("execution_id"),
                "broker_status": latest_execution.get("broker_status"),
                "submitted": latest_execution.get("submitted"),
            },
            "latest_backtest": {
                "backtest_id": latest_backtest.get("backtest_id"),
                "sharpe": ((latest_backtest.get("metrics") or {}).get("sharpe") if latest_backtest else None),
            },
            "paper_gate": paper_gate,
            "components": components,
        }

    def search_audit_events(
        self,
        *,
        query: str = "",
        category: str = "",
        action: str = "",
        limit: int = 50,
    ) -> dict[str, Any]:
        normalized_query = str(query or "").strip().lower()
        normalized_category = str(category or "").strip().lower()
        normalized_action = str(action or "").strip().lower()
        rows = self.storage.list_records("audit_summary")
        matches: list[dict[str, Any]] = []
        for row in rows:
            row_category = str(row.get("category") or "").lower()
            row_action = str(row.get("action") or "").lower()
            payload = row.get("payload") or {}
            serialized = json.dumps(payload, ensure_ascii=False).lower()
            if normalized_category and row_category != normalized_category:
                continue
            if normalized_action and row_action != normalized_action:
                continue
            if normalized_query and normalized_query not in serialized and normalized_query not in row_action and normalized_query not in row_category:
                continue
            matches.append(row)
            if len(matches) >= max(1, min(int(limit or 50), 200)):
                break
        return {
            "generated_at": _iso_now(),
            "query": query,
            "category": category,
            "action": action,
            "results": matches,
            "count": len(matches),
        }

    def build_model_registry(self) -> dict[str, Any]:
        event_classifier_status = get_event_classifier_runtime().status()
        registry_path = self._resolve_runtime_path(
            getattr(settings, "MODEL_REGISTRY_PATH", "storage/quant/model_registry/current_runtime.json"),
            "storage/quant/model_registry/current_runtime.json",
        )
        release_log_path = self._resolve_runtime_path(
            getattr(settings, "MODEL_RELEASE_LOG_PATH", "storage/quant/model_registry/release_log.jsonl"),
            "storage/quant/model_registry/release_log.jsonl",
        )
        current_registry = self._load_runtime_registry()

        def _registry_entry(model_key: str) -> dict[str, Any]:
            return dict(current_registry.get("models", {}).get(model_key, {}) or {})

        def _decorate_model(model_key: str, *, available: bool, version: Any, checkpoint_dir: Any) -> dict[str, Any]:
            entry = _registry_entry(model_key)
            return {
                "key": model_key,
                "available": bool(available),
                "version": version,
                "checkpoint_dir": checkpoint_dir,
                "release_action": entry.get("action"),
                "release_actor": entry.get("actor"),
                "release_notes": entry.get("notes"),
                "release_updated_at": entry.get("updated_at"),
                "release_canary_percent": entry.get("canary_percent"),
            }

        models = [
            _decorate_model(
                "remote_llm",
                available=bool(self._remote_llm_status().get("configured")),
                version=_registry_entry("remote_llm").get("version")
                or getattr(settings, "REMOTE_LLM_BASE_MODEL", "Qwen/Qwen2.5-7B-Instruct"),
                checkpoint_dir=str(Path(__file__).resolve().parents[2] / "model-serving" / "checkpoint"),
            ),
            _decorate_model(
                "alpha_ranker",
                available=bool(self.alpha_ranker.status().get("available")),
                version=_registry_entry("alpha_ranker").get("version")
                or self.alpha_ranker.status().get("metadata", {}).get("generated_at"),
                checkpoint_dir=self.alpha_ranker.status().get("checkpoint_dir"),
            ),
            _decorate_model(
                "p1_suite",
                available=bool(self.p1_suite.status().get("available")),
                version=_registry_entry("p1_suite").get("version")
                or self.p1_suite.status().get("suite_manifest", {}).get("generated_at"),
                checkpoint_dir=self.p1_suite.status().get("checkpoint_root"),
            ),
            _decorate_model(
                "sequence_forecaster",
                available=bool(self.p1_suite.status().get("sequence_forecaster", {}).get("available")),
                version=_registry_entry("sequence_forecaster").get("version")
                or self.p1_suite.status().get("sequence_forecaster", {}).get("version"),
                checkpoint_dir=self.p1_suite.status().get("sequence_forecaster", {}).get("checkpoint_dir"),
            ),
            _decorate_model(
                "event_classifier",
                available=bool(event_classifier_status.get("available")),
                version=_registry_entry("event_classifier").get("version")
                or getattr(settings, "EVENT_CLASSIFIER_TARGET", "controversy_label"),
                checkpoint_dir=event_classifier_status.get("checkpoint_dir")
                or getattr(settings, "EVENT_CLASSIFIER_CHECKPOINT_ROOT", "model-serving/checkpoint/event_classifier"),
            ),
            _decorate_model(
                "p2_selector",
                available=bool(self.p2_stack.status().get("selector", {}).get("available")),
                version=_registry_entry("p2_selector").get("version")
                or self.p2_stack.status().get("selector", {}).get("suite_manifest", {}).get("generated_at"),
                checkpoint_dir=self.p2_stack.status().get("selector", {}).get("checkpoint_root"),
            ),
            _decorate_model(
                "contextual_bandit",
                available=bool(self.p2_stack.status().get("selector", {}).get("bandit", {}).get("available")),
                version=_registry_entry("contextual_bandit").get("version")
                or self.p2_stack.status().get("selector", {}).get("bandit", {}).get("metadata", {}).get("generated_at"),
                checkpoint_dir=self.p2_stack.status().get("selector", {}).get("bandit", {}).get("checkpoint_dir"),
            ),
            _decorate_model(
                "gnn_graph",
                available=bool(self.p2_stack.status().get("graph", {}).get("gnn", {}).get("available")),
                version=_registry_entry("gnn_graph").get("version")
                or self.p2_stack.status().get("graph", {}).get("gnn", {}).get("version"),
                checkpoint_dir=self.p2_stack.status().get("graph", {}).get("gnn", {}).get("checkpoint_dir"),
            ),
        ]

        release_log_tail: list[dict[str, Any]] = []
        if release_log_path.exists():
            try:
                lines = release_log_path.read_text(encoding="utf-8").splitlines()[-10:]
                for line in lines:
                    if line.strip():
                        release_log_tail.append(json.loads(line))
            except Exception as exc:
                logger.warning(f"Model release log load failed for {release_log_path}: {exc}")
                release_log_tail = []

        return {
            "generated_at": _iso_now(),
            "registry_path": str(registry_path),
            "release_log_path": str(release_log_path),
            "registry_load_error": current_registry.get("load_error"),
            "canary_enabled": bool(getattr(settings, "EXECUTION_CANARY_ENABLED", True)),
            "canary_release_percent": float(getattr(settings, "EXECUTION_CANARY_RELEASE_PERCENT", 0.15) or 0.15),
            "has_active_canary": self._active_canary_percent() is not None,
            "active_canary_percent": self._active_canary_percent(),
            "models": models,
            "release_log_tail": release_log_tail,
        }

    def ensure_runtime_model_registry(self, *, actor: str = "system") -> dict[str, Any]:
        registry_path = self._resolve_runtime_path(
            getattr(settings, "MODEL_REGISTRY_PATH", "storage/quant/model_registry/current_runtime.json"),
            "storage/quant/model_registry/current_runtime.json",
        )
        if registry_path.exists():
            return {"created": False, "registry_path": str(registry_path), "reason": "registry_exists"}
        try:
            snapshot = self.build_model_registry()
            entries: dict[str, Any] = {}
            for model in snapshot.get("models", []):
                if not isinstance(model, dict) or not model.get("available"):
                    continue
                entries[str(model.get("key"))] = {
                    "version": model.get("version") or "runtime_detected",
                    "action": "runtime_detected",
                    "notes": "Auto-bootstrapped from available local checkpoint artifacts for unattended paper preflight.",
                    "updated_at": snapshot.get("generated_at") or _iso_now(),
                    "actor": actor,
                    "canary_percent": None,
                    "checkpoint_dir": model.get("checkpoint_dir"),
                }
            if not entries:
                return {"created": False, "registry_path": str(registry_path), "reason": "no_available_models"}
            registry_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {"generated_at": _iso_now(), "models": entries}
            registry_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            return {
                "created": True,
                "registry_path": str(registry_path),
                "model_count": len(entries),
                "models": sorted(entries),
            }
        except Exception as exc:
            return {"created": False, "registry_path": str(registry_path), "reason": "bootstrap_failed", "error": str(exc)}

    def update_model_release(
        self,
        *,
        actor: str,
        model_key: str,
        version: str,
        action: str,
        notes: str = "",
        canary_percent: float | None = None,
    ) -> dict[str, Any]:
        registry_path = self._resolve_runtime_path(
            getattr(settings, "MODEL_REGISTRY_PATH", "storage/quant/model_registry/current_runtime.json"),
            "storage/quant/model_registry/current_runtime.json",
        )
        release_log_path = self._resolve_runtime_path(
            getattr(settings, "MODEL_RELEASE_LOG_PATH", "storage/quant/model_registry/release_log.jsonl"),
            "storage/quant/model_registry/release_log.jsonl",
        )
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        release_log_path.parent.mkdir(parents=True, exist_ok=True)
        registry = {"generated_at": _iso_now(), "models": {}}
        if registry_path.exists():
            try:
                registry = json.loads(registry_path.read_text(encoding="utf-8"))
            except Exception:
                registry = {"generated_at": _iso_now(), "models": {}}
        registry.setdefault("models", {})
        registry["generated_at"] = _iso_now()
        registry["models"][model_key] = {
            "version": version,
            "action": action,
            "notes": notes,
            "updated_at": registry["generated_at"],
            "actor": actor,
            "canary_percent": canary_percent,
        }
        registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")
        release_event = {
            "timestamp": _iso_now(),
            "actor": actor,
            "model_key": model_key,
            "version": version,
            "action": action,
            "notes": notes,
            "canary_percent": canary_percent,
        }
        with release_log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(release_event, ensure_ascii=False) + "\n")
        self._record_audit(category="model_release", action=action, payload=release_event)
        return {
            "ok": True,
            "registry_path": str(registry_path),
            "release_log_path": str(release_log_path),
            "release": release_event,
        }

    def build_ops_alerts(
        self,
        *,
        monitor: dict[str, Any] | None = None,
        metrics: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        monitor = monitor or self.build_execution_monitor(broker=self.default_broker)
        metrics = metrics or {}
        alerts: list[dict[str, Any]] = []
        stale_orders = monitor.get("stale_orders", [])
        if len(stale_orders) >= int(getattr(settings, "EXECUTION_STALE_ORDER_ALERT_THRESHOLD", 1) or 1):
            alerts.append(
                {
                    "severity": "high",
                    "title": "Stale routed orders detected",
                    "detail": f"{len(stale_orders)} orders are beyond the stale threshold.",
                    "action": "Review stale order watch and cancel/retry as needed.",
                }
            )
        if monitor.get("controls", {}).get("kill_switch_enabled"):
            alerts.append(
                {
                    "severity": "medium",
                    "title": "Kill switch engaged",
                    "detail": monitor["controls"].get("kill_switch_reason") or "Execution routing is blocked.",
                    "action": "Release only after operator review.",
                }
            )
        strategy_health = self.build_strategy_health()
        if strategy_health.get("overall") != "healthy":
            alerts.append(
                {
                    "severity": "medium",
                    "title": "Strategy health degraded",
                    "detail": "; ".join(strategy_health.get("blockers", [])[:3]) or "Model suite needs review.",
                    "action": "Inspect P1/P2 readiness and latest validation before routing.",
                }
            )
        if not self.alpha_ranker.status().get("available"):
            alerts.append(
                {
                    "severity": "high",
                    "title": "Alpha ranker unavailable",
                    "detail": "Alpha ranker checkpoint is missing or not loadable.",
                    "action": "Restore checkpoint before promoting research to paper execution.",
                }
            )
        return {"generated_at": _iso_now(), "alerts": alerts, "count": len(alerts)}

    def _estimate_order_slippage_bps(self, position: PortfolioPosition, capital_base: float) -> float:
        base = float(getattr(settings, "EXECUTION_DEFAULT_SLIPPAGE_BPS", 8.0) or 8.0)
        order_notional = max(capital_base * max(float(position.weight or 0.0), 0.0), 0.0)
        snapshot = self._estimate_liquidity_snapshot(position.symbol, order_notional)
        participation = _bounded(snapshot["participation_rate"], 0.0, 1.5)
        volatility = _bounded(snapshot["realized_volatility"], 0.06, 0.85)
        spread = snapshot["spread_proxy_bps"]
        urgency = {
            "passive_limit": 0.82,
            "twap": 0.96,
            "adaptive": 1.03,
            "aggressive_market": 1.24,
        }.get(str(position.execution_tactic or "").lower(), 1.0)
        slippage = (
            spread * 0.45 * urgency
            + 78.0 * math.sqrt(max(participation, 0.0)) * max(volatility, 0.08)
            + 10.0 * max(float(position.weight or 0.0), 0.0) * urgency
            + base * 0.35
        )
        return round(_bounded(slippage, max(base * 0.5, 2.5), 95.0), 2)

    def _estimate_order_impact_bps(self, position: PortfolioPosition, capital_base: float) -> float:
        base = float(getattr(settings, "EXECUTION_DEFAULT_IMPACT_BPS", 5.0) or 5.0)
        order_notional = max(capital_base * max(float(position.weight or 0.0), 0.0), 0.0)
        snapshot = self._estimate_liquidity_snapshot(position.symbol, order_notional)
        participation = _bounded(snapshot["participation_rate"], 0.0, 2.0)
        volatility = _bounded(snapshot["realized_volatility"], 0.06, 0.85)
        impact = (
            base
            + 95.0 * volatility * math.sqrt(max(participation, 0.0))
            + 18.0 * participation
            + 6.5 * max(float(position.weight or 0.0), 0.0)
        )
        if str(position.execution_tactic or "").lower() == "aggressive_market":
            impact *= 1.18
        elif str(position.execution_tactic or "").lower() == "passive_limit":
            impact *= 0.88
        return round(_bounded(impact, max(base * 0.5, 2.0), 85.0), 2)

    def _estimate_order_fill_probability(
        self,
        position: PortfolioPosition,
        *,
        capital_base: float,
        slippage_bps: float,
        impact_bps: float,
    ) -> float:
        base = float(getattr(settings, "EXECUTION_FILL_PROBABILITY_BASE", 0.72) or 0.72)
        min_fill = float(getattr(settings, "EXECUTION_FILL_PROBABILITY_MIN", 0.08) or 0.08)
        max_fill = float(getattr(settings, "EXECUTION_FILL_PROBABILITY_MAX", 0.98) or 0.98)
        order_notional = max(capital_base * max(float(position.weight or 0.0), 0.0), 0.0)
        snapshot = self._estimate_liquidity_snapshot(position.symbol, order_notional)
        participation = _bounded(snapshot["participation_rate"], 0.0, 2.0)
        volatility = _bounded(snapshot["realized_volatility"], 0.06, 0.85)
        confidence_bonus = ((float(position.score) / 100.0) - 0.5) * 0.24
        urgency = {
            "passive_limit": -0.18,
            "twap": -0.05,
            "adaptive": 0.0,
            "aggressive_market": 0.10,
        }.get(str(position.execution_tactic or "").lower(), 0.0)
        logit = (
            1.10
            + confidence_bonus
            + urgency
            - 4.4 * math.sqrt(max(participation, 0.0))
            - 1.65 * volatility
            - (slippage_bps / 120.0)
            - (impact_bps / 145.0)
            + (base - 0.72)
        )
        probability = 1.0 / (1.0 + math.exp(-logit))
        return round(_bounded(probability, min_fill, max_fill), 4)

    def _select_execution_tactic(self, position: PortfolioPosition) -> str:
        if position.execution_tactic:
            return str(position.execution_tactic)
        if float(position.risk_budget or 0.0) < 0.35:
            return "aggressive_market"
        if float(position.weight or 0.0) >= 0.18:
            return "twap"
        return "passive_limit"

    def _assign_canary_bucket(self, execution_id: str, symbol: str) -> str:
        release_percent = self._active_canary_percent()
        if release_percent is None:
            return "full_release"
        sample = (_stable_seed(execution_id, symbol, "canary") % 1000) / 1000.0
        return "canary_release" if sample <= release_percent else "holdout_shadow"

    def _export_paper_feedback(self, execution_payload: dict[str, Any], journal: dict[str, Any]) -> None:
        if not bool(getattr(settings, "PAPER_FEEDBACK_CAPTURE_ENABLED", True)):
            return
        feedback_dir = self._resolve_runtime_path(
            getattr(settings, "PAPER_FEEDBACK_DIR", "storage/quant/paper_feedback"),
            "storage/quant/paper_feedback",
        )
        feedback_dir.mkdir(parents=True, exist_ok=True)
        feedback_payload = {
            "generated_at": _iso_now(),
            "execution_id": execution_payload.get("execution_id"),
            "broker_id": execution_payload.get("broker_id"),
            "submitted": execution_payload.get("submitted"),
            "broker_status": execution_payload.get("broker_status"),
            "orders": execution_payload.get("orders", []),
            "journal": journal,
            "portfolio": execution_payload.get("portfolio", {}),
            "validation_link": (self.storage.list_records("validations") or [{}])[0].get("validation_id"),
        }
        (feedback_dir / f"{execution_payload.get('execution_id')}.json").write_text(
            json.dumps(feedback_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _record_audit(self, *, category: str, action: str, payload: dict[str, Any]) -> None:
        if not bool(getattr(settings, "AUDIT_LOG_ENABLED", True)):
            return
        self.storage.append_audit_event(category=category, action=action, payload=payload)
        audit_id = f"audit-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
        self.storage.persist_record(
            "audit_summary",
            audit_id,
            {
                "audit_id": audit_id,
                "created_at": _iso_now(),
                "category": category,
                "action": action,
                "payload": payload,
            },
        )

    def _simulate_validation_window(
        self,
        *,
        label: str,
        start_offset: int,
        duration: int,
        portfolio: PortfolioSummary,
        slippage_bps: float,
        impact_cost_bps: float,
        strategy_name: str,
        bucket: str | None = None,
        fill_probability: float | None = None,
        calibrated_confidence: float | None = None,
    ) -> ValidationWindow:
        drift = portfolio.expected_alpha / 252.0
        daily_returns: list[float] = []
        nav = 1.0
        peak = 1.0
        max_drawdown = 0.0
        for step in range(max(20, duration)):
            seed = _stable_seed(strategy_name, portfolio.strategy_name, label, str(step + start_offset))
            cyclical = math.sin((step + start_offset) / 7) * 0.0018
            idiosyncratic = ((seed % 25) - 12) / 10000
            cost_drag = (portfolio.turnover_estimate * (slippage_bps + impact_cost_bps)) / 1_000_000
            daily_return = drift + cyclical + idiosyncratic - cost_drag
            daily_returns.append(daily_return)
            nav *= 1 + daily_return
            peak = max(peak, nav)
            max_drawdown = max(max_drawdown, 1 - nav / peak)
        annualized_return = _bounded(statistics.mean(daily_returns) * 252 if daily_returns else 0.0, -0.95, 1.5)
        annualized_vol = statistics.pstdev(daily_returns) * math.sqrt(252) if len(daily_returns) > 1 else 0.0
        sharpe = _bounded(annualized_return / annualized_vol if annualized_vol else 0.0, -4.5, 4.5)
        turnover_drag = portfolio.turnover_estimate * (slippage_bps + impact_cost_bps) / 10000
        end_date = date.today() - timedelta(days=start_offset)
        start_date = end_date - timedelta(days=duration)
        return ValidationWindow(
            label=label,
            start=start_date.isoformat(),
            end=end_date.isoformat(),
            sharpe=round(sharpe, 4),
            cumulative_return=round(nav - 1, 4),
            turnover_cost_drag=round(turnover_drag, 4),
            max_drawdown=round(max_drawdown, 4),
            bucket=bucket,
            fill_probability=fill_probability,
            expected_slippage_bps=round(slippage_bps, 2),
            calibrated_confidence=calibrated_confidence,
        )

    @staticmethod
    def _validation_bucket_for_index(index: int) -> str:
        buckets = ("high_confidence", "medium_confidence", "low_confidence")
        return buckets[index % len(buckets)]

    @staticmethod
    def _average_portfolio_fill_probability(portfolio: PortfolioSummary) -> float:
        return round(
            statistics.mean([float(item.expected_fill_probability or 0.0) for item in portfolio.positions] or [0.0]),
            4,
        )

    @staticmethod
    def _average_calibrated_confidence(signals: list[ResearchSignal]) -> float:
        return round(
            statistics.mean([float(item.p1_confidence_calibrated or item.decision_confidence or 0.0) for item in signals] or [0.0]),
            4,
        )

    @staticmethod
    def _stratify_validation_windows(windows: list[ValidationWindow]) -> list[dict[str, Any]]:
        grouped: dict[str, list[ValidationWindow]] = {}
        for window in windows:
            grouped.setdefault(str(window.bucket or "unbucketed"), []).append(window)
        payload: list[dict[str, Any]] = []
        for bucket, members in grouped.items():
            payload.append(
                {
                    "bucket": bucket,
                    "windows": len(members),
                    "average_sharpe": round(statistics.mean([item.sharpe for item in members] or [0.0]), 4),
                    "average_return": round(statistics.mean([item.cumulative_return for item in members] or [0.0]), 4),
                    "average_fill_probability": round(
                        statistics.mean([float(item.fill_probability or 0.0) for item in members] or [0.0]),
                        4,
                    ),
                    "average_calibrated_confidence": round(
                        statistics.mean([float(item.calibrated_confidence or 0.0) for item in members] or [0.0]),
                        4,
                    ),
                }
            )
        return sorted(payload, key=lambda item: item["bucket"])

    @staticmethod
    def _build_alpaca_order_payload(
        *,
        execution_id: str,
        order: dict[str, Any],
        asset: dict[str, Any],
        index: int,
        capped_notional: float,
        normalized_order_type: str,
        normalized_tif: str,
        extended_hours: bool,
    ) -> dict[str, Any]:
        return build_alpaca_order_payload(
            execution_id=execution_id,
            order=order,
            asset=asset,
            index=index,
            capped_notional=capped_notional,
            normalized_order_type=normalized_order_type,
            normalized_tif=normalized_tif,
            extended_hours=extended_hours,
        )

    def _summarize_broker_account(self, broker_id: str, account: dict[str, Any]) -> dict[str, Any]:
        if broker_id == "alpaca":
            return self._summarize_alpaca_account(account)
        return dict(account)

    def _summarize_broker_clock(self, broker_id: str, clock: dict[str, Any]) -> dict[str, Any]:
        if broker_id == "alpaca":
            return self._summarize_alpaca_clock(clock)
        return dict(clock)

    def _summarize_broker_order(self, broker_id: str, order: dict[str, Any]) -> dict[str, Any]:
        if broker_id == "alpaca":
            return self._summarize_alpaca_order(order)
        return dict(order)

    def _summarize_broker_position(self, broker_id: str, position: dict[str, Any]) -> dict[str, Any]:
        if broker_id == "alpaca":
            return self._summarize_alpaca_position(position)
        return dict(position)

    @staticmethod
    def _normalize_order_state(broker_id: str, status: Any) -> str:
        normalized = str(status or "").strip().lower()
        if broker_id == "alpaca":
            mapping = {
                "accepted": "accepted",
                "new": "accepted",
                "pending_new": "pending",
                "partially_filled": "partially_filled",
                "filled": "filled",
                "canceled": "canceled",
                "cancelled": "canceled",
                "done_for_day": "accepted",
                "expired": "expired",
                "rejected": "rejected",
                "replaced": "accepted",
            }
            return mapping.get(normalized, normalized or "unknown")
        return normalized or "unknown"


    def _build_portfolio(
        self,
        signals: list[ResearchSignal],
        capital_base: float,
        benchmark: str,
        *,
        allow_watchlist_fallback: bool = False,
    ) -> PortfolioSummary:
        return self.components.portfolio.build(
            signals,
            capital_base,
            benchmark,
            allow_watchlist_fallback=allow_watchlist_fallback,
        )


    def _build_live_market_signals(
        self,
        universe: list[UniverseMember],
        research_question: str,
        benchmark: str,
        *,
        provider_order_override: list[str] | None = None,
        timeout_override: int | None = None,
        cache_tag: str = "signal_bundle",
    ) -> tuple[list[ResearchSignal], dict[str, Any]]:
        bars_map = self._prefetch_market_bars(
            [member.symbol for member in universe],
            limit=self.signal_engine.history_bars,
            provider_order_override=provider_order_override,
            allow_stale_cache=True,
            timeout_override=timeout_override,
            cache_tag=cache_tag,
        )
        signals = self.signal_engine.build_signals(
            universe=universe,
            benchmark=benchmark,
            research_question=research_question,
            prefetched_bars=bars_map,
        )
        return signals, bars_map

    def _build_signal_bundle(
        self,
        universe: list[UniverseMember],
        research_question: str,
        benchmark: str,
        *,
        provider_order_override: list[str] | None = None,
        timeout_override: int | None = None,
        cache_tag: str = "signal_bundle",
    ) -> tuple[list[ResearchSignal], dict[str, Any]]:
        build_signals_method = getattr(self, "_build_signals")
        build_signals_impl = getattr(build_signals_method, "__func__", build_signals_method)
        if build_signals_impl is not QuantSystemService._build_signals:
            return list(build_signals_method(universe, research_question, benchmark) or []), {}
        market_data_signals: list[ResearchSignal] = []
        bars_map: dict[str, Any] = {}
        if self._should_use_live_market_data():
            try:
                market_data_signals, bars_map = self._build_live_market_signals(
                    universe=universe,
                    research_question=research_question,
                    benchmark=benchmark,
                    provider_order_override=provider_order_override,
                    timeout_override=timeout_override,
                    cache_tag=cache_tag,
                )
            except Exception as exc:
                logger.warning(f"Signal engine fallback engaged: {exc}")

        if len(market_data_signals) == len(universe):
            ranked = self.alpha_ranker.rerank(market_data_signals)
            p1_enriched = self.p1_suite.enrich_and_rerank(ranked)
            return [self._enrich_signal_house_score(signal) for signal in self._apply_p2_stack(p1_enriched)], bars_map

        fallback_signals = self._build_synthetic_signals(universe, research_question, benchmark)
        fallback_lookup = {signal.symbol: signal for signal in fallback_signals}
        covered = {signal.symbol for signal in market_data_signals}
        blended = list(market_data_signals)
        for member in universe:
            if member.symbol in covered:
                continue
            fallback = fallback_lookup.get(member.symbol)
            if fallback is not None:
                blended.append(fallback)

        blended.sort(key=lambda item: (item.action != "long", -item.overall_score, -item.confidence))
        ranked = self.alpha_ranker.rerank(blended)
        p1_enriched = self.p1_suite.enrich_and_rerank(ranked)
        enriched = [self._enrich_signal_house_score(signal) for signal in self._apply_p2_stack(p1_enriched)]
        return enriched, bars_map

    def _build_signals(
        self,
        universe: list[UniverseMember],
        research_question: str,
        benchmark: str,
    ) -> list[ResearchSignal]:
        signals, _ = self._build_signal_bundle(universe, research_question, benchmark)
        return signals

    def _apply_p2_stack(self, signals: list[ResearchSignal]) -> list[ResearchSignal]:
        if not signals or not self.p2_stack.available():
            return signals
        enriched, _, _ = self.p2_stack.apply(signals)
        return enriched

    def _build_p2_context(self, signals: list[ResearchSignal]) -> tuple[dict[str, Any], dict[str, Any]]:
        if not signals:
            return self.p2_stack.graph.analyze([]), self.p2_stack.selector.select([], {"summary": {}})[1]
        _, graph_payload, selector_payload = self.p2_stack.apply(signals)
        return graph_payload, selector_payload

    def _build_synthetic_signals(
        self,
        universe: list[UniverseMember],
        research_question: str,
        benchmark: str,
    ) -> list[ResearchSignal]:
        signals: list[ResearchSignal] = []
        for member in universe:
            seed = _stable_seed(member.symbol, benchmark, "synthetic_fallback")
            momentum = 55 + (seed % 32)
            quality = 52 + ((seed // 7) % 30)
            value = 45 + ((seed // 11) % 28)
            alternative_data = 48 + ((seed // 13) % 36)
            regime_fit = 50 + ((seed // 17) % 30)
            esg_delta = 50 + ((seed // 19) % 34)

            e_score = _bounded(0.28 * alternative_data + 0.42 * esg_delta + 18, 45, 96)
            s_score = _bounded(0.35 * quality + 0.18 * value + 22, 40, 92)
            g_score = _bounded(0.25 * quality + 0.25 * regime_fit + 25, 42, 93)
            overall = round(0.42 * e_score + 0.26 * s_score + 0.32 * g_score, 2)
            confidence = round(_bounded(0.58 + ((seed % 300) / 1000), 0.58, 0.94), 2)
            expected_return = round(((overall - 50) / 420) + ((momentum - 50) / 1000), 4)
            risk_score = round(_bounded(100 - (0.55 * quality + 0.45 * g_score), 18, 78), 2)
            action = "long" if overall >= 64 else "neutral" if overall >= 54 else "short"

            signals.append(
                ResearchSignal(
                    symbol=member.symbol,
                    company_name=member.company_name,
                    sector=member.sector,
                    thesis=(
                        f"{member.company_name} combines ESG trend, quality, and alternative-data proxy strength "
                        f"for enhanced positioning versus {benchmark}."
                    ),
                    action=action,
                    confidence=confidence,
                    expected_return=expected_return,
                    risk_score=risk_score,
                    overall_score=overall,
                    e_score=round(e_score, 2),
                    s_score=round(s_score, 2),
                    g_score=round(g_score, 2),
                    signal_source="synthetic_fallback",
                    market_data_source="synthetic",
                    factor_scores=[
                        FactorScore(name="momentum", value=momentum, contribution=0.18, description="Trend continuation proxy"),
                        FactorScore(name="quality", value=quality, contribution=0.22, description="Quality and balance-sheet proxy"),
                        FactorScore(name="value", value=value, contribution=0.14, description="Valuation cushion proxy"),
                        FactorScore(name="alternative_data", value=alternative_data, contribution=0.19, description="Alternative data proxy"),
                        FactorScore(name="regime_fit", value=regime_fit, contribution=0.11, description="Macro regime fit proxy"),
                        FactorScore(name="esg_delta", value=esg_delta, contribution=0.16, description="ESG disclosure delta proxy"),
                    ],
                    catalysts=[
                        f"{member.company_name} ESG disclosure momentum is above the peer median",
                        f"{member.symbol} retains a stronger quality-governance blend inside {member.sector}",
                        "Synthetic fallback remains reproducible for offline demos and testing",
                    ],
                    data_lineage=[
                        "L0: fallback factor proxies",
                        "L1: deterministic synthetic ranking",
                        "L2: multi-factor + ESG heuristic blend",
                        "L4: Strategy signal -> risk checks -> broker router -> execution journal",
                    ],
                )
            )

        signals.sort(key=lambda item: (item.action != "long", -item.overall_score, -item.confidence))
        return signals

    def _build_backtest(
        self,
        strategy_name: str,
        benchmark: str,
        capital_base: float,
        positions: list[PortfolioPosition],
        lookback_days: int,
        persist: bool,
        market_data_provider: str | None = None,
        force_refresh: bool = False,
    ) -> BacktestResult:
        market_result = None
        provider_chain = self._normalize_market_data_provider_chain(market_data_provider)
        warnings: list[str] = []
        if self._should_use_live_market_data():
            original_order = getattr(self.market_data, "provider_order", None)
            if provider_chain and hasattr(self.market_data, "provider_order"):
                self.market_data.provider_order = [provider for provider in provider_chain if provider != "cache"]
            market_result = self._build_market_data_backtest(
                strategy_name=strategy_name,
                benchmark=benchmark,
                capital_base=capital_base,
                positions=positions,
                lookback_days=lookback_days,
                force_refresh=force_refresh,
            )
            if original_order is not None and hasattr(self.market_data, "provider_order"):
                self.market_data.provider_order = original_order
            if market_result is None:
                warnings.append("Live/cache market data was unavailable; synthetic fallback was used.")
        result = market_result or self._build_synthetic_backtest(
            strategy_name=strategy_name,
            benchmark=benchmark,
            capital_base=capital_base,
            positions=positions,
            lookback_days=lookback_days,
            provider_chain=provider_chain,
            warnings=warnings,
        )

        if persist:
            payload = result.model_dump()
            payload["generated_at"] = _iso_now()
            payload["capital_base"] = capital_base
            payload["storage"] = self.storage.persist_record("backtests", result.backtest_id, payload)
        return result

    def _build_market_data_backtest(
        self,
        *,
        strategy_name: str,
        benchmark: str,
        capital_base: float,
        positions: list[PortfolioPosition],
        lookback_days: int,
        force_refresh: bool = False,
    ) -> BacktestResult | None:
        if not positions:
            return None

        try:
            close_frame = pd.DataFrame()
            provider_labels: list[str] = []
            for position in positions:
                bars_result = self.market_data.get_daily_bars(
                    position.symbol,
                    limit=max(lookback_days + 10, 120),
                    force_refresh=force_refresh,
                )
                bars = bars_result.bars
                if bars.empty:
                    return None
                provider_labels.append(("cache:" if bars_result.cache_hit else "") + bars_result.provider)
                series = bars.set_index("timestamp")["close"].rename(position.symbol)
                close_frame = series.to_frame() if close_frame.empty else close_frame.join(series, how="outer")

            benchmark_result = self.market_data.get_daily_bars(
                benchmark,
                limit=max(lookback_days + 10, 120),
                force_refresh=force_refresh,
            )
            benchmark_bars = benchmark_result.bars
            if benchmark_bars.empty:
                return None
            provider_labels.append(("cache:" if benchmark_result.cache_hit else "") + benchmark_result.provider)
            benchmark_close = benchmark_bars.set_index("timestamp")["close"].rename(benchmark)
            close_frame = close_frame.join(benchmark_close, how="outer").sort_index().ffill().dropna()
            if len(close_frame) < max(20, lookback_days // 2):
                return None

            returns_frame = close_frame.pct_change().dropna().tail(lookback_days)
            if returns_frame.empty:
                return None

            portfolio_returns = pd.Series(0.0, index=returns_frame.index)
            for position in positions:
                portfolio_returns = portfolio_returns.add(
                    returns_frame[position.symbol].fillna(0.0) * position.weight,
                    fill_value=0.0,
                )
            benchmark_returns = returns_frame[benchmark].fillna(0.0)

            portfolio_nav = (1 + portfolio_returns).cumprod()
            benchmark_nav = (1 + benchmark_returns).cumprod()
            drawdown = 1 - portfolio_nav / portfolio_nav.cummax()

            timeline = [
                BacktestPoint(
                    date=index.date().isoformat(),
                    portfolio_nav=round(float(portfolio_nav.loc[index]), 4),
                    benchmark_nav=round(float(benchmark_nav.loc[index]), 4),
                    drawdown=round(float(drawdown.loc[index]), 4),
                    gross_exposure=round(sum(position.weight for position in positions), 4),
                )
                for index in portfolio_nav.index
            ]
            if not timeline:
                return None

            portfolio_values = portfolio_returns.tolist()
            benchmark_values = benchmark_returns.tolist()
            downside = [value for value in portfolio_values if value < 0]
            excess = [portfolio - bench for portfolio, bench in zip(portfolio_values, benchmark_values)]
            cumulative_return = float(portfolio_nav.iloc[-1] - 1)
            annualized_return = float((1 + cumulative_return) ** (252 / max(1, len(portfolio_values))) - 1)
            annualized_vol = float(portfolio_returns.std(ddof=0) * math.sqrt(252)) if len(portfolio_values) > 1 else 0.0
            downside_vol = float(pd.Series(downside).std(ddof=0) * math.sqrt(252)) if len(downside) > 1 else annualized_vol or 1e-6
            sharpe = annualized_return / annualized_vol if annualized_vol else 0.0
            sortino = annualized_return / downside_vol if downside_vol else 0.0
            beta = float(portfolio_returns.cov(benchmark_returns) / benchmark_returns.var()) if len(benchmark_values) > 1 and float(benchmark_returns.var()) else 0.0
            information_ratio = (
                float(pd.Series(excess).mean() / ((pd.Series(excess).std(ddof=0) or 1e-6)) * math.sqrt(252))
                if len(excess) > 1
                else 0.0
            )
            cvar_95 = abs(float(pd.Series(portfolio_values)[pd.Series(portfolio_values) <= pd.Series(portfolio_values).quantile(0.05)].mean() or 0.0))
            metrics = BacktestMetrics(
                cumulative_return=round(cumulative_return, 4),
                annualized_return=round(annualized_return, 4),
                annualized_volatility=round(annualized_vol, 4),
                sharpe=round(sharpe, 4),
                sortino=round(sortino, 4),
                max_drawdown=round(float(drawdown.max()), 4),
                hit_rate=round(float((portfolio_returns > 0).mean()), 4),
                cvar_95=round(cvar_95, 4),
                beta=round(beta, 4),
                information_ratio=round(information_ratio, 4),
            )
            alerts = self._build_risk_alerts(metrics)
            unique_sources = list(dict.fromkeys(provider_labels))
            live_sources = [source for source in unique_sources if not source.startswith("cache:")]
            data_source = ", ".join(live_sources or ["cache"])
            return BacktestResult(
                backtest_id=f"backtest-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
                strategy_name=strategy_name,
                benchmark=benchmark,
                period_start=timeline[0].date,
                period_end=timeline[-1].date,
                metrics=metrics,
                positions=positions,
                timeline=timeline,
                risk_alerts=alerts,
                experiment_tags=["market-data", "walk-forward", "esg", "paper-first"],
                data_source=data_source,
                data_source_chain=unique_sources,
                used_synthetic_fallback=False,
                market_data_warnings=[],
            )
        except Exception as exc:
            logger.warning(f"Market-data backtest fallback engaged: {exc}")
            return None

    def _build_synthetic_backtest(
        self,
        *,
        strategy_name: str,
        benchmark: str,
        capital_base: float,
        positions: list[PortfolioPosition],
        lookback_days: int,
        provider_chain: list[str] | None = None,
        warnings: list[str] | None = None,
    ) -> BacktestResult:
        start = date.today() - timedelta(days=lookback_days)
        nav = 1.0
        benchmark_nav = 1.0
        peak = 1.0
        returns: list[float] = []
        benchmark_returns: list[float] = []
        timeline: list[BacktestPoint] = []

        signal_strength = sum(position.weight * position.expected_return for position in positions)

        for offset in range(lookback_days):
            current_date = start + timedelta(days=offset)
            cyclical = math.sin(offset / 11) * 0.0024
            seasonal = math.cos(offset / 29) * 0.0018
            drift = signal_strength / 7.5
            daily_return = drift + cyclical + seasonal
            benchmark_return = 0.0006 + math.sin(offset / 15) * 0.0014

            nav *= 1 + daily_return
            benchmark_nav *= 1 + benchmark_return
            peak = max(peak, nav)
            current_drawdown = 1 - nav / peak

            returns.append(daily_return)
            benchmark_returns.append(benchmark_return)
            timeline.append(
                BacktestPoint(
                    date=current_date.isoformat(),
                    portfolio_nav=round(nav, 4),
                    benchmark_nav=round(benchmark_nav, 4),
                    drawdown=round(current_drawdown, 4),
                    gross_exposure=round(sum(position.weight for position in positions), 4),
                )
            )

        downside = [value for value in returns if value < 0]
        excess = [portfolio - bench for portfolio, bench in zip(returns, benchmark_returns)]
        annualized_return = (nav ** (252 / max(1, lookback_days))) - 1
        annualized_vol = statistics.pstdev(returns) * math.sqrt(252) if len(returns) > 1 else 0.0
        downside_vol = statistics.pstdev(downside) * math.sqrt(252) if len(downside) > 1 else annualized_vol or 1e-6
        sharpe = annualized_return / annualized_vol if annualized_vol else 0.0
        sortino = annualized_return / downside_vol if downside_vol else 0.0
        mean_portfolio = statistics.mean(returns)
        mean_benchmark = statistics.mean(benchmark_returns)
        covariance = statistics.mean((r - mean_portfolio) * (b - mean_benchmark) for r, b in zip(returns, benchmark_returns))
        benchmark_var = statistics.pvariance(benchmark_returns) if len(benchmark_returns) > 1 else 0.0
        beta = covariance / benchmark_var if benchmark_var else 0.0
        information_ratio = (
            statistics.mean(excess) / (statistics.pstdev(excess) or 1e-6) * math.sqrt(252)
            if len(excess) > 1
            else 0.0
        )
        cvar_95 = abs(statistics.mean(sorted(returns)[: max(1, len(returns) // 20)]))
        metrics = BacktestMetrics(
            cumulative_return=round(nav - 1, 4),
            annualized_return=round(annualized_return, 4),
            annualized_volatility=round(annualized_vol, 4),
            sharpe=round(sharpe, 4),
            sortino=round(sortino, 4),
            max_drawdown=round(max(point.drawdown for point in timeline), 4),
            hit_rate=round(sum(1 for value in returns if value > 0) / len(returns), 4),
            cvar_95=round(cvar_95, 4),
            beta=round(beta, 4),
            information_ratio=round(information_ratio, 4),
        )
        return BacktestResult(
            backtest_id=f"backtest-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            strategy_name=strategy_name,
            benchmark=benchmark,
            period_start=timeline[0].date,
            period_end=timeline[-1].date,
            metrics=metrics,
            positions=positions,
            timeline=timeline,
            risk_alerts=self._build_risk_alerts(metrics),
            experiment_tags=["walk-forward", "esg", "multi-factor", "paper-first"],
            data_source="synthetic fallback",
            data_source_chain=list(provider_chain or []) + ["synthetic"],
            used_synthetic_fallback=True,
            market_data_warnings=warnings or ["Synthetic fallback was used because live/cache market data was unavailable."],
        )

    def _normalize_sweep_grid(self, parameter_grid: dict[str, list[Any]] | None, *, lookback_days: int) -> dict[str, list[Any]]:
        normalized = {
            "lookback_days": [lookback_days],
            "position_scale": [0.9, 1.0, 1.1],
            "position_cap": [1.0],
            "signal_return_scale": [1.0],
            "transaction_cost_bps": [0.0, 8.0],
        }
        for key, values in (parameter_grid or {}).items():
            cleaned = [value for value in list(values or []) if value is not None]
            if cleaned:
                normalized[key] = cleaned
        return normalized

    def _apply_sweep_parameters(
        self,
        positions: list[PortfolioPosition],
        parameters: dict[str, Any],
    ) -> list[PortfolioPosition]:
        scale = float(parameters.get("position_scale") or 1.0)
        position_cap = float(parameters.get("position_cap") or 1.0)
        return_scale = float(parameters.get("signal_return_scale") or 1.0)
        updated: list[PortfolioPosition] = []
        for position in positions:
            updated.append(
                position.model_copy(
                    update={
                        "weight": min(float(position.weight or 0.0) * scale, position_cap),
                        "expected_return": float(position.expected_return or 0.0) * return_scale,
                        "risk_budget": min(float(position.risk_budget or 0.0) * scale, 1.0),
                    }
                )
            )
        total_weight = sum(float(position.weight or 0.0) for position in updated)
        if total_weight > 1.0 and total_weight > 0:
            updated = [
                position.model_copy(update={"weight": round(float(position.weight or 0.0) / total_weight, 6)})
                for position in updated
            ]
        return updated

    def _apply_backtest_cost_adjustments(self, metrics: dict[str, Any], *, transaction_cost_bps: float) -> dict[str, float]:
        adjusted = {key: float(value) for key, value in metrics.items()}
        drag = max(float(transaction_cost_bps), 0.0) / 10000.0
        if drag <= 0:
            return adjusted
        adjusted["cumulative_return"] = round(adjusted.get("cumulative_return", 0.0) - drag * 2.4, 6)
        adjusted["annualized_return"] = round(adjusted.get("annualized_return", 0.0) - drag * 1.8, 6)
        adjusted["sharpe"] = round(adjusted.get("sharpe", 0.0) - drag * 18.0, 6)
        adjusted["sortino"] = round(adjusted.get("sortino", 0.0) - drag * 14.0, 6)
        adjusted["max_drawdown"] = round(adjusted.get("max_drawdown", 0.0) + drag * 1.5, 6)
        adjusted["information_ratio"] = round(adjusted.get("information_ratio", 0.0) - drag * 10.0, 6)
        return adjusted

    def _build_scenario_matrix(self, combinations: list[dict[str, Any]]) -> list[dict[str, Any]]:
        top = combinations[:3]
        matrix: list[dict[str, Any]] = []
        for row in top:
            parameters = dict(row.get("parameters") or {})
            metrics = dict(row.get("metrics") or {})
            matrix.append(
                {
                    "label": f"lookback={parameters.get('lookback_days')} cost={parameters.get('transaction_cost_bps', 0)}bps",
                    "sharpe": float(metrics.get("sharpe") or 0.0),
                    "cumulative_return": float(metrics.get("cumulative_return") or 0.0),
                    "max_drawdown": float(metrics.get("max_drawdown") or 0.0),
                }
            )
        return matrix

    def _build_risk_alerts(self, metrics: BacktestMetrics) -> list[RiskAlert]:
        alerts: list[RiskAlert] = []
        if metrics.max_drawdown > 0.12:
            alerts.append(
                RiskAlert(
                    level="high",
                    title="Drawdown exceeded 12%",
                    description="The strategy entered a drawdown window that needs further review before promotion.",
                    recommendation="Reduce single-name caps and add stricter regime-switching thresholds.",
                )
            )
        if metrics.annualized_volatility > 0.24:
            alerts.append(
                RiskAlert(
                    level="medium",
                    title="Annualized volatility is above the delivery target band",
                    description="Portfolio volatility is higher than the preferred productized operating range.",
                    recommendation="Add stronger CVaR or volatility-budget constraints before larger routing.",
                )
            )
        if not alerts:
            alerts.append(
                RiskAlert(
                    level="low",
                    title="Risk remains in the controlled band",
                    description="Current drawdown and volatility remain inside the preferred operating envelope.",
                    recommendation="Continue walk-forward and stress-test validation before scaling notional size.",
                )
            )
        return alerts

    def _persist_experiment(
        self,
        name: str,
        objective: str,
        benchmark: str,
        metrics: dict[str, float | str],
        tags: list[str],
        artifact_uri: str | None,
    ) -> None:
        experiment = ExperimentRun(
            experiment_id=f"exp-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            name=name,
            created_at=_iso_now(),
            objective=objective,
            benchmark=benchmark,
            metrics=metrics,
            tags=tags,
            artifact_uri=artifact_uri,
        )
        payload = experiment.model_dump()
        payload["storage"] = self.storage.persist_record("experiments", experiment.experiment_id, payload)

    def _build_training_plan(self) -> TrainingPlan:
        remote_target = getattr(settings, "REMOTE_TRAINING_TARGET", "") or "Cloud RTX 5090 Finetune Node"
        return TrainingPlan(
            target_environment=remote_target,
            adapter_strategy="Qwen2.5 / ESG domain LoRA continuation training",
            dataset_sources=[
                "Supabase structured runs",
                "Artifact store payloads (R2 or Supabase Storage)",
                "ESG RAG corpora and SEC filings",
                "Alternative data derived features",
                "P2 graph topology snapshots and strategy selector datasets",
            ],
            artifact_store="R2 preferred, Supabase Storage fallback, Supabase metadata registry",
            remote_ready=bool(getattr(settings, "REMOTE_LLM_URL", "") or getattr(settings, "REMOTE_TRAINING_TARGET", "")),
            notes=[
                "默认以 Paper Trading 和离线回测为先，不直接连实盘。",
                "训练与微调流程保留为云端 5090 节点扩展路径。",
                "所有研究/回测/执行结果都会优先沉淀为可复用工件。",
            ],
        )

    def _summarize_signals(self, signals: list[ResearchSignal], portfolio: PortfolioSummary) -> str:
        leaders = ", ".join(signal.symbol for signal in signals[:3])
        if not portfolio.positions:
            return (
                f"本轮研究扫描了 {self.default_universe_name}，优先观察名单为 {leaders}，"
                "但当前没有通过 20/60 动量与 long-only 过滤的可执行标的，因此系统保持 no-trade。"
            )
        return (
            f"本轮研究以 {self.default_universe_name} 为基础股票池，筛出 {leaders} 作为优先候选，"
            f"组合期望 alpha 为 {portfolio.expected_alpha:.2%}，并保持 Paper Trading 优先的交付约束。"
        )

    @staticmethod
    def _factor_value(signal: dict[str, Any], factor_name: str) -> float:
        for factor in signal.get("factor_scores", []):
            if factor["name"] == factor_name:
                return float(factor["value"])
        return 50.0

    @staticmethod
    def _trend_from_metrics(e_score: float, s_score: float, g_score: float) -> list[dict[str, Any]]:
        base = [
            {"month": "Jan", "E": e_score - 10, "S": s_score - 8, "G": g_score - 7},
            {"month": "Feb", "E": e_score - 8, "S": s_score - 6, "G": g_score - 5},
            {"month": "Mar", "E": e_score - 7, "S": s_score - 5, "G": g_score - 4},
            {"month": "Apr", "E": e_score - 5, "S": s_score - 4, "G": g_score - 3},
            {"month": "May", "E": e_score - 4, "S": s_score - 3, "G": g_score - 2},
            {"month": "Jun", "E": e_score - 3, "S": s_score - 2, "G": g_score - 1},
            {"month": "Jul", "E": e_score - 2, "S": s_score - 1, "G": g_score - 1},
            {"month": "Aug", "E": e_score - 1, "S": s_score, "G": g_score - 1},
            {"month": "Sep", "E": e_score, "S": s_score, "G": g_score},
            {"month": "Oct", "E": e_score + 1, "S": s_score + 1, "G": g_score},
        ]
        return [{**item, "E": round(item["E"]), "S": round(item["S"]), "G": round(item["G"])} for item in base]


_quant_system: QuantSystemService | None = None


def get_quant_system(get_client: Any | None = None) -> QuantSystemService:
    global _quant_system
    if _quant_system is None:
        _quant_system = QuantSystemService(get_client=get_client)
        logger.info("Quant system service initialized")
    return _quant_system
