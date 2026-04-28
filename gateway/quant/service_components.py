from __future__ import annotations

import hashlib
import inspect
from dataclasses import dataclass
from typing import Any

from gateway.config import settings
from gateway.quant.models import ExecutionOrder, PortfolioPosition, PortfolioSummary, ResearchSignal
from gateway.quant.p2_decision import P2_STRATEGY_PROFILES


def _stable_seed(*parts: str) -> int:
    raw = "::".join(parts).encode("utf-8")
    return int(hashlib.sha256(raw).hexdigest()[:8], 16)


def _bounded(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


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
class PortfolioConstructionComponent:
    owner: Any

    def build(
        self,
        signals: list[ResearchSignal],
        capital_base: float,
        benchmark: str,
        *,
        allow_watchlist_fallback: bool = False,
    ) -> PortfolioSummary:
        active_strategy = next(
            (signal.selector_strategy for signal in signals if signal.selector_strategy in P2_STRATEGY_PROFILES),
            "balanced_quality_growth",
        )
        strategy_profile = P2_STRATEGY_PROFILES.get(active_strategy, P2_STRATEGY_PROFILES["balanced_quality_growth"])
        decision_floor = max(
            float(getattr(settings, "P2_DECISION_MIN_SCORE", 0.54) or 0.54),
            float(strategy_profile["paper_gate_min_decision_score"]),
        )
        candidate_status = "ready"
        long_candidates = [
            signal
            for signal in signals
            if signal.action == "long"
            and (signal.predicted_drawdown_20d is None or signal.predicted_drawdown_20d < 0.28)
            and (signal.predicted_volatility_10d is None or signal.predicted_volatility_10d < 0.38)
            and (signal.decision_score is None or signal.decision_score >= decision_floor)
            and (
                signal.graph_contagion_risk is None
                or signal.graph_contagion_risk < float(getattr(settings, "P2_GRAPH_CONTAGION_LIMIT", 0.62) or 0.62)
            )
        ][: int(strategy_profile["max_positions"])]
        if allow_watchlist_fallback and not long_candidates:
            long_candidates = [
                signal
                for signal in signals
                if signal.action != "short"
                and signal.overall_score >= 50
                and (signal.predicted_drawdown_20d is None or signal.predicted_drawdown_20d < 0.32)
                and (signal.predicted_volatility_10d is None or signal.predicted_volatility_10d < 0.42)
                and (signal.graph_contagion_risk is None or signal.graph_contagion_risk < 0.78)
            ][: max(1, min(int(strategy_profile["max_positions"]), 4))]
            if long_candidates:
                candidate_status = "watchlist_fallback"
        if allow_watchlist_fallback and not long_candidates:
            long_candidates = [
                signal
                for signal in signals
                if signal.action == "neutral"
                and signal.confidence >= 0.88
                and signal.overall_score >= 40
                and (signal.predicted_drawdown_20d is None or signal.predicted_drawdown_20d < 0.36)
                and (signal.predicted_volatility_10d is None or signal.predicted_volatility_10d < 0.46)
                and (signal.graph_contagion_risk is None or signal.graph_contagion_risk < 0.82)
            ][: max(1, min(int(strategy_profile["max_positions"]), 4))]
            if long_candidates:
                candidate_status = "confidence_fallback"
        minimum_target_positions = max(1, min(int(strategy_profile["max_positions"]), 3))
        if allow_watchlist_fallback and 0 < len(long_candidates) < minimum_target_positions:
            existing_symbols = {signal.symbol for signal in long_candidates}
            breadth_candidates = [
                signal
                for signal in signals
                if signal.symbol not in existing_symbols
                and signal.action != "short"
                and signal.overall_score >= 48
                and (signal.predicted_drawdown_20d is None or signal.predicted_drawdown_20d < 0.34)
                and (signal.predicted_volatility_10d is None or signal.predicted_volatility_10d < 0.45)
            ]
            needed = minimum_target_positions - len(long_candidates)
            if needed > 0 and breadth_candidates:
                long_candidates.extend(breadth_candidates[:needed])
                candidate_status = "breadth_fallback"
        if not long_candidates:
            return PortfolioSummary(
                strategy_name=f"ESG P2 Decision Stack - {strategy_profile['label']}",
                benchmark=benchmark,
                capital_base=capital_base,
                gross_exposure=0.0,
                net_exposure=0.0,
                turnover_estimate=0.0,
                expected_alpha=0.0,
                positions=[],
                constraints={
                    "max_single_name_weight": 0.26,
                    "max_sector_tilt": 0.20,
                    "esg_floor": 60.0,
                    "execution_mode": "paper_first",
                    "signal_filter": "long_only",
                    "status": "no_trade",
                    "candidate_mode": "strict",
                    "regime_overlay": "enabled",
                    "p1_stack": "active" if self.owner.p1_suite.available() else "heuristic",
                    "p2_strategy_selector": active_strategy,
                    "graph_overlay": "enabled",
                    "decision_min_score": round(decision_floor, 4),
                },
            )

        raw_scores: list[float] = []
        for signal in long_candidates:
            baseline_return = float(signal.expected_return)
            decision_score = float(signal.decision_score if signal.decision_score is not None else signal.p1_stack_score or signal.alpha_model_score or 0.5)
            selector_priority = float(signal.selector_priority_score if signal.selector_priority_score is not None else decision_score)
            size_multiplier = _bounded(
                float(signal.bandit_size_multiplier if signal.bandit_size_multiplier is not None else 1.0),
                float(getattr(settings, "P2_BANDIT_SIZE_MULTIPLIER_MIN", 0.55) or 0.55),
                float(getattr(settings, "P2_BANDIT_SIZE_MULTIPLIER_MAX", 1.35) or 1.35),
            )
            p1_score = float(
                signal.p1_stack_score
                if signal.p1_stack_score is not None
                else signal.alpha_model_score
                if signal.alpha_model_score is not None
                else _bounded(signal.overall_score / 100.0, 0.0, 1.0)
            )
            predicted_return_5d = float(
                signal.predicted_return_5d
                if signal.predicted_return_5d is not None
                else max(baseline_return * 1.8, baseline_return)
            )
            blended_return = max(
                baseline_return * 0.5,
                0.55 * baseline_return + 0.45 * predicted_return_5d,
            )
            predicted_volatility = float(
                signal.predicted_volatility_10d
                if signal.predicted_volatility_10d is not None
                else _bounded(0.08 + signal.risk_score / 250.0, 0.06, 0.38)
            )
            predicted_drawdown = float(
                signal.predicted_drawdown_20d
                if signal.predicted_drawdown_20d is not None
                else _bounded(0.04 + signal.risk_score / 320.0, 0.04, 0.32)
            )
            regime_multiplier = {
                "risk_on": 1.08,
                "neutral": 0.95,
                "risk_off": 0.72,
            }.get(str(signal.regime_label or "neutral").lower(), 0.95)
            graph_diversification = float(signal.graph_diversification_score if signal.graph_diversification_score is not None else 0.52)
            graph_contagion = float(signal.graph_contagion_risk if signal.graph_contagion_risk is not None else 0.28)
            graph_centrality = float(signal.graph_centrality if signal.graph_centrality is not None else 0.35)
            risk_penalty = _bounded(
                1.0 - predicted_volatility * 0.7 - predicted_drawdown * 0.65 - graph_contagion * 0.22,
                0.18,
                1.0,
            )
            diversification_bonus = _bounded(0.82 + graph_diversification * 0.22 - graph_centrality * 0.08, 0.72, 1.08)
            expected_edge = max(blended_return, 0.0) * 420.0
            raw_scores.append(
                max(
                    0.01,
                    size_multiplier
                    * regime_multiplier
                    * diversification_bonus
                    * risk_penalty
                    * (
                        decision_score * 42.0
                        + selector_priority * 18.0
                        + p1_score * 18.0
                        + expected_edge * 0.26
                        + signal.confidence * 10.0
                    ),
                )
            )
        total_score = sum(raw_scores)
        positions: list[PortfolioPosition] = []

        for signal, raw in zip(long_candidates, raw_scores):
            baseline_return = float(signal.expected_return)
            predicted_return_5d = float(
                signal.predicted_return_5d
                if signal.predicted_return_5d is not None
                else max(baseline_return * 1.8, baseline_return)
            )
            blended_return = max(
                baseline_return * 0.5,
                0.55 * baseline_return + 0.45 * predicted_return_5d,
            )
            predicted_volatility = float(
                signal.predicted_volatility_10d
                if signal.predicted_volatility_10d is not None
                else _bounded(0.08 + signal.risk_score / 250.0, 0.06, 0.38)
            )
            predicted_drawdown = float(
                signal.predicted_drawdown_20d
                if signal.predicted_drawdown_20d is not None
                else _bounded(0.04 + signal.risk_score / 320.0, 0.04, 0.32)
            )
            decision_score = float(signal.decision_score if signal.decision_score is not None else signal.p1_stack_score or signal.alpha_model_score or 0.5)
            size_multiplier = _bounded(
                float(signal.bandit_size_multiplier if signal.bandit_size_multiplier is not None else 1.0),
                float(getattr(settings, "P2_BANDIT_SIZE_MULTIPLIER_MIN", 0.55) or 0.55),
                float(getattr(settings, "P2_BANDIT_SIZE_MULTIPLIER_MAX", 1.35) or 1.35),
            )
            execution_delay_seconds = int(
                _bounded(
                    float(signal.bandit_execution_delay_seconds if signal.bandit_execution_delay_seconds is not None else 0.0),
                    0.0,
                    float(getattr(settings, "P2_BANDIT_EXECUTION_DELAY_MAX_SECONDS", 900) or 900),
                )
            )
            target_weight = round(
                _bounded(
                    raw / total_score,
                    0.05,
                    min(float(strategy_profile["max_single_name_weight"]), float(getattr(settings, "EXECUTION_SINGLE_NAME_WEIGHT_CAP", 0.26) or 0.26)),
                ),
                4,
            )
            positions.append(
                PortfolioPosition(
                    symbol=signal.symbol,
                    company_name=signal.company_name,
                    weight=target_weight,
                    expected_return=round(blended_return, 6),
                    risk_budget=round(_bounded(1.0 - predicted_volatility * 0.85 - predicted_drawdown * 0.45, 0.18, 0.92), 4),
                    score=round(decision_score * 100.0, 4),
                    side="long",
                    thesis=(
                        f"{signal.thesis} | Regime {signal.regime_label or 'neutral'}"
                        f" | Strategy {signal.selector_strategy or active_strategy}"
                        f" | Blend {blended_return:.2%}"
                        f" | Decision {decision_score:.2f}"
                        f" | Model5D {predicted_return_5d:.2%}"
                        f" | DD20 {predicted_drawdown:.2%}"
                    ),
                    strategy_bucket=signal.selector_strategy or active_strategy,
                    decision_score=round(decision_score, 6),
                    regime_posture=str(signal.regime_label or "neutral"),
                    size_multiplier=round(size_multiplier, 4),
                    execution_tactic=str(signal.bandit_execution_style or "adaptive"),
                    execution_delay_seconds=execution_delay_seconds,
                    alpha_engine=str(signal.alpha_engine or active_strategy),
                )
            )

        single_name_cap = min(
            float(strategy_profile["max_single_name_weight"]),
            float(getattr(settings, "EXECUTION_SINGLE_NAME_WEIGHT_CAP", 0.26) or 0.26),
        )
        sector_cap = float(getattr(settings, "PORTFOLIO_DEFAULT_SECTOR_CAP", 0.20) or 0.20)
        optimized_weights, allocation_meta = self.owner._allocate_objective_weights(
            positions,
            {signal.symbol: signal for signal in long_candidates},
            objective_key="maximum_sharpe",
            max_position_weight=single_name_cap,
            max_sector_concentration=sector_cap,
        )
        if optimized_weights and len(optimized_weights) == len(positions):
            positions = [
                position.model_copy(update={"weight": round(weight, 4)})
                for position, weight in zip(positions, optimized_weights)
            ]

        total_weight = sum(position.weight for position in positions)
        normalized_positions: list[PortfolioPosition] = []
        for position in positions:
            normalized = position.model_copy(update={"weight": round(position.weight / total_weight, 4)})
            normalized = normalized.model_copy(
                update={
                    "execution_tactic": normalized.execution_tactic or self.owner._select_execution_tactic(normalized),
                }
            )
            slippage_bps = self.owner._estimate_order_slippage_bps(normalized, capital_base)
            impact_bps = self.owner._estimate_order_impact_bps(normalized, capital_base)
            fill_probability = self.owner._estimate_order_fill_probability(
                normalized,
                capital_base=capital_base,
                slippage_bps=slippage_bps,
                impact_bps=impact_bps,
            )
            normalized_positions.append(
                normalized.model_copy(
                    update={
                        "estimated_slippage_bps": slippage_bps,
                        "estimated_impact_bps": impact_bps,
                        "expected_fill_probability": fill_probability,
                    }
                )
            )
        gross_exposure = round(sum(position.weight for position in normalized_positions), 4)
        expected_alpha = round(sum(position.weight * position.expected_return for position in normalized_positions), 4)
        turnover_estimate = round(float(strategy_profile["turnover_budget_bps"]) / 10_000.0 + len(normalized_positions) * 0.008, 4)

        return PortfolioSummary(
            strategy_name=f"ESG P2 Decision Stack - {strategy_profile['label']}",
            benchmark=benchmark,
            capital_base=capital_base,
            gross_exposure=gross_exposure,
            net_exposure=gross_exposure,
            turnover_estimate=turnover_estimate,
            expected_alpha=expected_alpha,
            positions=normalized_positions,
            constraints={
                "max_single_name_weight": round(single_name_cap, 4),
                "max_sector_tilt": round(sector_cap, 4),
                "esg_floor": 60.0,
                "execution_mode": "paper_first",
                "candidate_mode": candidate_status,
                "signal_filter": {
                    "ready": "long_only",
                    "watchlist_fallback": "neutral_watchlist_fallback",
                    "breadth_fallback": "neutral_breadth_fallback",
                    "confidence_fallback": "high_confidence_neutral_fallback",
                }.get(candidate_status, "neutral_watchlist_fallback"),
                "status": candidate_status,
                "regime_overlay": "enabled",
                "p1_stack": "active" if self.owner.p1_suite.available() else "heuristic",
                "p2_strategy_selector": active_strategy,
                "graph_overlay": "enabled",
                "allocator": allocation_meta.get("mode", "heuristic"),
                "allocator_history_rows": float(allocation_meta.get("history_rows", 0) or 0),
                "allocator_average_correlation": float(allocation_meta.get("average_correlation", 0.0) or 0.0),
                "decision_min_score": round(decision_floor, 4),
            },
        )


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
    portfolio: PortfolioConstructionComponent
    paper_workflow: PaperWorkflowComponent

    @classmethod
    def from_owner(cls, owner: Any) -> "QuantServiceComponents":
        return cls(
            market_data=MarketDataComponent(owner),
            dashboard=DashboardComponent(owner),
            execution=ExecutionComponent(owner),
            portfolio=PortfolioConstructionComponent(owner),
            paper_workflow=PaperWorkflowComponent(owner),
        )
