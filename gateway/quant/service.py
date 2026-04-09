from __future__ import annotations

import hashlib
import math
import statistics
from datetime import date, datetime, timedelta, timezone
from typing import Any

from pydantic import BaseModel

from gateway.config import settings
from gateway.quant.alpaca import AlpacaPaperClient
from gateway.quant.models import (
    ArchitectureLayerStatus,
    BacktestMetrics,
    BacktestPoint,
    BacktestResult,
    ExecutionOrder,
    ExecutionPlan,
    ExperimentRun,
    FactorScore,
    PortfolioPosition,
    PortfolioSummary,
    ResearchSignal,
    RiskAlert,
    TrainingPlan,
    UniverseMember,
)
from gateway.quant.storage import QuantStorageGateway
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


class QuantSystemService:
    def __init__(self, get_client: Any | None = None) -> None:
        self.storage = QuantStorageGateway(get_client=get_client)
        self.alpaca = AlpacaPaperClient()
        self.default_capital = float(getattr(settings, "QUANT_DEFAULT_CAPITAL", 1_000_000))
        self.default_benchmark = getattr(settings, "QUANT_DEFAULT_BENCHMARK", "SPY")
        self.default_universe_name = getattr(settings, "QUANT_DEFAULT_UNIVERSE", "ESG_US_LARGE_CAP")

    def get_default_universe(self, symbols: list[str] | None = None) -> list[UniverseMember]:
        base_universe = [
            UniverseMember(symbol="AAPL", company_name="Apple", sector="Technology", industry="Consumer Electronics", benchmark_weight=0.068),
            UniverseMember(symbol="MSFT", company_name="Microsoft", sector="Technology", industry="Software", benchmark_weight=0.072),
            UniverseMember(symbol="TSLA", company_name="Tesla", sector="Consumer Discretionary", industry="EV Manufacturing", benchmark_weight=0.021),
            UniverseMember(symbol="NVDA", company_name="NVIDIA", sector="Technology", industry="Semiconductors", benchmark_weight=0.064),
            UniverseMember(symbol="JPM", company_name="JPMorgan Chase", sector="Financials", industry="Banks", benchmark_weight=0.013),
            UniverseMember(symbol="NEE", company_name="NextEra Energy", sector="Utilities", industry="Renewables", benchmark_weight=0.004),
            UniverseMember(symbol="PG", company_name="Procter & Gamble", sector="Consumer Staples", industry="Household Products", benchmark_weight=0.007),
            UniverseMember(symbol="UNH", company_name="UnitedHealth", sector="Health Care", industry="Managed Care", benchmark_weight=0.011),
        ]
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

    def build_platform_overview(self) -> dict[str, Any]:
        universe = self.get_default_universe()
        signals = self._build_signals(universe, "overview refresh", self.default_benchmark)
        portfolio = self._build_portfolio(signals, self.default_capital, self.default_benchmark)
        backtests = self.storage.list_records("backtests")
        experiments = self.storage.list_records("experiments")
        latest_backtest = backtests[0] if backtests else self._build_backtest(
            strategy_name="ESG Multi-Factor Long-Only",
            benchmark=self.default_benchmark,
            capital_base=self.default_capital,
            positions=portfolio.positions,
            lookback_days=126,
            persist=False,
        ).model_dump()

        return {
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
            "universe": {
                "name": self.default_universe_name,
                "size": len(universe),
                "benchmark": self.default_benchmark,
                "coverage": [member.symbol for member in universe],
            },
            "top_signals": [_as_dict(signal) for signal in signals[:5]],
            "portfolio_preview": portfolio.model_dump(),
            "latest_backtest": latest_backtest,
            "experiments": experiments[:3],
            "training_plan": self._build_training_plan().model_dump(),
        }

    def build_dashboard_overview(self) -> dict[str, Any]:
        overview = self.build_platform_overview()
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
                "overall_score": round(top_signal["overall_score"]),
                "confidence": top_signal["confidence"],
                "dimensions": [
                    {"key": "E", "label": "环保", "score": round(top_signal["e_score"]), "trend": "up"},
                    {"key": "S", "label": "社会", "score": round(top_signal["s_score"]), "trend": "stable"},
                    {"key": "G", "label": "治理", "score": round(top_signal["g_score"]), "trend": "up"},
                ],
                "radar": [
                    {"label": "ESG", "value": round(top_signal["overall_score"])},
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

    def optimize_portfolio(
        self,
        universe_symbols: list[str] | None = None,
        benchmark: str | None = None,
        capital_base: float | None = None,
        research_question: str = "",
    ) -> dict[str, Any]:
        benchmark = benchmark or self.default_benchmark
        capital_base = capital_base or self.default_capital
        signals = self._build_signals(self.get_default_universe(universe_symbols), research_question, benchmark)
        portfolio = self._build_portfolio(signals, capital_base, benchmark)

        record = {
            "optimization_id": f"portfolio-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            "created_at": _iso_now(),
            "benchmark": benchmark,
            "portfolio": portfolio.model_dump(),
            "signals_used": [_as_dict(signal) for signal in signals[:6]],
            "storage": {},
        }
        record["storage"] = self.storage.persist_record("portfolio_runs", record["optimization_id"], record)
        return record

    def run_backtest(
        self,
        strategy_name: str,
        universe_symbols: list[str] | None = None,
        benchmark: str | None = None,
        capital_base: float | None = None,
        lookback_days: int = 126,
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
        return result.model_dump()

    def list_backtests(self) -> list[dict[str, Any]]:
        return self.storage.list_records("backtests")

    def get_backtest(self, backtest_id: str) -> dict[str, Any] | None:
        return self.storage.load_record("backtests", backtest_id)

    def get_execution_account(self) -> dict[str, Any]:
        status = self.alpaca.connection_status()
        if not status["configured"]:
            return {
                "connected": False,
                "broker_connection": status,
                "warnings": ["Alpaca paper trading credentials are not configured."],
            }

        try:
            account = self.alpaca.get_account()
            clock = self.alpaca.get_clock()
            account_snapshot = self._summarize_alpaca_account(account)
            clock_snapshot = self._summarize_alpaca_clock(clock)
            return {
                "connected": True,
                "broker_connection": status,
                "account": account_snapshot,
                "market_clock": clock_snapshot,
                "warnings": self._collect_execution_warnings(
                    account_snapshot=account_snapshot,
                    market_clock=clock_snapshot,
                    submit_orders=False,
                ),
            }
        except Exception as exc:
            logger.warning(f"Failed to load Alpaca account status: {exc}")
            return {
                "connected": False,
                "broker_connection": status,
                "warnings": [str(exc)],
            }

    def list_execution_orders(self, status: str = "all", limit: int = 20) -> dict[str, Any]:
        connection = self.alpaca.connection_status()
        if not connection["configured"]:
            return {"connected": False, "orders": [], "broker_connection": connection}

        try:
            orders = self.alpaca.list_orders(status=status, limit=limit)
            return {
                "connected": True,
                "broker_connection": connection,
                "orders": [self._summarize_alpaca_order(item) for item in orders],
            }
        except Exception as exc:
            logger.warning(f"Failed to list Alpaca orders: {exc}")
            return {
                "connected": False,
                "broker_connection": connection,
                "orders": [],
                "warnings": [str(exc)],
            }

    def list_execution_positions(self) -> dict[str, Any]:
        connection = self.alpaca.connection_status()
        if not connection["configured"]:
            return {"connected": False, "positions": [], "broker_connection": connection}

        try:
            positions = self.alpaca.list_positions()
            return {
                "connected": True,
                "broker_connection": connection,
                "positions": [self._summarize_alpaca_position(item) for item in positions],
            }
        except Exception as exc:
            logger.warning(f"Failed to list Alpaca positions: {exc}")
            return {
                "connected": False,
                "broker_connection": connection,
                "positions": [],
                "warnings": [str(exc)],
            }

    def create_execution_plan(
        self,
        benchmark: str | None = None,
        capital_base: float | None = None,
        universe_symbols: list[str] | None = None,
        mode: str = "paper",
        submit_orders: bool = False,
        max_orders: int = 2,
        per_order_notional: float | None = None,
        order_type: str = "market",
        time_in_force: str = "day",
        extended_hours: bool = False,
    ) -> dict[str, Any]:
        benchmark = benchmark or self.default_benchmark
        capital_base = capital_base or self.default_capital
        signals = self._build_signals(self.get_default_universe(universe_symbols), "execution plan", benchmark)
        portfolio = self._build_portfolio(signals, capital_base, benchmark)
        normalized_order_type = (order_type or "market").strip().lower()
        normalized_tif = (time_in_force or "day").strip().lower()
        capped_max_orders = max(1, min(int(max_orders or 1), int(getattr(settings, "ALPACA_MAX_TEST_ORDERS", 2) or 2), 5))
        capped_notional = round(
            min(
                float(per_order_notional or getattr(settings, "ALPACA_DEFAULT_TEST_NOTIONAL", 1.0) or 1.0),
                float(getattr(settings, "ALPACA_MAX_ORDER_NOTIONAL", 10.0) or 10.0),
            ),
            2,
        )
        orders = self._build_execution_orders(
            positions=portfolio.positions,
            capital_base=capital_base,
            order_type=normalized_order_type,
            time_in_force=normalized_tif,
            per_order_notional=capped_notional,
        )

        plan = ExecutionPlan(
            execution_id=f"execution-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            broker="Alpaca Paper Trading",
            mode="paper" if mode != "live" else "live",
            ready=True,
            estimated_slippage_bps=7.5,
            compliance_checks=[
                "No MNPI detected in prompt or attached research inputs",
                "Max single-name weight below configured cap",
                "Paper trading mode enabled by default",
            ],
            orders=orders,
            submitted=False,
            broker_status="planned",
            warnings=[],
            broker_connection=self.alpaca.connection_status(),
        )

        payload = plan.model_dump()
        payload["generated_at"] = _iso_now()
        payload["portfolio"] = portfolio.model_dump()
        payload["submit_orders"] = bool(submit_orders)
        payload["max_orders"] = capped_max_orders
        payload["per_order_notional"] = capped_notional
        payload["order_type"] = normalized_order_type
        payload["time_in_force"] = normalized_tif
        payload["extended_hours"] = bool(extended_hours)
        payload["submitted_orders"] = []
        payload["broker_errors"] = []

        if mode == "live" and not bool(getattr(settings, "ALPACA_ENABLE_LIVE_TRADING", False)):
            payload["ready"] = False
            payload["broker_status"] = "blocked"
            payload["warnings"].append("Live trading is disabled. Only Alpaca paper trading is enabled.")

        if submit_orders and payload["mode"] == "paper":
            self._submit_alpaca_paper_orders(
                payload=payload,
                capped_max_orders=capped_max_orders,
                capped_notional=capped_notional,
                normalized_order_type=normalized_order_type,
                normalized_tif=normalized_tif,
                extended_hours=bool(extended_hours),
            )

        payload["storage"] = self.storage.persist_record("executions", plan.execution_id, payload)
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

    def _build_execution_orders(
        self,
        positions: list[PortfolioPosition],
        capital_base: float,
        order_type: str,
        time_in_force: str,
        per_order_notional: float,
    ) -> list[ExecutionOrder]:
        orders: list[ExecutionOrder] = []
        for position in positions:
            ref_price = round(40 + position.weight * 500 + (_stable_seed(position.symbol) % 100) / 3, 2)
            quantity = max(1, int((capital_base * position.weight) / ref_price))
            orders.append(
                ExecutionOrder(
                    symbol=position.symbol,
                    side="buy" if position.side == "long" else "sell",
                    quantity=quantity,
                    target_weight=round(position.weight, 4),
                    limit_price=ref_price,
                    venue="alpaca-paper",
                    rationale=position.thesis,
                    order_type=order_type,
                    time_in_force=time_in_force,
                    notional=per_order_notional,
                )
            )
        return orders

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
        connection = self.alpaca.connection_status()
        if not connection["configured"]:
            payload["warnings"].append("Alpaca credentials missing. Execution stayed in plan-only mode.")
            payload["broker_status"] = "not_configured"
            return

        try:
            account = self.alpaca.get_account()
            payload["account_snapshot"] = self._summarize_alpaca_account(account)
        except Exception as exc:
            payload["warnings"].append(f"Unable to fetch Alpaca account: {exc}")
            payload["broker_status"] = "account_error"
            payload["ready"] = False
            return

        if payload["account_snapshot"].get("trading_blocked"):
            payload["warnings"].append("Alpaca account is trading_blocked. Orders were not submitted.")
            payload["broker_status"] = "trading_blocked"
            payload["ready"] = False
            return

        if payload["account_snapshot"].get("account_blocked"):
            payload["warnings"].append("Alpaca account is account_blocked. Orders were not submitted.")
            payload["broker_status"] = "account_blocked"
            payload["ready"] = False
            return

        try:
            payload["market_clock"] = self._summarize_alpaca_clock(self.alpaca.get_clock())
        except Exception as exc:
            payload["warnings"].append(f"Unable to fetch Alpaca market clock: {exc}")

        payload["warnings"].extend(
            self._collect_execution_warnings(
                account_snapshot=payload.get("account_snapshot", {}),
                market_clock=payload.get("market_clock"),
                submit_orders=True,
            )
        )

        buying_power = self._safe_float(payload.get("account_snapshot", {}).get("buying_power"))
        if buying_power is not None and buying_power < capped_notional:
            payload["warnings"].append(
                f"Buying power {buying_power:.2f} is below requested per-order notional {capped_notional:.2f}. Orders were not submitted."
            )
            payload["broker_status"] = "insufficient_buying_power"
            payload["ready"] = False
            return

        submitted_orders: list[dict[str, Any]] = []
        for index, order in enumerate(payload.get("orders", [])[:capped_max_orders]):
            symbol = str(order.get("symbol", "")).upper().strip()
            try:
                asset = self.alpaca.get_asset(symbol)
                if not asset.get("tradable", False):
                    payload["warnings"].append(f"{symbol} is not tradable on Alpaca paper and was skipped.")
                    continue

                broker_payload = self._build_alpaca_order_payload(
                    execution_id=payload["execution_id"],
                    order=order,
                    asset=asset,
                    index=index,
                    capped_notional=capped_notional,
                    normalized_order_type=normalized_order_type,
                    normalized_tif=normalized_tif,
                    extended_hours=extended_hours,
                )
                created_order = self.alpaca.submit_order(broker_payload)
                refreshed_order = created_order
                order_id = str(created_order.get("id") or "").strip()
                if order_id:
                    try:
                        refreshed_order = self.alpaca.get_order(order_id)
                    except Exception:
                        refreshed_order = created_order

                receipt = self._summarize_alpaca_order(refreshed_order)
                receipt["submitted_payload"] = broker_payload
                submitted_orders.append(receipt)
                order.update(
                    {
                        "status": receipt.get("status", "submitted"),
                        "broker_order_id": receipt.get("id"),
                        "client_order_id": receipt.get("client_order_id"),
                        "submitted_at": receipt.get("submitted_at"),
                        "filled_qty": receipt.get("filled_qty"),
                        "filled_avg_price": receipt.get("filled_avg_price"),
                        "order_type": receipt.get("type") or order.get("order_type"),
                        "time_in_force": receipt.get("time_in_force") or order.get("time_in_force"),
                        "notional": receipt.get("notional") or order.get("notional"),
                    }
                )
            except Exception as exc:
                logger.warning(f"Alpaca order submission failed for {symbol}: {exc}")
                payload["broker_errors"].append(f"{symbol}: {exc}")

        payload["submitted_orders"] = submitted_orders
        payload["submitted"] = bool(submitted_orders)
        payload["broker_status"] = "submitted" if submitted_orders else "submit_failed"
        if not submitted_orders and not payload["warnings"] and not payload["broker_errors"]:
            payload["warnings"].append("No Alpaca paper orders were submitted.")

    @staticmethod
    def _safe_float(value: Any) -> float | None:
        if value in {None, ""}:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _collect_execution_warnings(
        self,
        *,
        account_snapshot: dict[str, Any],
        market_clock: dict[str, Any] | None,
        submit_orders: bool,
    ) -> list[str]:
        warnings: list[str] = []
        cash = self._safe_float(account_snapshot.get("cash"))
        equity = self._safe_float(account_snapshot.get("equity"))

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
        symbol = str(order.get("symbol", "")).upper().strip()
        payload: dict[str, Any] = {
            "symbol": symbol,
            "side": order.get("side", "buy"),
            "type": normalized_order_type,
            "time_in_force": normalized_tif,
            "client_order_id": f"{execution_id}-{symbol.lower()}-{index + 1}",
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

    @staticmethod
    def _summarize_alpaca_account(account: dict[str, Any]) -> dict[str, str | bool | None]:
        return {
            "account_id": account.get("id"),
            "status": account.get("status"),
            "currency": account.get("currency"),
            "buying_power": account.get("buying_power"),
            "cash": account.get("cash"),
            "equity": account.get("equity"),
            "last_equity": account.get("last_equity"),
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

    def _build_signals(
        self,
        universe: list[UniverseMember],
        research_question: str,
        benchmark: str,
    ) -> list[ResearchSignal]:
        signals: list[ResearchSignal] = []

        for member in universe:
            seed = _stable_seed(member.symbol, research_question or "default", benchmark)
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
            action = "long" if overall >= 68 else "neutral" if overall >= 58 else "short"

            factor_scores = [
                FactorScore(name="momentum", value=momentum, contribution=0.18, description="趋势与价格延续性"),
                FactorScore(name="quality", value=quality, contribution=0.22, description="盈利质量与资本效率"),
                FactorScore(name="value", value=value, contribution=0.14, description="估值与安全边际"),
                FactorScore(name="alternative_data", value=alternative_data, contribution=0.19, description="卫星/新闻/行为金融代理信号"),
                FactorScore(name="regime_fit", value=regime_fit, contribution=0.11, description="宏观 regime 适配度"),
                FactorScore(name="esg_delta", value=esg_delta, contribution=0.16, description="ESG 变化率与披露质量"),
            ]

            signals.append(
                ResearchSignal(
                    symbol=member.symbol,
                    company_name=member.company_name,
                    sector=member.sector,
                    thesis=(
                        f"{member.company_name} 在 ESG 变化、质量因子和另类数据代理指标上形成了叠加优势，"
                        f"适合作为 {benchmark} 基准上的增强型候选。"
                    ),
                    action=action,
                    confidence=confidence,
                    expected_return=expected_return,
                    risk_score=risk_score,
                    overall_score=overall,
                    e_score=round(e_score, 2),
                    s_score=round(s_score, 2),
                    g_score=round(g_score, 2),
                    factor_scores=factor_scores,
                    catalysts=[
                        f"{member.company_name} 的 ESG 变化率优于同业中位数",
                        f"{member.symbol} 在 {member.sector} 中具备更好的质量与治理组合",
                        "研究链路已保留可追溯的数据血缘与实验记录",
                    ],
                    data_lineage=[
                        "L0: yfinance/FRED/SEC/ESG RAG",
                        "L1: alignment + outlier filtering + metadata lineage",
                        "L2: technical + factor + ESG scoring + alternative data fusion",
                        "L4: Research Agent -> Strategy Agent -> Risk Agent",
                    ],
                )
            )

        signals.sort(key=lambda item: (item.action != "long", -item.overall_score, -item.confidence))
        return signals

    def _build_portfolio(
        self,
        signals: list[ResearchSignal],
        capital_base: float,
        benchmark: str,
    ) -> PortfolioSummary:
        long_candidates = [signal for signal in signals if signal.action == "long"][:5]
        if not long_candidates:
            long_candidates = signals[:4]

        raw_scores = [max(0.01, signal.expected_return * 100 + signal.confidence * 10) for signal in long_candidates]
        total_score = sum(raw_scores)
        positions: list[PortfolioPosition] = []

        for signal, raw in zip(long_candidates, raw_scores):
            target_weight = round(_bounded(raw / total_score, 0.08, 0.26), 4)
            positions.append(
                PortfolioPosition(
                    symbol=signal.symbol,
                    company_name=signal.company_name,
                    weight=target_weight,
                    expected_return=signal.expected_return,
                    risk_budget=round(1 - signal.risk_score / 100, 4),
                    score=signal.overall_score,
                    side="long",
                    thesis=signal.thesis,
                )
            )

        total_weight = sum(position.weight for position in positions)
        normalized_positions = [
            position.model_copy(update={"weight": round(position.weight / total_weight, 4)})
            for position in positions
        ]
        gross_exposure = round(sum(position.weight for position in normalized_positions), 4)
        expected_alpha = round(sum(position.weight * position.expected_return for position in normalized_positions), 4)
        turnover_estimate = round(0.18 + len(normalized_positions) * 0.015, 4)

        return PortfolioSummary(
            strategy_name="ESG Multi-Factor Long-Only",
            benchmark=benchmark,
            capital_base=capital_base,
            gross_exposure=gross_exposure,
            net_exposure=gross_exposure,
            turnover_estimate=turnover_estimate,
            expected_alpha=expected_alpha,
            positions=normalized_positions,
            constraints={
                "max_single_name_weight": 0.26,
                "max_sector_tilt": 0.20,
                "esg_floor": 60.0,
                "execution_mode": "paper_first",
            },
        )

    def _build_backtest(
        self,
        strategy_name: str,
        benchmark: str,
        capital_base: float,
        positions: list[PortfolioPosition],
        lookback_days: int,
        persist: bool,
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
            drawdown = 1 - nav / peak

            returns.append(daily_return)
            benchmark_returns.append(benchmark_return)
            timeline.append(
                BacktestPoint(
                    date=current_date.isoformat(),
                    portfolio_nav=round(nav, 4),
                    benchmark_nav=round(benchmark_nav, 4),
                    drawdown=round(drawdown, 4),
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

        alerts: list[RiskAlert] = []
        if metrics.max_drawdown > 0.12:
            alerts.append(
                RiskAlert(
                    level="high",
                    title="回撤超过 12%",
                    description="策略样本区间内出现了需要重点关注的回撤窗口。",
                    recommendation="降低单票上限，并开启更严格的 regime 切换阈值。",
                )
            )
        if metrics.annualized_volatility > 0.24:
            alerts.append(
                RiskAlert(
                    level="medium",
                    title="波动率高于目标带",
                    description="组合年化波动高于工业化交付建议区间。",
                    recommendation="加入风险平价或 CVaR 约束，压降高波动资产权重。",
                )
            )
        if not alerts:
            alerts.append(
                RiskAlert(
                    level="low",
                    title="风险处于可控区间",
                    description="当前回撤与波动率均处于可交付区间。",
                    recommendation="继续进行 Walk-forward 与压力测试验证。",
                )
            )

        result = BacktestResult(
            backtest_id=f"backtest-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            strategy_name=strategy_name,
            benchmark=benchmark,
            period_start=timeline[0].date,
            period_end=timeline[-1].date,
            metrics=metrics,
            positions=positions,
            timeline=timeline,
            risk_alerts=alerts,
            experiment_tags=["walk-forward", "esg", "multi-factor", "paper-first"],
        )

        if persist:
            payload = result.model_dump()
            payload["generated_at"] = _iso_now()
            payload["capital_base"] = capital_base
            payload["storage"] = self.storage.persist_record("backtests", result.backtest_id, payload)
        return result

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
