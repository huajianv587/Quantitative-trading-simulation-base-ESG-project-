from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd

from gateway.quant.market_data import MarketBarsResult
from gateway.quant.models import PortfolioPosition, ResearchSignal, UniverseMember
from gateway.quant.service import QuantSystemService
from gateway.quant.signals import MovingAverageCrossSignalEngine


class _FakeMarketData:
    def get_daily_bars(self, symbol: str, limit: int = 180, force_refresh: bool = False):
        base = datetime(2025, 1, 1, tzinfo=timezone.utc)
        closes = []
        price = 100.0
        for index in range(120):
            price += 0.4
            closes.append(
                {
                    "timestamp": base + timedelta(days=index),
                    "open": price - 0.3,
                    "high": price + 0.5,
                    "low": price - 0.6,
                    "close": price,
                    "volume": 1_000_000 + index,
                    "trade_count": 1000 + index,
                    "vwap": price,
                }
            )
        return MarketBarsResult(
            symbol=symbol,
            provider="alpaca",
            timeframe="1Day",
            cache_hit=False,
            bars=pd.DataFrame(closes),
            cache_path="storage/quant/market_data/bars.sqlite3",
        )


def test_moving_average_cross_signal_engine_builds_long_signal():
    engine = MovingAverageCrossSignalEngine(_FakeMarketData())
    signals = engine.build_signals(
        universe=[UniverseMember(symbol="AAPL", company_name="Apple", sector="Technology", industry="Hardware")],
        benchmark="SPY",
        research_question="Run momentum strategy",
    )

    assert len(signals) == 1
    assert signals[0].action == "long"
    assert any(score.name == "momentum" for score in signals[0].factor_scores)
    assert "moving-average crossover engine" in " ".join(signals[0].data_lineage)


def test_quant_service_prefers_market_data_backtest_when_available():
    service = QuantSystemService()
    service.market_data = _FakeMarketData()
    service.signal_engine = MovingAverageCrossSignalEngine(service.market_data)

    result = service._build_backtest(
        strategy_name="Momentum MA Cross",
        benchmark="SPY",
        capital_base=1_000_000,
        positions=[
            PortfolioPosition(
                symbol="AAPL",
                company_name="Apple",
                weight=0.5,
                expected_return=0.08,
                risk_budget=0.6,
                score=70,
                side="long",
                thesis="Bullish trend",
            ),
            PortfolioPosition(
                symbol="MSFT",
                company_name="Microsoft",
                weight=0.5,
                expected_return=0.07,
                risk_budget=0.62,
                score=68,
                side="long",
                thesis="Bullish trend",
            ),
        ],
        lookback_days=60,
        persist=False,
    )

    assert "market-data" in result.experiment_tags
    assert result.timeline
    assert result.metrics.cumulative_return >= 0


def test_quant_service_returns_no_trade_portfolio_without_long_signals():
    service = QuantSystemService()
    portfolio = service._build_portfolio(
        signals=[
            ResearchSignal(
                symbol="AAPL",
                company_name="Apple",
                sector="Technology",
                thesis="Neutral regime",
                action="neutral",
                confidence=0.7,
                expected_return=0.0,
                risk_score=55,
                overall_score=54,
                e_score=60,
                s_score=58,
                g_score=57,
            ),
            ResearchSignal(
                symbol="MSFT",
                company_name="Microsoft",
                sector="Technology",
                thesis="Still below long MA",
                action="short",
                confidence=0.68,
                expected_return=-0.02,
                risk_score=62,
                overall_score=49,
                e_score=59,
                s_score=57,
                g_score=56,
            ),
        ],
        capital_base=1_000_000,
        benchmark="SPY",
    )

    assert portfolio.positions == []
    assert portfolio.expected_alpha == 0.0
    assert portfolio.constraints["status"] == "no_trade"
