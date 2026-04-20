from __future__ import annotations

import math
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

from tenacity import retry, stop_after_attempt, wait_exponential

from gateway.connectors.free_live import FreeLiveConnectorRegistry
from gateway.trading.models import SentimentSnapshot, SentimentSymbolScore


POSITIVE_TOKENS = {
    "beat",
    "beats",
    "growth",
    "upgrade",
    "improving",
    "strong",
    "surge",
    "record",
    "bullish",
    "resilient",
    "expands",
    "wins",
    "positive",
}
NEGATIVE_TOKENS = {
    "miss",
    "misses",
    "downgrade",
    "weak",
    "risk",
    "lawsuit",
    "probe",
    "decline",
    "cuts",
    "controversy",
    "negative",
    "bearish",
    "fall",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SentimentAgent:
    def __init__(self, connectors: FreeLiveConnectorRegistry | None = None) -> None:
        self.connectors = connectors or FreeLiveConnectorRegistry()

    @retry(wait=wait_exponential(multiplier=0.5, min=0.5, max=4), stop=stop_after_attempt(3), reraise=True)
    def _fetch_yfinance_news(self, symbol: str) -> list[dict[str, Any]]:
        import yfinance as yf  # type: ignore

        ticker = yf.Ticker(symbol)
        return list(getattr(ticker, "news", []) or [])

    def _fetch_connector_news(
        self,
        symbol: str,
        *,
        providers: list[str] | None = None,
        quota_guard: bool = True,
    ) -> list[dict[str, Any]]:
        provider_ids = self.connectors.provider_ids(providers or ["marketaux", "thenewsapi"], configured_only=True)
        items: list[dict[str, Any]] = []
        for provider_id in provider_ids:
            if provider_id not in {"marketaux", "thenewsapi"}:
                continue
            result = self.connectors.connectors[provider_id].sample_request(
                symbol,
                dry_run=False,
                quota_guard=quota_guard,
            )
            items.extend(result.normalized_items)
        return items

    @staticmethod
    def _article_text(article: dict[str, Any]) -> str:
        pieces = [
            str(article.get("title") or ""),
            str(article.get("summary") or ""),
            str(article.get("content") or ""),
        ]
        return " ".join(piece.strip() for piece in pieces if piece).lower()

    def _score_article(self, article: dict[str, Any]) -> float:
        text = self._article_text(article)
        positive = sum(1 for token in POSITIVE_TOKENS if token in text)
        negative = sum(1 for token in NEGATIVE_TOKENS if token in text)
        if not positive and not negative:
            return 0.0
        raw = (positive - negative) / max(positive + negative, 1)
        return max(-1.0, min(1.0, raw))

    @staticmethod
    def _freshness_score(published_at: str | None) -> float:
        if not published_at:
            return 0.4
        try:
            parsed = datetime.fromisoformat(str(published_at).replace("Z", "+00:00"))
        except ValueError:
            return 0.4
        hours = max((datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds() / 3600.0, 0.0)
        return max(0.1, min(1.0, math.exp(-hours / 36.0)))

    @staticmethod
    def _normalize_yfinance_article(symbol: str, article: dict[str, Any]) -> dict[str, Any]:
        provider = "yfinance_news"
        published = article.get("providerPublishTime")
        published_at = None
        if published is not None:
            try:
                published_at = datetime.fromtimestamp(int(published), tz=timezone.utc).isoformat()
            except Exception:
                published_at = None
        return {
            "provider": provider,
            "symbol": symbol,
            "title": str(article.get("title") or f"{symbol} news"),
            "summary": str(article.get("summary") or article.get("title") or ""),
            "url": article.get("link"),
            "published_at": published_at,
            "metadata": article,
        }

    def run(
        self,
        *,
        universe: list[str],
        providers: list[str] | None = None,
        quota_guard: bool = True,
    ) -> SentimentSnapshot:
        symbols = [str(symbol or "").upper().strip() for symbol in universe if str(symbol or "").strip()]
        source_mix: Counter[str] = Counter()
        symbol_rows: list[SentimentSymbolScore] = []
        warnings: list[str] = []
        headline_count = 0
        weighted_total = 0.0
        weight_denominator = 0.0

        for symbol in symbols:
            articles: list[dict[str, Any]] = []
            try:
                articles.extend(self._normalize_yfinance_article(symbol, row) for row in self._fetch_yfinance_news(symbol)[:6])
            except Exception as exc:
                warnings.append(f"{symbol}: yfinance news unavailable ({exc})")
            try:
                articles.extend(self._fetch_connector_news(symbol, providers=providers, quota_guard=quota_guard))
            except Exception as exc:
                warnings.append(f"{symbol}: connector news unavailable ({exc})")

            if not articles:
                symbol_rows.append(
                    SentimentSymbolScore(
                        symbol=symbol,
                        polarity=0.0,
                        confidence=0.0,
                        article_count=0,
                        freshness_score=0.0,
                        source_mix={},
                        headline_samples=[],
                        feature_value=50.0,
                    )
                )
                continue

            polarity_sum = 0.0
            confidence_sum = 0.0
            freshness_values: list[float] = []
            provider_counter: Counter[str] = Counter()
            headline_samples: list[str] = []
            for article in articles:
                article_score = self._score_article(article)
                freshness = self._freshness_score(article.get("published_at"))
                confidence = max(0.2, min(1.0, 0.45 + abs(article_score) * 0.35 + freshness * 0.2))
                polarity_sum += article_score * freshness
                confidence_sum += confidence
                freshness_values.append(freshness)
                provider = str(article.get("provider") or "unknown")
                provider_counter[provider] += 1
                source_mix[provider] += 1
                if len(headline_samples) < 3:
                    headline_samples.append(str(article.get("title") or ""))

            article_count = len(articles)
            polarity = max(-1.0, min(1.0, polarity_sum / max(article_count, 1)))
            confidence = max(0.0, min(1.0, confidence_sum / max(article_count, 1)))
            freshness = max(freshness_values) if freshness_values else 0.0
            feature_value = max(0.0, min(100.0, 50.0 + polarity * 35.0 + (confidence - 0.5) * 10.0))
            symbol_rows.append(
                SentimentSymbolScore(
                    symbol=symbol,
                    polarity=round(polarity, 4),
                    confidence=round(confidence, 4),
                    article_count=article_count,
                    freshness_score=round(freshness, 4),
                    source_mix=dict(provider_counter),
                    headline_samples=headline_samples,
                    feature_value=round(feature_value, 2),
                )
            )
            headline_count += article_count
            weighted_total += polarity * article_count
            weight_denominator += article_count

        overall_polarity = weighted_total / max(weight_denominator, 1.0)
        overall_confidence = (
            sum(row.confidence for row in symbol_rows) / max(len(symbol_rows), 1)
            if symbol_rows
            else 0.0
        )
        overall_freshness = (
            sum(row.freshness_score for row in symbol_rows) / max(len(symbol_rows), 1)
            if symbol_rows
            else 0.0
        )
        return SentimentSnapshot(
            snapshot_id=f"sentiment-{uuid.uuid4().hex[:12]}",
            generated_at=utc_now(),
            universe=symbols,
            headline_count=headline_count,
            overall_polarity=round(overall_polarity, 4),
            confidence=round(overall_confidence, 4),
            source_mix=dict(source_mix),
            freshness_score=round(overall_freshness, 4),
            symbol_scores=symbol_rows,
            lineage=[
                "yfinance news primary feed",
                "optional free-tier news enrichers",
                "headline lexicon polarity scoring",
                "0-100 sentiment feature projection",
            ],
            warnings=warnings,
            metadata={"free_first": True},
        )
