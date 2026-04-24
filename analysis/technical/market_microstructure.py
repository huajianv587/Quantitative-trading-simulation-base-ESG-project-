from __future__ import annotations

from typing import Any


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _bounded(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _session_for_index(index: int) -> str:
    if index < 6:
        return "open"
    if index < 14:
        return "midday"
    return "close"


def _default_records(payload: dict[str, Any]) -> list[dict[str, Any]]:
    symbol = str(payload.get("symbol") or "AAPL").upper()
    base_spread = float(payload.get("base_spread_bps") or 7.0)
    base_volume = float(payload.get("base_volume") or 120000.0)
    records: list[dict[str, Any]] = []
    for index in range(20):
        session = _session_for_index(index)
        spread = base_spread + (4.0 if session == "open" else 1.5 if session == "midday" else 3.0) + (index % 3) * 0.6
        impact = spread * (0.55 if session == "midday" else 0.8)
        fill = _bounded(0.96 - spread / 100.0 - (0.03 if session == "open" else 0.0), 0.4, 0.99)
        records.append(
            {
                "symbol": symbol,
                "bar_index": index,
                "session": session,
                "spread_bps": round(spread, 4),
                "quoted_spread_bps": round(spread * 0.92, 4),
                "impact_bps": round(impact, 4),
                "slippage_bps": round(impact * 0.7, 4),
                "fill_probability": round(fill, 6),
                "trade_size_pct_adv": round(0.03 + (index % 5) * 0.01, 4),
                "volume": round(base_volume * (1.4 if session == "open" else 0.75 if session == "midday" else 1.2), 2),
                "close_to_close_move": round((-0.001 + index * 0.0002), 6),
            }
        )
    return records


def _depth_records(payload: dict[str, Any]) -> list[dict[str, Any]]:
    snapshots = list(payload.get("order_book_snapshots") or [])
    records: list[dict[str, Any]] = []
    for index, snapshot in enumerate(snapshots):
        best_bid = float(snapshot.get("best_bid") or 0.0)
        best_ask = float(snapshot.get("best_ask") or 0.0)
        mid_price = float(snapshot.get("mid_price") or ((best_bid + best_ask) / 2.0 if best_bid and best_ask else 0.0))
        spread_bps = float(snapshot.get("spread_bps") or (((best_ask - best_bid) / mid_price) * 10000.0 if mid_price and best_ask >= best_bid else 0.0))
        total_bid = float(snapshot.get("total_bid_size") or 0.0)
        total_ask = float(snapshot.get("total_ask_size") or 0.0)
        depth = max(total_bid + total_ask, 1.0)
        impact = spread_bps * _bounded(18.0 / depth, 0.18, 0.95)
        slippage = impact * (0.62 if snapshot.get("is_real") else 0.78)
        fill = _bounded(0.99 - spread_bps / 100.0 + min(depth / 4000.0, 0.08), 0.45, 0.995)
        records.append(
            {
                "symbol": snapshot.get("symbol") or payload.get("symbol") or "AAPL",
                "bar_index": index,
                "session": str(snapshot.get("session") or _session_for_index(index)),
                "spread_bps": round(spread_bps, 6),
                "quoted_spread_bps": round(spread_bps * 0.94, 6),
                "impact_bps": round(impact, 6),
                "slippage_bps": round(slippage, 6),
                "fill_probability": round(fill, 6),
                "trade_size_pct_adv": round(min(depth / 100000.0, 0.4), 6),
                "volume": round(depth, 4),
                "close_to_close_move": round(float(snapshot.get("imbalance") or 0.0) * 0.0015, 6),
                "book_imbalance": round(float(snapshot.get("imbalance") or 0.0), 6),
                "is_real_provider": bool(snapshot.get("is_real")),
            }
        )
    return records


def analyze_payload(payload: dict | None = None) -> dict:
    payload = payload or {}
    order_book_snapshots = list(payload.get("order_book_snapshots") or [])
    proxy_mode = "none" if order_book_snapshots and any(snapshot.get("is_real") for snapshot in order_book_snapshots) else "l1"
    records = list(payload.get("records") or _depth_records(payload) or _default_records(payload))
    spreads = [float(row.get("spread_bps") or row.get("quoted_spread_bps") or 0.0) for row in records]
    impacts = [float(row.get("impact_bps") or 0.0) for row in records]
    slippage = [float(row.get("slippage_bps") or 0.0) for row in records]
    fills = [float(row.get("fill_probability") or 0.0) for row in records]
    volumes = [float(row.get("volume") or 0.0) for row in records]
    imbalances = [float(row.get("book_imbalance") or 0.0) for row in records]
    session_breakdown: dict[str, dict[str, float]] = {}
    for session in sorted({str(row.get("session") or "unknown") for row in records}):
        session_rows = [row for row in records if str(row.get("session") or "unknown") == session]
        session_breakdown[session] = {
            "avg_spread_bps": round(_mean([float(row.get("spread_bps") or 0.0) for row in session_rows]), 6),
            "avg_fill_probability": round(_mean([float(row.get("fill_probability") or 0.0) for row in session_rows]), 6),
            "avg_impact_bps": round(_mean([float(row.get("impact_bps") or 0.0) for row in session_rows]), 6),
            "avg_depth": round(_mean([float(row.get("volume") or 0.0) for row in session_rows]), 4),
            "bars": float(len(session_rows)),
        }
    warnings: list[str] = []
    if _mean(spreads) > 12.0:
        warnings.append("Average spread is elevated; prefer midpoint-aware routing or slower participation.")
    if _mean(fills) < 0.82:
        warnings.append("Expected fill probability is weak; execution quality sandbox should remain in review mode.")
    if max(impacts or [0.0]) > 15.0:
        warnings.append("Impact spikes exceed the preferred paper-trading comfort band.")
    best_session = min(session_breakdown.items(), key=lambda item: item[1]["avg_spread_bps"])[0] if session_breakdown else "midday"
    return {
        "module": "market_microstructure",
        "records": records,
        "summary": "Order-book-aware execution-quality analysis ready" if order_book_snapshots else "L1/minute execution-quality analysis ready",
        "proxy_mode": proxy_mode,
        "metrics": {
            "avg_spread_bps": round(_mean(spreads), 6),
            "avg_impact_bps": round(_mean(impacts), 6),
            "avg_slippage_bps": round(_mean(slippage), 6),
            "avg_fill_probability": round(_mean(fills), 6),
            "avg_volume": round(_mean(volumes), 2),
            "avg_imbalance": round(_mean(imbalances), 6),
            "avg_depth": round(_mean(volumes), 4),
            "best_session": best_session,
            "worst_spread_bps": round(max(spreads or [0.0]), 6),
        },
        "session_breakdown": session_breakdown,
        "warnings": warnings,
        "execution_scenarios": [
            {
                "name": "open",
                "delay_seconds": 8,
                "partial_fill_risk": "high",
                "auction_risk": "high",
            },
            {
                "name": "midday",
                "delay_seconds": 3,
                "partial_fill_risk": "medium",
                "auction_risk": "low",
            },
            {
                "name": "close",
                "delay_seconds": 5,
                "partial_fill_risk": "medium",
                "auction_risk": "high",
            },
            {
                "name": "halt",
                "delay_seconds": 60,
                "partial_fill_risk": "extreme",
                "auction_risk": "extreme",
            },
            {
                "name": "high_volatility",
                "delay_seconds": 18,
                "partial_fill_risk": "high",
                "auction_risk": "medium",
            },
        ],
        "order_book_summary": {
            "snapshot_count": len(order_book_snapshots),
            "proxy_mode": proxy_mode,
            "real_provider": any(snapshot.get("is_real") for snapshot in order_book_snapshots),
        },
    }
