from __future__ import annotations

import hashlib
import inspect
from dataclasses import dataclass
from typing import Any

from gateway.config import settings
from gateway.quant.models import ExecutionOrder, PortfolioPosition


def _stable_seed(*parts: str) -> int:
    raw = "::".join(parts).encode("utf-8")
    return int(hashlib.sha256(raw).hexdigest()[:8], 16)


def coerce_float(value: Any) -> float | None:
    if value in {None, ""}:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def build_alpaca_order_payload(
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
    symbol = str(order.get("symbol", "")).upper().strip()
    payload: dict[str, Any] = {
        "symbol": symbol,
        "side": order.get("side", "buy"),
        "type": normalized_order_type,
        "time_in_force": normalized_tif,
        "client_order_id": order.get("client_order_id") or f"{execution_id}-{symbol.lower()}-{index + 1}",
    }
    fractionable = bool(asset.get("fractionable"))
    if normalized_order_type == "market" and fractionable:
        payload["notional"] = f"{capped_notional:.2f}"
    else:
        payload["qty"] = str(max(1, int(order.get("quantity") or 1)))

    if normalized_order_type == "limit":
        payload["limit_price"] = f"{float(order.get('limit_price') or 0):.2f}"
        if extended_hours and normalized_tif == "day":
            payload["extended_hours"] = True

    return payload


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

    @staticmethod
    def safe_float(value: Any) -> float | None:
        return coerce_float(value)

    def collect_warnings(
        self,
        *,
        account_snapshot: dict[str, Any],
        market_clock: dict[str, Any] | None,
        submit_orders: bool,
    ) -> list[str]:
        warnings: list[str] = []
        cash = self.safe_float(account_snapshot.get("cash"))
        equity = self.safe_float(account_snapshot.get("equity"))

        if cash is not None and cash < 0:
            warnings.append(
                "Account cash is negative. Review existing paper positions and margin usage before increasing exposure."
            )
        if equity is not None and equity <= 0:
            warnings.append("Account equity is non-positive. Broker execution should be paused until the paper account is reset.")
        if account_snapshot.get("pattern_day_trader"):
            warnings.append("Account is flagged as pattern_day_trader. Intraday turnover should stay controlled.")
        if market_clock and market_clock.get("is_open") is False:
            next_open = market_clock.get("next_open") or "the next session"
            if submit_orders:
                warnings.append(f"Market is currently closed. DAY paper orders may remain accepted until {next_open}.")
            else:
                warnings.append(f"Market is currently closed. The next session opens at {next_open}.")
        return warnings

    def build_orders(
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
        orders: list[ExecutionOrder] = []
        for index, position in enumerate(positions):
            ref_price = round(40 + position.weight * 500 + (_stable_seed(position.symbol) % 100) / 3, 2)
            quantity = max(1, int((capital_base * position.weight) / ref_price))
            tracking_id = self.owner._build_order_tracking_id(execution_id, position.symbol, index)
            execution_tactic = self.owner._select_execution_tactic(position)
            slippage_bps = position.estimated_slippage_bps or self.owner._estimate_order_slippage_bps(position, capital_base)
            impact_bps = position.estimated_impact_bps or self.owner._estimate_order_impact_bps(position, capital_base)
            fill_probability = position.expected_fill_probability or self.owner._estimate_order_fill_probability(
                position,
                capital_base=capital_base,
                slippage_bps=float(slippage_bps),
                impact_bps=float(impact_bps),
            )
            orders.append(
                ExecutionOrder(
                    symbol=position.symbol,
                    side="buy" if position.side == "long" else "sell",
                    quantity=quantity,
                    target_weight=round(position.weight, 4),
                    limit_price=ref_price,
                    venue=broker_id,
                    rationale=position.thesis,
                    order_type=order_type,
                    time_in_force=time_in_force,
                    notional=per_order_notional,
                    client_order_id=tracking_id,
                    status="validated",
                    expected_fill_probability=round(float(fill_probability), 4),
                    estimated_slippage_bps=round(float(slippage_bps), 2),
                    estimated_impact_bps=round(float(impact_bps), 2),
                    execution_tactic=execution_tactic,
                    execution_delay_seconds=int(position.execution_delay_seconds or 0),
                    canary_bucket=self.owner._assign_canary_bucket(execution_id, position.symbol),
                )
            )
        return orders

    def submit_alpaca_paper_orders(
        self,
        *,
        payload: dict[str, Any],
        capped_max_orders: int,
        capped_notional: float,
        normalized_order_type: str,
        normalized_tif: str,
        extended_hours: bool,
    ) -> None:
        journal = payload.get("journal") or self.owner._build_execution_journal(
            execution_id=payload["execution_id"],
            broker_id="alpaca",
            mode=payload.get("mode", "paper"),
            orders=payload.get("orders", []),
            risk_summary=payload.get("warnings", []),
        )
        payload["journal"] = journal
        self.owner._submit_broker_orders(
            adapter=self.owner._resolve_broker("alpaca"),
            payload=payload,
            journal=journal,
            capped_max_orders=capped_max_orders,
            capped_notional=capped_notional,
            normalized_order_type=normalized_order_type,
            normalized_tif=normalized_tif,
            extended_hours=extended_hours,
        )

    @staticmethod
    def build_alpaca_order_payload(**kwargs) -> dict[str, Any]:
        return build_alpaca_order_payload(**kwargs)

    def build_broker_order_payload(
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
        if broker_id == "alpaca":
            return self.build_alpaca_order_payload(
                execution_id=execution_id,
                order=order,
                asset=asset,
                index=index,
                capped_notional=capped_notional,
                normalized_order_type=normalized_order_type,
                normalized_tif=normalized_tif,
                extended_hours=extended_hours,
            )
        return {
            "symbol": order.get("symbol"),
            "side": order.get("side", "buy"),
            "type": normalized_order_type,
            "time_in_force": normalized_tif,
            "qty": str(max(1, int(order.get("quantity") or 1))),
            "client_order_id": order.get("client_order_id")
            or self.owner._build_order_tracking_id(execution_id, str(order.get("symbol")), index),
        }


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
