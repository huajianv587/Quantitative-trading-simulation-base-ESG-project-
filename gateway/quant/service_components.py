from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any

from gateway.config import settings


@dataclass
class MarketDataComponent:
    owner: Any

    def provider_order(self) -> list[str]:
        provider_order = getattr(self.owner.market_data, "provider_order", None)
        if isinstance(provider_order, (list, tuple)):
            normalized = [str(item or "").strip().lower() for item in provider_order if str(item or "").strip()]
            if normalized:
                return normalized
        configured = str(getattr(settings, "MARKET_DATA_PROVIDER", "twelvedata,alpaca,yfinance") or "")
        fallback = [item.strip().lower() for item in configured.split(",") if item.strip()]
        return fallback or ["twelvedata", "alpaca", "yfinance"]

    def daily_bars(self, symbol: str, **kwargs):
        getter = self.owner.market_data.get_daily_bars
        try:
            signature = inspect.signature(getter)
        except (TypeError, ValueError):
            signature = None
        if signature is not None:
            accepted = {
                name
                for name, parameter in signature.parameters.items()
                if parameter.kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
            }
            filtered_kwargs = {name: value for name, value in kwargs.items() if name in accepted and value is not None}
            return getter(symbol, **filtered_kwargs)
        return getter(
            symbol,
            limit=kwargs.get("limit", 180),
            force_refresh=bool(kwargs.get("force_refresh", False)),
        )

    def status(self) -> dict[str, Any]:
        return self.owner.market_data.status()


@dataclass
class DashboardComponent:
    owner: Any

    def overview(self) -> dict[str, Any]:
        return self.owner.build_platform_overview()

    def summary(self, provider: str = "auto") -> dict[str, Any]:
        return self.owner.build_dashboard_summary(provider=provider)

    def secondary(self, provider: str = "auto") -> dict[str, Any]:
        return self.owner.build_dashboard_secondary(provider=provider)

    def chart(self, *, symbol: str | None = None, timeframe: str = "1D", provider: str = "auto") -> dict[str, Any]:
        return self.owner.build_dashboard_chart(symbol=symbol, timeframe=timeframe, provider=provider)


@dataclass
class ExecutionComponent:
    owner: Any

    def notional_limits(self, mode: str | None) -> dict[str, Any]:
        normalized_mode = self.owner._normalize_broker_mode(mode)
        if normalized_mode == "live":
            broker_limit = float(getattr(settings, "ALPACA_LIVE_MAX_ORDER_NOTIONAL", 1.0) or 1.0)
            execution_limit = float(getattr(settings, "EXECUTION_LIVE_MAX_NOTIONAL_PER_ORDER", 1.0) or 1.0)
            daily_limit = float(getattr(settings, "EXECUTION_LIVE_MAX_DAILY_NOTIONAL", 5.0) or 5.0)
        else:
            broker_limit = float(
                getattr(
                    settings,
                    "ALPACA_PAPER_MAX_ORDER_NOTIONAL",
                    getattr(settings, "ALPACA_MAX_ORDER_NOTIONAL", 2500.0),
                )
                or 2500.0
            )
            execution_limit = float(
                getattr(
                    settings,
                    "EXECUTION_PAPER_MAX_NOTIONAL_PER_ORDER",
                    getattr(settings, "EXECUTION_MAX_NOTIONAL_PER_ORDER", 2500.0),
                )
                or 2500.0
            )
            daily_limit = None
        return {
            "mode": normalized_mode,
            "broker_max_order_notional": round(max(broker_limit, 0.0), 2),
            "execution_max_order_notional": round(max(execution_limit, 0.0), 2),
            "effective_per_order_notional": round(max(min(broker_limit, execution_limit), 0.0), 2),
            "daily_notional_limit": None if daily_limit is None else round(max(daily_limit, 0.0), 2),
        }

    def create_plan(self, **kwargs) -> dict[str, Any]:
        return self.owner.create_execution_plan(**kwargs)

    def controls(self) -> dict[str, Any]:
        return self.owner.get_execution_controls()

    def monitor(self, **kwargs) -> dict[str, Any]:
        return self.owner.build_execution_monitor(**kwargs)


@dataclass
class PaperWorkflowComponent:
    owner: Any

    def gate_thresholds(self) -> dict[str, Any]:
        return {
            "window_trading_days": int(getattr(settings, "PAPER_GATE_WINDOW_TRADING_DAYS", 60) or 60),
            "min_valid_days": int(getattr(settings, "PAPER_GATE_MIN_VALID_DAYS", 40) or 40),
            "min_net_return": float(getattr(settings, "PAPER_GATE_MIN_NET_RETURN", 0.0) or 0.0),
            "min_excess_return": float(getattr(settings, "PAPER_GATE_MIN_EXCESS_RETURN", 0.0) or 0.0),
            "min_sharpe": float(getattr(settings, "PAPER_GATE_MIN_SHARPE", 0.5) or 0.5),
            "max_drawdown": float(getattr(settings, "PAPER_GATE_MAX_DRAWDOWN", 0.08) or 0.08),
            "max_drawdown_underperformance": float(
                getattr(settings, "PAPER_GATE_MAX_DRAWDOWN_UNDERPERFORMANCE", 0.03) or 0.03
            ),
            "require_paper_evidence": bool(getattr(settings, "PAPER_GATE_REQUIRE_PAPER_EVIDENCE", True)),
            "benchmark": self.owner.default_benchmark,
        }

    def run_strategy_workflow(self, **kwargs) -> dict[str, Any]:
        return self.owner.run_hybrid_paper_strategy_workflow(**kwargs)

    def performance_report(self, **kwargs) -> dict[str, Any]:
        return self.owner.build_paper_performance_report(**kwargs)

    def promotion_report(self, **kwargs) -> dict[str, Any]:
        return self.owner.build_promotion_report(**kwargs)

    def observability(self, **kwargs) -> dict[str, Any]:
        return self.owner.build_paper_workflow_observability(**kwargs)


@dataclass
class QuantServiceComponents:
    market_data: MarketDataComponent
    dashboard: DashboardComponent
    execution: ExecutionComponent
    paper_workflow: PaperWorkflowComponent

    @classmethod
    def from_owner(cls, owner: Any) -> "QuantServiceComponents":
        return cls(
            market_data=MarketDataComponent(owner),
            dashboard=DashboardComponent(owner),
            execution=ExecutionComponent(owner),
            paper_workflow=PaperWorkflowComponent(owner),
        )
