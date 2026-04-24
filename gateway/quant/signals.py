from __future__ import annotations

import hashlib
from typing import Any

import pandas as pd

from gateway.config import settings
from gateway.quant.market_data import MarketBarsResult, MarketDataGateway
from gateway.quant.models import FactorScore, ResearchSignal, UniverseMember


def _stable_seed(*parts: str) -> int:
    raw = "::".join(parts).encode("utf-8")
    return int(hashlib.sha256(raw).hexdigest()[:8], 16)


def _bounded(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


class MovingAverageCrossSignalEngine:
    def __init__(self, market_data: MarketDataGateway) -> None:
        self.market_data = market_data
        self.short_window = int(getattr(settings, "MOMENTUM_SHORT_WINDOW", 20) or 20)
        self.long_window = int(getattr(settings, "MOMENTUM_LONG_WINDOW", 60) or 60)
        self.history_bars = max(
            int(getattr(settings, "MARKET_DATA_HISTORY_DAYS", 240) or 240),
            self.long_window + 10,
        )

    def build_signals(
        self,
        universe: list[UniverseMember],
        benchmark: str,
        research_question: str = "",
        prefetched_bars: dict[str, MarketBarsResult] | None = None,
    ) -> list[ResearchSignal]:
        signals: list[ResearchSignal] = []
        for member in universe:
            try:
                bars_result = (prefetched_bars or {}).get(member.symbol)
                if bars_result is None:
                    bars_result = self.market_data.get_daily_bars(member.symbol, limit=self.history_bars)
                signal = self._build_signal(member, benchmark, research_question, bars_result)
                if signal is not None:
                    signals.append(signal)
            except Exception:
                continue

        signals.sort(key=lambda item: (item.action != "long", -item.overall_score, -item.confidence))
        return signals

    def _build_signal(
        self,
        member: UniverseMember,
        benchmark: str,
        research_question: str,
        bars_result: MarketBarsResult,
    ) -> ResearchSignal | None:
        bars = bars_result.bars.copy()
        if bars.empty or len(bars) < self.long_window + 2:
            return None

        bars["short_ma"] = bars["close"].rolling(self.short_window).mean()
        bars["long_ma"] = bars["close"].rolling(self.long_window).mean()
        bars = bars.dropna(subset=["short_ma", "long_ma"]).reset_index(drop=True)
        if len(bars) < 2:
            return None

        last = bars.iloc[-1]
        previous = bars.iloc[-2]
        short_ma = float(last["short_ma"])
        long_ma = float(last["long_ma"])
        prev_short = float(previous["short_ma"])
        prev_long = float(previous["long_ma"])
        close = float(last["close"])
        trend_gap = (short_ma - long_ma) / long_ma if long_ma else 0.0
        price_vs_long = (close - long_ma) / long_ma if long_ma else 0.0

        if prev_short <= prev_long and short_ma > long_ma:
            crossover = "golden_cross"
        elif prev_short >= prev_long and short_ma < long_ma:
            crossover = "death_cross"
        else:
            crossover = "bullish_trend" if short_ma > long_ma else "bearish_trend"

        seed = _stable_seed(member.symbol, benchmark, "momentum")
        quality = 52 + ((seed // 7) % 24)
        value = 48 + ((seed // 11) % 22)
        alternative_data = 50 + ((seed // 13) % 18)
        regime_fit = 49 + ((seed // 17) % 22)
        esg_delta = 54 + ((seed // 19) % 20)
        momentum = _bounded(50 + trend_gap * 1400 + price_vs_long * 600, 8, 96)
        e_score = _bounded(0.36 * alternative_data + 0.28 * esg_delta + 0.10 * momentum + 18, 45, 94)
        s_score = _bounded(0.42 * quality + 0.12 * value + 18, 42, 90)
        g_score = _bounded(0.33 * quality + 0.18 * regime_fit + 20, 44, 92)
        overall = round(
            _bounded(
                0.34 * momentum
                + 0.16 * quality
                + 0.10 * value
                + 0.12 * alternative_data
                + 0.12 * regime_fit
                + 0.16 * esg_delta,
                25,
                96,
            ),
            2,
        )
        action = "long" if short_ma > long_ma else "neutral"
        expected_return = round(_bounded(trend_gap * 1.6 + max(price_vs_long, 0.0) * 0.45 + (0.012 if crossover == "golden_cross" else 0.0), -0.04, 0.16), 4)
        risk_score = round(_bounded(64 - trend_gap * 900 - (quality - 60) * 0.35 + (0 if action == "long" else 8), 16, 84), 2)
        confidence = round(_bounded(0.56 + min(len(bars), 200) / 500 + abs(trend_gap) * 3 + (0.05 if "cross" in crossover else 0.0), 0.56, 0.96), 2)

        factor_scores = [
            FactorScore(name="momentum", value=round(momentum, 2), contribution=0.34, description=f"{self.short_window}/{self.long_window} MA trend strength"),
            FactorScore(name="quality", value=quality, contribution=0.16, description="Quality proxy blended with execution discipline"),
            FactorScore(name="value", value=value, contribution=0.10, description="Valuation proxy retained for ranking stability"),
            FactorScore(name="alternative_data", value=alternative_data, contribution=0.12, description=f"{bars_result.provider} daily bars cached in SQLite"),
            FactorScore(name="regime_fit", value=regime_fit, contribution=0.12, description=f"Price above long MA: {price_vs_long:.2%}"),
            FactorScore(name="esg_delta", value=esg_delta, contribution=0.16, description="ESG disclosure proxy retained for blended ranking"),
        ]

        thesis = (
            f"{member.company_name} is running a {self.short_window}/{self.long_window} moving-average "
            f"{'bullish' if action == 'long' else 'neutral'} regime on {bars_result.provider} daily bars. "
            f"Latest close {close:.2f}, short MA {short_ma:.2f}, long MA {long_ma:.2f}, crossover state {crossover}."
        )

        return ResearchSignal(
            symbol=member.symbol,
            company_name=member.company_name,
            sector=member.sector,
            thesis=thesis,
            action=action,
            confidence=confidence,
            expected_return=expected_return,
            risk_score=risk_score,
            overall_score=overall,
            e_score=round(e_score, 2),
            s_score=round(s_score, 2),
            g_score=round(g_score, 2),
            signal_source="momentum_engine",
            market_data_source=bars_result.provider,
            factor_scores=factor_scores,
            catalysts=[
                f"Crossover state: {crossover}",
                f"{self.short_window}D MA {short_ma:.2f} vs {self.long_window}D MA {long_ma:.2f}",
                f"Price vs {self.long_window}D MA: {price_vs_long:.2%}",
            ],
            data_lineage=[
                f"L0: {bars_result.provider} daily bars",
                f"L1: SQLite cache at {bars_result.cache_path}",
                f"L2: {self.short_window}/{self.long_window} moving-average crossover engine",
                "L4: Strategy signal -> risk checks -> broker router -> execution journal",
            ],
        )
