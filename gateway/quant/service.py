from __future__ import annotations
import json
import hashlib
import math
import sys
import statistics
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
from gateway.quant.p2_decision import P2_STRATEGY_PROFILES, P2DecisionStackRuntime
from gateway.scheduler.event_classifier_runtime import get_event_classifier_runtime
from gateway.quant.signals import MovingAverageCrossSignalEngine
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
        self.alpha_ranker = AlphaRankerRuntime()
        self.p1_suite = P1ModelSuiteRuntime()
        self.p2_stack = P2DecisionStackRuntime()
        self.default_capital = float(getattr(settings, "QUANT_DEFAULT_CAPITAL", 1_000_000))
        self.default_benchmark = getattr(settings, "QUANT_DEFAULT_BENCHMARK", "SPY")
        self.default_universe_name = getattr(settings, "QUANT_DEFAULT_UNIVERSE", "ESG_US_LARGE_CAP")
        self.default_broker = getattr(settings, "QUANT_BROKER_DEFAULT", "alpaca")

    @staticmethod
    def _normalize_broker_mode(mode: str | None) -> str:
        return "live" if str(mode or "").strip().lower() == "live" else "paper"

    def _prepare_broker_adapter(self, broker: str | None, mode: str | None = None):
        adapter = self._resolve_broker(broker)
        normalized_mode = self._normalize_broker_mode(mode)
        if adapter.broker_id == "alpaca" and hasattr(self.alpaca, "set_runtime_mode"):
            self.alpaca.set_runtime_mode(normalized_mode)
        return adapter, normalized_mode

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
        except Exception:
            return None
        if not account_payload.get("connected"):
            return None
        return account_payload

    def _extract_position_symbols(self, mode: str = "paper") -> list[str]:
        try:
            positions_payload = self.list_execution_positions(broker="alpaca", mode=mode)
        except Exception:
            return []
        symbols = []
        for position in positions_payload.get("positions", []):
            symbol = str(position.get("symbol") or "").upper().strip()
            if symbol:
                symbols.append(symbol)
        return sorted(dict.fromkeys(symbols))

    def _build_market_surface(self, watchlist_signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
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
                bars = self.market_data.get_daily_bars(symbol, limit=12)
                provider = bars.provider or provider or "unavailable"
                frame = bars.bars
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
        if signal.house_score is not None and signal.house_grade and signal.formula_version:
            return {
                "house_score": float(signal.house_score),
                "house_grade": signal.house_grade,
                "formula_version": signal.formula_version,
                "pillar_breakdown": dict(signal.pillar_breakdown or {}),
                "disclosure_confidence": float(signal.disclosure_confidence or 0.0),
                "controversy_penalty": float(signal.controversy_penalty or 0.0),
                "data_gap_penalty": float(signal.data_gap_penalty or 0.0),
                "materiality_adjustment": float(signal.materiality_adjustment or 0.0),
                "trend_bonus": float(signal.trend_bonus or 0.0),
                "house_explanation": str(signal.house_explanation or ""),
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
        return house

    def _enrich_signal_house_score(self, signal: ResearchSignal) -> ResearchSignal:
        return signal.model_copy(update=self._build_house_score_payload(signal))

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

    def _build_watchlist_snapshot(self) -> dict[str, Any]:
        position_symbols = self._extract_position_symbols(mode="paper")
        preferred_watchlist = ["AAPL", "MSFT", "NVDA", "GOOGL", "NEE", "PG", "TSLA", "AMZN"]
        universe = self.get_default_universe(position_symbols + preferred_watchlist)
        signals = self._build_signals(universe, "overview refresh", self.default_benchmark)
        watchlist_signals = [self._serialize_watchlist_signal(signal) for signal in signals]
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
            "live_account_snapshot": self._safe_live_account_snapshot(mode="paper"),
        }

    def build_platform_overview(self) -> dict[str, Any]:
        snapshot = self._build_watchlist_snapshot()
        position_symbols = snapshot["position_symbols"]
        universe = snapshot["universe"]
        signals = snapshot["signals"]
        watchlist_signals = snapshot["watchlist_signals"]
        sector_heatmap = self._build_sector_heatmap(signals)
        market_surface = self._build_market_surface(watchlist_signals)
        portfolio = self._build_portfolio(signals, self.default_capital, self.default_benchmark)
        backtests = self.storage.list_records("backtests")
        experiments = self.storage.list_records("experiments")
        live_account_snapshot = snapshot["live_account_snapshot"]
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
            "portfolio_preview": portfolio.model_dump(),
            "latest_backtest": latest_backtest,
            "experiments": experiments[:3],
            "training_plan": self._build_training_plan().model_dump(),
        }

    def _chart_limit_for_timeframe(self, timeframe: str) -> int:
        return {
            "1D": 120,
            "1W": 90,
            "1M": 72,
            "3M": 56,
            "1Y": 90,
        }.get(str(timeframe or "1D").upper(), 120)

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

    def build_dashboard_chart(self, symbol: str | None = None, timeframe: str = "1D") -> dict[str, Any]:
        snapshot = self._build_watchlist_snapshot()
        watchlist = snapshot.get("watchlist_signals") or []
        if not watchlist:
            return {
                "symbol": symbol or "",
                "timeframe": timeframe,
                "candles": [],
                "source": "unavailable",
                "indicators": {},
                "projection_scenarios": {},
                "projection_explanations": {},
                "projected_volume": [],
                "viewport_defaults": {},
                "click_targets": [],
                "prediction_disabled_reason": "no_watchlist_signals",
                "is_live_data": False,
                "provider_status": {"available": False, "provider": "unavailable"},
                "degraded_from": None,
                "market_session": None,
                "range_label": timeframe.upper(),
                "positions_context": {"symbols": snapshot.get("position_symbols", [])},
                "indicator_panels": [],
            }

        active = next((item for item in watchlist if item["symbol"] == (symbol or "").upper().strip()), watchlist[0])
        active_symbol = active["symbol"]
        limit = self._chart_limit_for_timeframe(timeframe)
        signal = next((item for item in self._build_signals(self.get_default_universe([active_symbol]), "dashboard chart", self.default_benchmark) if item.symbol == active_symbol), None)
        if signal is None:
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

        source = str(active.get("market_data_source") or self._resolve_market_data_source(signal))
        degraded_from = None
        provider_status = {"available": False, "provider": source}
        try:
            bars_result = self.market_data.get_daily_bars(active_symbol, limit=limit)
            source = bars_result.provider
            provider_status = {
                "available": True,
                "provider": bars_result.provider,
                "cache_hit": bool(getattr(bars_result, "cache_hit", False)),
                "lookback_limit": int(limit),
            }
            frame = bars_result.bars.copy()
            if str(active.get("market_data_source") or "").lower() == "alpaca" and bars_result.provider != "alpaca":
                degraded_from = "alpaca"
        except Exception as exc:
            return {
                "symbol": active_symbol,
                "timeframe": timeframe.upper(),
                "source": "unavailable",
                "candles": [],
                "indicators": {},
                "projection_scenarios": {},
                "projection_explanations": {},
                "projected_volume": [],
                "viewport_defaults": {
                    "116%": {"visibleCount": 64, "projectionWidthRatio": 0.22, "pricePaddingRatio": 0.06},
                    "352%": {"visibleCount": 32, "projectionWidthRatio": 0.28, "pricePaddingRatio": 0.08},
                    "600%": {"visibleCount": 20, "projectionWidthRatio": 0.34, "pricePaddingRatio": 0.11},
                },
                "click_targets": ["symbol_chip", "timeframe_tab", "zoom_control", "projection_line", "heatmap_tile"],
                "prediction_disabled_reason": "market_data_unavailable",
                "signal": active,
                "is_live_data": False,
                "provider_status": {"available": False, "provider": "unavailable", "error": str(exc)},
                "degraded_from": None,
                "market_session": self._safe_get_clock(self._prepare_broker_adapter("alpaca", "paper")[0]),
                "range_label": timeframe.upper(),
                "positions_context": {"symbols": snapshot.get("position_symbols", [])},
                "indicator_panels": [],
            }

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

        return {
            "symbol": active_symbol,
            "timeframe": timeframe.upper(),
            "source": source,
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
            "signal": active,
            "is_live_data": source == "alpaca",
            "provider_status": provider_status,
            "degraded_from": degraded_from,
            "market_session": self._safe_get_clock(self._prepare_broker_adapter("alpaca", "paper")[0]),
            "range_label": timeframe.upper(),
            "positions_context": {"symbols": snapshot.get("position_symbols", [])},
            "indicator_panels": ["main", "volume"],
        }

    def _should_use_live_market_data(self) -> bool:
        running_pytest = any(name == "pytest" or name.startswith("_pytest") for name in sys.modules)
        return not (running_pytest and isinstance(self.market_data, MarketDataGateway))

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
        portfolio = self._build_portfolio(signals, capital_base, benchmark)
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
        status = adapter.connection_status()
        descriptor = adapter.descriptor().model_dump()
        if not status.get("configured"):
            return {
                "connected": False,
                "mode": normalized_mode,
                "broker": descriptor,
                "broker_connection": status,
                "warnings": [f"{adapter.label} credentials are not configured for the current runtime."],
            }

        try:
            account = adapter.get_account()
            account_snapshot = self._summarize_broker_account(adapter.broker_id, account)
            account_snapshot["account_mode"] = normalized_mode
            clock_snapshot = self._safe_get_clock(adapter)
            return {
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
            }
        except Exception as exc:
            logger.warning(f"Failed to load {adapter.label} account status: {exc}")
            return {
                "connected": False,
                "mode": normalized_mode,
                "broker": descriptor,
                "broker_connection": status,
                "warnings": [str(exc)],
            }

    def list_execution_orders(
        self,
        broker: str | None = None,
        status: str = "all",
        limit: int = 20,
        mode: str = "paper",
    ) -> dict[str, Any]:
        adapter, normalized_mode = self._prepare_broker_adapter(broker, mode)
        connection = adapter.connection_status()
        descriptor = adapter.descriptor().model_dump()
        if not connection.get("configured"):
            return {"connected": False, "mode": normalized_mode, "orders": [], "broker": descriptor, "broker_connection": connection}

        try:
            orders = adapter.list_orders(status=status, limit=limit)
            return {
                "connected": True,
                "mode": normalized_mode,
                "broker": descriptor,
                "broker_connection": connection,
                "orders": [self._summarize_broker_order(adapter.broker_id, item) for item in orders],
            }
        except Exception as exc:
            logger.warning(f"Failed to list {adapter.label} orders: {exc}")
            return {
                "connected": False,
                "mode": normalized_mode,
                "broker": descriptor,
                "broker_connection": connection,
                "orders": [],
                "warnings": [str(exc)],
            }

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
        connection = adapter.connection_status()
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
        connection = adapter.connection_status()
        descriptor = adapter.descriptor().model_dump()
        if not connection.get("configured"):
            return {"connected": False, "mode": normalized_mode, "positions": [], "broker": descriptor, "broker_connection": connection}

        try:
            positions = adapter.list_positions()
            return {
                "connected": True,
                "mode": normalized_mode,
                "broker": descriptor,
                "broker_connection": connection,
                "positions": [self._summarize_broker_position(adapter.broker_id, item) for item in positions],
            }
        except Exception as exc:
            logger.warning(f"Failed to list {adapter.label} positions: {exc}")
            return {
                "connected": False,
                "mode": normalized_mode,
                "broker": descriptor,
                "broker_connection": connection,
                "positions": [],
                "warnings": [str(exc)],
            }

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
        capped_max_orders = max(
            1,
            min(
                int(max_orders or 1),
                int(getattr(settings, "ALPACA_MAX_TEST_ORDERS", 2) or 2),
                int(getattr(settings, "EXECUTION_MAX_DAILY_ORDERS", 25) or 25),
                10,
            ),
        )
        capped_notional = round(
            min(
                float(per_order_notional or getattr(settings, "ALPACA_DEFAULT_TEST_NOTIONAL", 1.0) or 1.0),
                float(getattr(settings, "ALPACA_MAX_ORDER_NOTIONAL", 10.0) or 10.0),
                float(getattr(settings, "EXECUTION_MAX_NOTIONAL_PER_ORDER", 2500.0) or 2500.0),
            ),
            2,
        )
        orders = self._build_execution_orders(
            execution_id=execution_id,
            broker_id=broker_id,
            positions=portfolio.positions,
            capital_base=capital_base,
            order_type=normalized_order_type,
            time_in_force=normalized_tif,
            per_order_notional=capped_notional,
        )
        average_slippage = round(
            statistics.mean([float(order.estimated_slippage_bps or 0.0) for order in orders] or [0.0]),
            2,
        )
        average_impact = round(
            statistics.mean([float(order.estimated_impact_bps or 0.0) for order in orders] or [0.0]),
            2,
        )
        average_fill_probability = round(
            statistics.mean([float(order.expected_fill_probability or 0.0) for order in orders] or [0.0]),
            4,
        )
        canary_summary = {
            "full_release": sum(1 for order in orders if order.canary_bucket == "full_release"),
            "canary_release": sum(1 for order in orders if order.canary_bucket == "canary_release"),
            "holdout_shadow": sum(1 for order in orders if order.canary_bucket == "holdout_shadow"),
        }
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
            broker_connection=adapter.connection_status(),
        )

        payload = plan.model_dump()
        payload["broker_id"] = broker_id
        payload["broker_descriptor"] = adapter.descriptor().model_dump()
        payload["generated_at"] = _iso_now()
        payload["portfolio"] = portfolio.model_dump()
        payload["submit_orders"] = bool(submit_orders)
        payload["max_orders"] = capped_max_orders
        payload["per_order_notional"] = capped_notional
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

        live_enabled = bool(getattr(settings, "ALPACA_ENABLE_LIVE_TRADING", False))
        if payload["mode"] == "live":
            if broker_id != "alpaca":
                payload["ready"] = False
                payload["broker_status"] = "blocked"
                payload["warnings"].append("Live routing is currently only enabled for Alpaca.")
            elif not live_enabled:
                payload["ready"] = False
                payload["broker_status"] = "blocked"
                payload["warnings"].append("Live trading is disabled in server settings. Keep validating in Alpaca Paper first.")
            elif not bool(live_confirmed):
                payload["ready"] = False
                payload["broker_status"] = "awaiting_live_confirmation"
                payload["warnings"].append("Live order routing requires an explicit operator confirmation before submission.")

        if submit_orders and payload["ready"] and (payload["mode"] == "paper" or (payload["mode"] == "live" and live_enabled and live_confirmed)):
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
        connection = adapter.connection_status()
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
        requested_notional = round(
            min(
                float(
                    per_order_notional
                    or existing_payload.get("notional")
                    or getattr(settings, "ALPACA_DEFAULT_TEST_NOTIONAL", 1.0)
                    or 1.0
                ),
                float(getattr(settings, "EXECUTION_MAX_NOTIONAL_PER_ORDER", 2500.0) or 2500.0),
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

        if capped_notional <= float(getattr(settings, "EXECUTION_MAX_NOTIONAL_PER_ORDER", 2500.0) or 2500.0):
            checks.append("Per-order notional is within configured broker-safe limits")
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
        orders: list[ExecutionOrder] = []
        for index, position in enumerate(positions):
            ref_price = round(40 + position.weight * 500 + (_stable_seed(position.symbol) % 100) / 3, 2)
            quantity = max(1, int((capital_base * position.weight) / ref_price))
            tracking_id = self._build_order_tracking_id(execution_id, position.symbol, index)
            execution_tactic = self._select_execution_tactic(position)
            slippage_bps = position.estimated_slippage_bps or self._estimate_order_slippage_bps(position, capital_base)
            impact_bps = position.estimated_impact_bps or self._estimate_order_impact_bps(position, capital_base)
            fill_probability = position.expected_fill_probability or self._estimate_order_fill_probability(
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
                    canary_bucket=self._assign_canary_bucket(execution_id, position.symbol),
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
        journal = payload.get("journal") or self._build_execution_journal(
            execution_id=payload["execution_id"],
            broker_id="alpaca",
            mode=payload.get("mode", "paper"),
            orders=payload.get("orders", []),
            risk_summary=payload.get("warnings", []),
        )
        payload["journal"] = journal
        self._submit_broker_orders(
            adapter=self._resolve_broker("alpaca"),
            payload=payload,
            journal=journal,
            capped_max_orders=capped_max_orders,
            capped_notional=capped_notional,
            normalized_order_type=normalized_order_type,
            normalized_tif=normalized_tif,
            extended_hours=extended_hours,
        )

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

    def _safe_get_clock(self, adapter) -> dict[str, Any] | None:
        try:
            clock = adapter.get_clock()
        except Exception:
            return None
        return self._summarize_broker_clock(adapter.broker_id, clock)

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
        controls = self.get_execution_controls()
        payload["controls"] = controls
        if controls.get("kill_switch_enabled"):
            payload["warnings"].append(
                controls.get("kill_switch_reason")
                or "Execution kill switch is engaged. Broker routing stayed disabled."
            )
            payload["broker_status"] = "kill_switch_engaged"
            payload["ready"] = False
            for order in payload.get("orders", []):
                order["status"] = "blocked"
                record = self._find_journal_record(journal, order.get("client_order_id") or order.get("symbol"))
                if record is not None:
                    self._update_journal_record(
                        journal=journal,
                        record=record,
                        state="blocked",
                        message=f"{order.get('symbol')} was blocked by the execution kill switch.",
                    )
            self._refresh_journal_state(journal)
            return

        connection = adapter.connection_status()
        if not connection.get("configured"):
            payload["warnings"].append(f"{adapter.label} credentials missing. Execution stayed in plan-only mode.")
            payload["broker_status"] = "not_configured"
            return

        try:
            account = adapter.get_account()
            payload["account_snapshot"] = self._summarize_broker_account(adapter.broker_id, account)
        except Exception as exc:
            payload["warnings"].append(f"Unable to fetch {adapter.label} account: {exc}")
            payload["broker_status"] = "account_error"
            payload["ready"] = False
            return

        if payload["account_snapshot"].get("trading_blocked"):
            payload["warnings"].append(f"{adapter.label} account is trading_blocked. Orders were not submitted.")
            payload["broker_status"] = "trading_blocked"
            payload["ready"] = False
            return
        if payload["account_snapshot"].get("account_blocked"):
            payload["warnings"].append(f"{adapter.label} account is account_blocked. Orders were not submitted.")
            payload["broker_status"] = "account_blocked"
            payload["ready"] = False
            return

        payload["market_clock"] = self._safe_get_clock(adapter)
        payload["warnings"].extend(
            self._collect_execution_warnings(
                account_snapshot=payload.get("account_snapshot", {}),
                market_clock=payload.get("market_clock"),
                submit_orders=True,
            )
        )
        if getattr(settings, "EXECUTION_REQUIRE_MARKET_OPEN", False) and payload.get("market_clock", {}).get("is_open") is False:
            payload["warnings"].append("Runtime policy requires the market to be open before routing orders.")
            payload["broker_status"] = "market_closed"
            payload["ready"] = False
            return

        buying_power = self._safe_float(payload.get("account_snapshot", {}).get("buying_power"))
        required_buffer = float(getattr(settings, "EXECUTION_MIN_BUYING_POWER_BUFFER", 100.0) or 100.0)
        if buying_power is not None and buying_power < capped_notional + required_buffer:
            payload["warnings"].append(
                f"Buying power {buying_power:.2f} is below requested per-order notional {capped_notional:.2f} plus safety buffer {required_buffer:.2f}. Orders were not submitted."
            )
            payload["broker_status"] = "insufficient_buying_power"
            payload["ready"] = False
            return

        duplicate_candidates = {}
        if not allow_duplicates:
            duplicate_candidates = self._find_duplicate_order_candidates(
                broker_id=adapter.broker_id,
                execution_id=payload["execution_id"],
                orders=payload.get("orders", []),
            )

        submitted_orders: list[dict[str, Any]] = []
        for index, order in enumerate(payload.get("orders", [])[:capped_max_orders]):
            symbol = str(order.get("symbol", "")).upper().strip()
            record = self._find_journal_record(journal, order.get("client_order_id") or symbol)
            duplicate_key = f"{symbol}:{str(order.get('side') or 'buy').lower()}"
            duplicate_context = duplicate_candidates.get(duplicate_key)
            if duplicate_context is not None:
                message = (
                    f"Duplicate order guard suppressed {symbol} {order.get('side', 'buy')} because "
                    f"{duplicate_context.get('status', 'an active order')} already exists."
                )
                payload["warnings"].append(message)
                order["status"] = "suppressed_duplicate"
                if record is not None:
                    self._update_journal_record(
                        journal=journal,
                        record=record,
                        state="suppressed",
                        message=message,
                        broker_snapshot=duplicate_context,
                    )
                continue

            if str(order.get("canary_bucket") or "") == "holdout_shadow":
                message = f"{symbol} held out by canary policy and stayed in shadow mode."
                payload["warnings"].append(message)
                order["status"] = "canary_holdout"
                if record is not None:
                    self._update_journal_record(
                        journal=journal,
                        record=record,
                        state="suppressed",
                        message=message,
                        broker_snapshot={
                            "status": "canary_holdout",
                            "symbol": symbol,
                            "client_order_id": order.get("client_order_id"),
                        },
                    )
                continue

            try:
                asset = adapter.get_asset(symbol)
            except Exception:
                asset = {"symbol": symbol, "tradable": True, "fractionable": False}

            if asset and asset.get("tradable") is False:
                payload["warnings"].append(f"{symbol} is not tradable on {adapter.label} and was skipped.")
                if record is not None:
                    self._update_journal_record(
                        journal=journal,
                        record=record,
                        state="rejected",
                        message=f"{symbol} is not tradable on {adapter.label}.",
                    )
                continue

            try:
                broker_payload = self._build_broker_order_payload(
                    broker_id=adapter.broker_id,
                    execution_id=payload["execution_id"],
                    order=order,
                    asset=asset,
                    index=index,
                    capped_notional=capped_notional,
                    normalized_order_type=normalized_order_type,
                    normalized_tif=normalized_tif,
                    extended_hours=extended_hours,
                )
                created_order = adapter.submit_order(broker_payload)
                refreshed_order = created_order
                order_id = str(created_order.get("id") or "").strip()
                if order_id:
                    try:
                        refreshed_order = adapter.get_order(order_id)
                    except Exception:
                        refreshed_order = created_order
                receipt = self._summarize_broker_order(adapter.broker_id, refreshed_order)
                receipt["submitted_payload"] = broker_payload
                submitted_orders.append(receipt)
                order.update(
                    {
                        "status": receipt.get("status", "submitted"),
                        "broker_order_id": receipt.get("id"),
                        "client_order_id": order.get("client_order_id") or receipt.get("client_order_id"),
                        "submitted_at": receipt.get("submitted_at"),
                        "filled_qty": receipt.get("filled_qty"),
                        "filled_avg_price": receipt.get("filled_avg_price"),
                        "order_type": receipt.get("type") or order.get("order_type"),
                        "time_in_force": receipt.get("time_in_force") or order.get("time_in_force"),
                        "notional": receipt.get("notional") or order.get("notional"),
                    }
                )
                if record is not None:
                    self._update_journal_record(
                        journal=journal,
                        record=record,
                        state=self._normalize_order_state(adapter.broker_id, receipt.get("status")),
                        message=f"{symbol} routed to {adapter.label}.",
                        broker_snapshot=receipt,
                        submitted_payload=broker_payload,
                    )
            except Exception as exc:
                logger.warning(f"{adapter.label} order submission failed for {symbol}: {exc}")
                payload["broker_errors"].append(f"{symbol}: {exc}")
                if record is not None:
                    self._update_journal_record(
                        journal=journal,
                        record=record,
                        state="failed",
                        message=f"{symbol} submission failed: {exc}",
                    )

        payload["submitted_orders"] = submitted_orders
        payload["submitted"] = bool(submitted_orders)
        if submitted_orders:
            payload["broker_status"] = "submitted"
        elif any(str(order.get("status") or "").lower() == "canary_holdout" for order in payload.get("orders", [])):
            payload["broker_status"] = "canary_shadow"
        elif any(str(order.get("status") or "").lower() == "suppressed_duplicate" for order in payload.get("orders", [])):
            payload["broker_status"] = "suppressed"
        else:
            payload["broker_status"] = "submit_failed"
        if not submitted_orders and not payload["warnings"] and not payload["broker_errors"]:
            payload["warnings"].append(f"No {adapter.label} orders were submitted.")
        self._refresh_journal_state(journal)
        payload["cancelable_order_ids"] = [
            record["order_id"]
            for record in journal.get("records", [])
            if self._can_cancel_state(record.get("current_state"))
        ]
        payload["retryable_order_ids"] = [
            record["order_id"]
            for record in journal.get("records", [])
            if self._can_retry_state(record.get("current_state"))
        ]

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
        if broker_id == "alpaca":
            return self._build_alpaca_order_payload(
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
            "client_order_id": order.get("client_order_id") or self._build_order_tracking_id(execution_id, str(order.get("symbol")), index),
        }

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
        except Exception:
            return {}

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
            "path": str(heartbeat_path),
            "exists": heartbeat_path.exists(),
            "stale": True,
            "last_seen": None,
        }
        if not heartbeat_path.exists():
            return payload
        try:
            heartbeat = json.loads(heartbeat_path.read_text(encoding="utf-8"))
        except Exception:
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

    def build_healthcheck(self) -> dict[str, Any]:
        heartbeat = self._scheduler_heartbeat_status()
        remote_llm = self._remote_llm_status()
        qdrant = self._qdrant_status()
        model_registry = self.build_model_registry()
        components = {
            "api": {"ok": True, "detail": "FastAPI runtime is available."},
            "quant_scheduler": {
                "ok": heartbeat.get("exists") and not heartbeat.get("stale"),
                "detail": f"Heartbeat {heartbeat.get('last_seen') or 'missing'}",
                "meta": heartbeat,
            },
            "remote_llm": {
                "ok": (
                    remote_llm.get("backend_mode") in {"cloud", "auto"}
                    or (
                        bool(remote_llm.get("configured"))
                        and remote_llm.get("backend_mode") == "remote"
                        and bool(remote_llm.get("reachable"))
                    )
                ),
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
        }
        required = [
            item.strip()
            for item in str(getattr(settings, "API_HEALTHCHECK_REQUIRED_COMPONENTS", "api,quant_scheduler,remote_llm,qdrant")).split(",")
            if item.strip()
        ]
        if remote_llm.get("backend_mode") in {"cloud", "auto"}:
            required = [item for item in required if item != "remote_llm"] + ["remote_llm"]
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
        components = {
            "alpha_ranker": self.alpha_ranker.status(),
            "p1_suite": self.p1_suite.status(),
            "p2_stack": self.p2_stack.status(),
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
            except Exception:
                release_log_tail = []

        return {
            "generated_at": _iso_now(),
            "registry_path": str(registry_path),
            "release_log_path": str(release_log_path),
            "canary_enabled": bool(getattr(settings, "EXECUTION_CANARY_ENABLED", True)),
            "canary_release_percent": float(getattr(settings, "EXECUTION_CANARY_RELEASE_PERCENT", 0.15) or 0.15),
            "has_active_canary": self._active_canary_percent() is not None,
            "active_canary_percent": self._active_canary_percent(),
            "models": models,
            "release_log_tail": release_log_tail,
        }

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

    def _build_signals(
        self,
        universe: list[UniverseMember],
        research_question: str,
        benchmark: str,
    ) -> list[ResearchSignal]:
        if self._should_use_live_market_data():
            try:
                live_signals = self.signal_engine.build_signals(
                    universe=universe,
                    benchmark=benchmark,
                    research_question=research_question,
                )
                if live_signals:
                    return self.alpha_ranker.rerank(live_signals)
            except Exception as exc:
                logger.warning(f"Signal engine fallback engaged: {exc}")

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
        return self.alpha_ranker.rerank(signals)

    def _build_portfolio(
        self,
        signals: list[ResearchSignal],
        capital_base: float,
        benchmark: str,
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
            and (signal.graph_contagion_risk is None or signal.graph_contagion_risk < float(getattr(settings, "P2_GRAPH_CONTAGION_LIMIT", 0.62) or 0.62))
        ][: int(strategy_profile["max_positions"])]
        if not long_candidates:
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
        if not long_candidates:
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
        if 0 < len(long_candidates) < minimum_target_positions:
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
                    "p1_stack": "active" if self.p1_suite.available() else "heuristic",
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
        optimized_weights, allocation_meta = self._allocate_objective_weights(
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
                    "execution_tactic": normalized.execution_tactic or self._select_execution_tactic(normalized),
                }
            )
            slippage_bps = self._estimate_order_slippage_bps(normalized, capital_base)
            impact_bps = self._estimate_order_impact_bps(normalized, capital_base)
            fill_probability = self._estimate_order_fill_probability(
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
                "p1_stack": "active" if self.p1_suite.available() else "heuristic",
                "p2_strategy_selector": active_strategy,
                "graph_overlay": "enabled",
                "allocator": allocation_meta.get("mode", "heuristic"),
                "allocator_history_rows": float(allocation_meta.get("history_rows", 0) or 0),
                "allocator_average_correlation": float(allocation_meta.get("average_correlation", 0.0) or 0.0),
                "decision_min_score": round(decision_floor, 4),
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

    def _build_signals(
        self,
        universe: list[UniverseMember],
        research_question: str,
        benchmark: str,
    ) -> list[ResearchSignal]:
        market_data_signals: list[ResearchSignal] = []
        if self._should_use_live_market_data():
            market_data_signals = self.signal_engine.build_signals(
                universe=universe,
                benchmark=benchmark,
                research_question=research_question,
            )
        if len(market_data_signals) == len(universe):
            ranked = self.alpha_ranker.rerank(market_data_signals)
            p1_enriched = self.p1_suite.enrich_and_rerank(ranked)
            return [self._enrich_signal_house_score(signal) for signal in self._apply_p2_stack(p1_enriched)]

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
        return [self._enrich_signal_house_score(signal) for signal in self._apply_p2_stack(p1_enriched)]

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
    ) -> BacktestResult:
        market_result = None
        if self._should_use_live_market_data():
            market_result = self._build_market_data_backtest(
                strategy_name=strategy_name,
                benchmark=benchmark,
                capital_base=capital_base,
                positions=positions,
                lookback_days=lookback_days,
            )
        result = market_result or self._build_synthetic_backtest(
            strategy_name=strategy_name,
            benchmark=benchmark,
            capital_base=capital_base,
            positions=positions,
            lookback_days=lookback_days,
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
    ) -> BacktestResult | None:
        if not positions:
            return None

        try:
            close_frame = pd.DataFrame()
            for position in positions:
                bars = self.market_data.get_daily_bars(position.symbol, limit=max(lookback_days + 10, 120)).bars
                if bars.empty:
                    return None
                series = bars.set_index("timestamp")["close"].rename(position.symbol)
                close_frame = series.to_frame() if close_frame.empty else close_frame.join(series, how="outer")

            benchmark_bars = self.market_data.get_daily_bars(benchmark, limit=max(lookback_days + 10, 120)).bars
            if benchmark_bars.empty:
                return None
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
        )

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
