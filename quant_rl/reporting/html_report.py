from __future__ import annotations

from pathlib import Path
from typing import Any


def render_backtest_report(
    run_id: str,
    metrics: dict[str, Any],
    equity_curve_path: str,
    output_path: str | Path,
) -> str:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = "\n".join(
        f"<tr><td>{k}</td><td>{v:.6f}</td></tr>" if isinstance(v, (int, float)) else f"<tr><td>{k}</td><td>{v}</td></tr>"
        for k, v in metrics.items()
    )
    html = f"""
    <html>
      <head>
        <meta charset="utf-8" />
        <title>Backtest Report - {run_id}</title>
        <style>
          body {{ font-family: Arial, sans-serif; margin: 24px; }}
          table {{ border-collapse: collapse; width: 420px; }}
          td, th {{ border: 1px solid #ddd; padding: 8px; }}
          th {{ background: #f5f5f5; text-align: left; }}
        </style>
      </head>
      <body>
        <h1>Backtest Report</h1>
        <p>Run ID: <strong>{run_id}</strong></p>
        <h2>Metrics</h2>
        <table>
          <tr><th>Metric</th><th>Value</th></tr>
          {rows}
        </table>
        <h2>Equity Curve</h2>
        <img src="{Path(equity_curve_path).name}" width="900" />
      </body>
    </html>
    """
    output_path.write_text(html, encoding="utf-8")
    return str(output_path)
