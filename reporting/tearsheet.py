from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from html import escape
from typing import Any


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _pct(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{float(value) * 100:.2f}%"


def _num(value: float | int | None, digits: int = 2) -> str:
    if value is None:
        return "-"
    return f"{float(value):,.{digits}f}"


def _daily_returns(timeline: list[dict[str, Any]]) -> list[float]:
    navs = [float(point.get("portfolio_nav") or 0.0) for point in timeline]
    returns: list[float] = []
    for previous, current in zip(navs, navs[1:]):
        if previous <= 0:
            returns.append(0.0)
        else:
            returns.append((current / previous) - 1.0)
    return returns


def _monthly_returns(timeline: list[dict[str, Any]]) -> dict[str, float]:
    by_month: dict[str, list[float]] = defaultdict(list)
    for point in timeline:
        date_value = str(point.get("date") or "")
        if not date_value:
            continue
        month_key = date_value[:7]
        by_month[month_key].append(float(point.get("portfolio_nav") or 0.0))
    monthly: dict[str, float] = {}
    for month, navs in by_month.items():
        if len(navs) < 2 or navs[0] <= 0:
            monthly[month] = 0.0
        else:
            monthly[month] = (navs[-1] / navs[0]) - 1.0
    return dict(sorted(monthly.items()))


def _monte_carlo_summary(returns: list[float]) -> dict[str, float]:
    if not returns:
        return {"drift": 0.0, "volatility": 0.0, "p05": 0.0, "p50": 0.0, "p95": 0.0}
    drift = _mean(returns)
    variance = _mean([(value - drift) ** 2 for value in returns])
    vol = variance ** 0.5
    scenarios = sorted(
        [
            (drift - 1.65 * vol) * 21,
            (drift - 0.65 * vol) * 21,
            drift * 21,
            (drift + 0.65 * vol) * 21,
            (drift + 1.65 * vol) * 21,
        ]
    )
    return {
        "drift": round(drift, 6),
        "volatility": round(vol, 6),
        "p05": round(scenarios[0], 6),
        "p50": round(scenarios[2], 6),
        "p95": round(scenarios[-1], 6),
    }


def _cost_sensitivity(metrics: dict[str, Any]) -> list[dict[str, Any]]:
    cumulative = float(metrics.get("cumulative_return") or 0.0)
    sharpe = float(metrics.get("sharpe") or 0.0)
    table: list[dict[str, Any]] = []
    for cost_bps in (0, 5, 10, 20):
        drag = cost_bps / 10000.0
        table.append(
            {
                "transaction_cost_bps": cost_bps,
                "cumulative_return": round(cumulative - drag * 2.4, 6),
                "sharpe": round(sharpe - drag * 20.0, 6),
            }
        )
    return table


def _table(headers: list[str], rows: list[list[str]]) -> str:
    head_html = "".join(f"<th>{escape(header)}</th>" for header in headers)
    row_html = "".join(
        "<tr>" + "".join(f"<td>{escape(cell)}</td>" for cell in row) + "</tr>"
        for row in rows
    )
    return f"<table><thead><tr>{head_html}</tr></thead><tbody>{row_html}</tbody></table>"


def build_output(payload: dict | None = None) -> dict:
    payload = payload or {}
    metrics = dict(payload.get("metrics") or {})
    timeline = list(payload.get("timeline") or [])
    positions = list(payload.get("positions") or [])
    alerts = list(payload.get("risk_alerts") or [])
    generated_at = str(payload.get("generated_at") or datetime.utcnow().isoformat())
    monthly = _monthly_returns(timeline)
    returns = _daily_returns(timeline)
    monte_carlo = _monte_carlo_summary(returns)
    cost_sensitivity = _cost_sensitivity(metrics)
    gross_exposure = _mean([float(point.get("gross_exposure") or 0.0) for point in timeline])
    top_positions = sorted(
        positions,
        key=lambda row: abs(float(row.get("weight") or 0.0)),
        reverse=True,
    )[:5]
    summary = {
        "cumulative_return": float(metrics.get("cumulative_return") or 0.0),
        "annualized_return": float(metrics.get("annualized_return") or 0.0),
        "annualized_volatility": float(metrics.get("annualized_volatility") or 0.0),
        "sharpe": float(metrics.get("sharpe") or 0.0),
        "max_drawdown": float(metrics.get("max_drawdown") or 0.0),
        "gross_exposure": round(gross_exposure, 6),
        "timeline_points": len(timeline),
    }
    sections = {
        "overview": {
            "strategy_name": payload.get("strategy_name"),
            "benchmark": payload.get("benchmark"),
            "period_start": payload.get("period_start"),
            "period_end": payload.get("period_end"),
            "data_source": payload.get("data_source"),
            "data_tier": payload.get("data_tier", "l1"),
            "market_depth_status": payload.get("market_depth_status", {}),
            "used_synthetic_fallback": bool(payload.get("used_synthetic_fallback")),
        },
        "monthly_returns": monthly,
        "monte_carlo": monte_carlo,
        "cost_sensitivity": cost_sensitivity,
        "top_positions": top_positions,
        "risk_alerts": alerts,
        "market_data_warnings": list(payload.get("market_data_warnings") or []),
    }
    metrics_table = _table(
        ["Metric", "Value"],
        [
            ["Cumulative Return", _pct(summary["cumulative_return"])],
            ["Annualized Return", _pct(summary["annualized_return"])],
            ["Annualized Volatility", _pct(summary["annualized_volatility"])],
            ["Sharpe", _num(summary["sharpe"], 2)],
            ["Max Drawdown", _pct(summary["max_drawdown"])],
            ["Gross Exposure", _pct(summary["gross_exposure"])],
        ],
    )
    monthly_table = _table(
        ["Month", "Return"],
        [[month, _pct(value)] for month, value in monthly.items()] or [["-", "-"]],
    )
    position_table = _table(
        ["Symbol", "Weight", "Expected Return", "Execution"],
        [
            [
                str(row.get("symbol") or "-"),
                _pct(float(row.get("weight") or 0.0)),
                _pct(float(row.get("expected_return") or 0.0)),
                str(row.get("execution_tactic") or row.get("side") or "-"),
            ]
            for row in top_positions
        ]
        or [["-", "-", "-", "-"]],
    )
    cost_table = _table(
        ["Cost (bps)", "Cumulative Return", "Sharpe"],
        [
            [
                str(item["transaction_cost_bps"]),
                _pct(item["cumulative_return"]),
                _num(item["sharpe"], 2),
            ]
            for item in cost_sensitivity
        ],
    )
    alerts_html = "".join(
        f"<li><strong>{escape(str(alert.get('level') or 'info').upper())}</strong>: "
        f"{escape(str(alert.get('title') or ''))} - {escape(str(alert.get('recommendation') or ''))}</li>"
        for alert in alerts
    ) or "<li>No blocking alerts</li>"
    depth_status = dict(payload.get("market_depth_status") or {})
    html = f"""
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>{escape(str(payload.get("strategy_name") or "Backtest Tearsheet"))}</title>
    <style>
      body {{ font-family: Arial, sans-serif; margin: 24px; color: #10203a; background: #f5f8fb; }}
      h1, h2 {{ margin: 0 0 12px; }}
      section {{ background: #ffffff; border: 1px solid #d8e1eb; padding: 16px; margin: 0 0 16px; }}
      table {{ border-collapse: collapse; width: 100%; }}
      th, td {{ border: 1px solid #d8e1eb; padding: 8px; text-align: left; font-size: 13px; }}
      th {{ background: #eef4fb; }}
      ul {{ margin: 0; padding-left: 20px; }}
      .meta {{ color: #50657d; font-size: 12px; margin-bottom: 16px; }}
    </style>
  </head>
  <body>
    <h1>{escape(str(payload.get("strategy_name") or "Backtest Tearsheet"))}</h1>
    <div class="meta">Generated {escape(generated_at)} | Benchmark {escape(str(payload.get("benchmark") or "-"))} | Data source {escape(str(payload.get("data_source") or "-"))} | Data tier {escape(str(payload.get("data_tier") or "l1"))}</div>
    <section>
      <h2>Overview</h2>
      {metrics_table}
    </section>
    <section>
      <h2>Market Depth</h2>
      <p>Tier {escape(str(payload.get("data_tier") or "l1"))} | Provider {escape(str(depth_status.get("selected_provider") or "daily_backtest_l1"))} | Gate {escape(str(depth_status.get("eligibility_status") or "pass"))}</p>
    </section>
    <section>
      <h2>Monthly Returns</h2>
      {monthly_table}
    </section>
    <section>
      <h2>Top Positions</h2>
      {position_table}
    </section>
    <section>
      <h2>Cost Sensitivity</h2>
      {cost_table}
    </section>
    <section>
      <h2>Risk Alerts</h2>
      <ul>{alerts_html}</ul>
    </section>
    <section>
      <h2>Monte Carlo Snapshot</h2>
      <p>P05 {_pct(monte_carlo["p05"])} | Median {_pct(monte_carlo["p50"])} | P95 {_pct(monte_carlo["p95"])}</p>
    </section>
  </body>
</html>
""".strip()
    return {
        "module": "tearsheet",
        "status": "ready",
        "summary": summary,
        "sections": sections,
        "html": html,
    }
