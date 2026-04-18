#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quant_rl.infrastructure.settings import get_settings
from quant_rl.reporting.experiment_recorder import EXPERIMENT_GROUPS


METRIC_KEYS = ["sharpe_ratio", "max_drawdown", "sortino_ratio", "calmar_ratio", "annual_return", "turnover_rate", "win_rate"]


def _load_rows(results_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(results_root.rglob("metrics.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        group = str(payload.get("group") or path.parent.parent.name)
        rows.append({
            "group": group,
            "group_label": EXPERIMENT_GROUPS.get(group, {}).get("label", group),
            "seed": payload.get("seed"),
            "path": str(path),
            **{key: payload.get(key) for key in METRIC_KEYS},
        })
    return rows


def _mean(values: list[float]) -> float | None:
    values = [float(value) for value in values if value is not None and math.isfinite(float(value))]
    return sum(values) / len(values) if values else None


def _std(values: list[float]) -> float | None:
    values = [float(value) for value in values if value is not None and math.isfinite(float(value))]
    if len(values) < 2:
        return None
    mean = sum(values) / len(values)
    return math.sqrt(sum((value - mean) ** 2 for value in values) / (len(values) - 1))


def _bootstrap_ci(diffs: list[float], iterations: int = 5000, alpha: float = 0.05) -> dict[str, float | None]:
    diffs = [float(value) for value in diffs if math.isfinite(float(value))]
    if not diffs:
        return {"mean": None, "low": None, "high": None}
    rng = random.Random(42)
    samples = []
    for _ in range(iterations):
        sample = [rng.choice(diffs) for _ in diffs]
        samples.append(sum(sample) / len(sample))
    samples.sort()
    low_idx = int((alpha / 2) * (len(samples) - 1))
    high_idx = int((1 - alpha / 2) * (len(samples) - 1))
    return {"mean": sum(diffs) / len(diffs), "low": samples[low_idx], "high": samples[high_idx]}


def _sample_results_root(namespace: str, sample: str, formula_mode: str | None) -> Path:
    root = ROOT / "storage" / "quant" / "rl-experiments" / namespace
    if formula_mode:
        root = root / f"formula_{formula_mode}"
    if namespace == "paper-run":
        root = root / f"sample_{sample}"
    return root / "results"


def _paired(rows: list[dict[str, Any]], left_group: str, right_group: str, metric: str) -> dict[str, Any]:
    left = {str(row.get("seed")): row for row in rows if row.get("group") == left_group and row.get(metric) is not None}
    right = {str(row.get("seed")): row for row in rows if row.get("group") == right_group and row.get(metric) is not None}
    seeds = sorted(set(left).intersection(right))
    diffs = [float(right[seed][metric]) - float(left[seed][metric]) for seed in seeds]
    higher_is_better = metric not in {"max_drawdown"}
    improvement_diffs = diffs if higher_is_better else [-value for value in diffs]
    ci = _bootstrap_ci(improvement_diffs)
    positives = sum(1 for value in improvement_diffs if value > 0)
    sign_rate = positives / len(improvement_diffs) if improvement_diffs else None
    return {
        "left_group": left_group,
        "right_group": right_group,
        "metric": metric,
        "higher_is_better": higher_is_better,
        "paired_seeds": seeds,
        "raw_right_minus_left_diffs": diffs,
        "improvement_diffs": improvement_diffs,
        "mean_diff": ci["mean"],
        "bootstrap_ci95": [ci["low"], ci["high"]],
        "positive_sign_rate": sign_rate,
        "interpretation": (
            "positive_esg_contribution" if ci["low"] is not None and ci["low"] > 0
            else "negative_or_inconclusive_esg_contribution" if ci["high"] is not None and ci["high"] <= 0
            else "inconclusive"
        ),
    }


def _load_equity_curves(results_root: Path) -> dict[tuple[str, str], pd.DataFrame]:
    curves: dict[tuple[str, str], pd.DataFrame] = {}
    for curve_path in sorted(results_root.rglob("equity_curve.csv")):
        if curve_path.parent.name.startswith("seed"):
            group = curve_path.parent.parent.name
            seed = curve_path.parent.name.replace("seed", "")
        else:
            group = curve_path.parent.name
            seed = "baseline"
        try:
            frame = pd.read_csv(curve_path)
        except Exception:
            continue
        if "date" not in frame.columns:
            continue
        if "daily_return" not in frame.columns and "portfolio_value" in frame.columns:
            frame["daily_return"] = pd.to_numeric(frame["portfolio_value"], errors="coerce").pct_change().fillna(0.0)
        if "daily_return" not in frame.columns:
            continue
        compact = frame[["date", "daily_return"]].copy()
        compact["daily_return"] = pd.to_numeric(compact["daily_return"], errors="coerce")
        compact = compact.dropna(subset=["date", "daily_return"]).groupby("date", as_index=False).last()
        curves[(group, seed)] = compact
    return curves


def _block_bootstrap_mean(values: list[float], *, block_size: int = 20, iterations: int = 3000, alpha: float = 0.05) -> dict[str, float | None]:
    values = [float(value) for value in values if math.isfinite(float(value))]
    if not values:
        return {"mean": None, "low": None, "high": None}
    rng = random.Random(42)
    n = len(values)
    block_size = max(1, min(block_size, n))
    samples: list[float] = []
    for _ in range(iterations):
        sampled: list[float] = []
        while len(sampled) < n:
            start = rng.randrange(0, max(1, n - block_size + 1))
            sampled.extend(values[start : start + block_size])
        sampled = sampled[:n]
        samples.append(sum(sampled) / len(sampled))
    samples.sort()
    low_idx = int((alpha / 2) * (len(samples) - 1))
    high_idx = int((1 - alpha / 2) * (len(samples) - 1))
    return {"mean": sum(values) / len(values), "low": samples[low_idx], "high": samples[high_idx]}


def _paired_equity_bootstrap(curves: dict[tuple[str, str], pd.DataFrame], left_group: str, right_group: str) -> dict[str, Any]:
    left_seeds = {seed for group, seed in curves if group == left_group}
    right_seeds = {seed for group, seed in curves if group == right_group}
    paired_seeds = sorted(left_seeds.intersection(right_seeds))
    daily_diffs: list[float] = []
    per_seed: list[dict[str, Any]] = []
    for seed in paired_seeds:
        left = curves[(left_group, seed)].rename(columns={"daily_return": "left_return"})
        right = curves[(right_group, seed)].rename(columns={"daily_return": "right_return"})
        merged = left.merge(right, on="date", how="inner")
        if merged.empty:
            continue
        merged["diff"] = pd.to_numeric(merged["right_return"], errors="coerce") - pd.to_numeric(merged["left_return"], errors="coerce")
        diffs = [float(value) for value in merged["diff"].dropna()]
        daily_diffs.extend(diffs)
        if diffs:
            per_seed.append({"seed": seed, "days": len(diffs), "mean_daily_diff": sum(diffs) / len(diffs)})
    ci = _block_bootstrap_mean(daily_diffs)
    annualized = {key: (value * 252 if value is not None else None) for key, value in ci.items()}
    return {
        "left_group": left_group,
        "right_group": right_group,
        "paired_seeds": paired_seeds,
        "paired_days": len(daily_diffs),
        "per_seed": per_seed,
        "mean_daily_return_diff": ci["mean"],
        "daily_bootstrap_ci95": [ci["low"], ci["high"]],
        "annualized_return_diff": annualized["mean"],
        "annualized_bootstrap_ci95": [annualized["low"], annualized["high"]],
        "interpretation": (
            "positive_curve_contribution" if annualized["low"] is not None and annualized["low"] > 0
            else "negative_or_inconclusive_curve_contribution" if annualized["high"] is not None and annualized["high"] <= 0
            else "inconclusive"
        ),
    }


def _paper_tables_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# ESG/RL Paper Result Tables",
        "",
        "## Main Group Metrics",
        "",
        "| Group | Runs | Sharpe Mean | Max DD Mean | Annual Return Mean |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for group, item in sorted(payload.get("grouped", {}).items()):
        metrics = item.get("metrics", {})
        lines.append(
            "| {label} | {runs} | {sharpe} | {mdd} | {ann} |".format(
                label=item.get("label", group),
                runs=item.get("runs", 0),
                sharpe=_fmt(metrics.get("sharpe_ratio", {}).get("mean")),
                mdd=_fmt(metrics.get("max_drawdown", {}).get("mean")),
                ann=_fmt(metrics.get("annual_return", {}).get("mean")),
            )
        )
    lines.extend(["", "## Paired Equity-Curve Bootstrap", "", "| Comparison | Paired Days | Annualized Diff | CI95 | Interpretation |", "| --- | ---: | ---: | --- | --- |"])
    for item in payload.get("equity_curve_comparisons", []):
        ci = item.get("annualized_bootstrap_ci95") or [None, None]
        lines.append(
            f"| {item.get('right_group')} - {item.get('left_group')} | {item.get('paired_days')} | "
            f"{_fmt(item.get('annualized_return_diff'))} | [{_fmt(ci[0])}, {_fmt(ci[1])}] | {item.get('interpretation')} |"
        )
    lines.extend(
        [
            "",
            "## Paper Readout",
            "",
            f"- Primary result: `{payload.get('paper_readout', {}).get('primary_result')}`",
            "- Negative or mixed ESG contribution remains publishable as evidence that annual RAG ESG signals may be too low-frequency for short-horizon RL.",
        ]
    )
    return "\n".join(lines) + "\n"


def _fmt(value: Any) -> str:
    try:
        if value is None or not math.isfinite(float(value)):
            return ""
        return f"{float(value):.4f}"
    except Exception:
        return ""


def build_report(results_root: Path, output_dir: Path, *, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    rows = _load_rows(results_root)
    curves = _load_equity_curves(results_root)
    output_dir.mkdir(parents=True, exist_ok=True)
    grouped: dict[str, dict[str, Any]] = {}
    for group in sorted({row["group"] for row in rows}):
        group_rows = [row for row in rows if row["group"] == group]
        grouped[group] = {
            "label": EXPERIMENT_GROUPS.get(group, {}).get("label", group),
            "runs": len(group_rows),
            "metrics": {
                metric: {
                    "mean": _mean([row.get(metric) for row in group_rows]),
                    "std": _std([row.get(metric) for row in group_rows]),
                }
                for metric in METRIC_KEYS
            },
        }

    comparisons = [
        _paired(rows, "B3_sac_noesg", "B4_sac_esg", "sharpe_ratio"),
        _paired(rows, "B3_sac_noesg", "B4_sac_esg", "max_drawdown"),
        _paired(rows, "B4_sac_esg", "OURS_full", "sharpe_ratio"),
    ]
    equity_curve_comparisons = [
        _paired_equity_bootstrap(curves, "B3_sac_noesg", "B4_sac_esg"),
        _paired_equity_bootstrap(curves, "B4_sac_esg", "OURS_full"),
    ]
    payload = {
        "metadata": metadata or {},
        "results_root": str(results_root),
        "rows": rows,
        "grouped": grouped,
        "comparisons": comparisons,
        "equity_curve_comparisons": equity_curve_comparisons,
        "paper_readout": {
            "primary_claim_metric": "B4_sac_esg minus B3_sac_noesg Sharpe",
            "primary_result": comparisons[0]["interpretation"] if comparisons else "missing",
            "negative_result_is_publishable": True,
        },
    }
    json_path = output_dir / "esg_contribution_report.json"
    csv_path = output_dir / "esg_contribution_rows.csv"
    equity_csv_path = output_dir / "equity_curve_bootstrap.csv"
    markdown_path = output_dir / "paper_result_tables.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    pd.DataFrame(rows).to_csv(csv_path, index=False)
    pd.DataFrame(equity_curve_comparisons).to_csv(equity_csv_path, index=False)
    markdown_path.write_text(_paper_tables_markdown(payload), encoding="utf-8")
    payload["json_path"] = str(json_path)
    payload["csv_path"] = str(csv_path)
    payload["equity_curve_bootstrap_csv_path"] = str(equity_csv_path)
    payload["paper_tables_markdown_path"] = str(markdown_path)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize ESG-vs-noESG RL contribution with paired bootstrap CIs.")
    parser.add_argument("--results-root", default=None)
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--run-namespace", default=None, choices=["smoke", "dev", "paper-run"])
    parser.add_argument("--sample", default="full_2022_2025", choices=["full_2022_2025", "post_esg_effective"])
    parser.add_argument("--formula-mode", default=None, choices=[None, "v2", "v2_1"])
    args = parser.parse_args()
    if args.run_namespace:
        namespace_root = _sample_results_root(args.run_namespace, args.sample, args.formula_mode).parent
        os.environ["QUANT_RL_EXPERIMENT_ROOT"] = str(namespace_root)
        get_settings.cache_clear()
    settings = get_settings()
    results_root = Path(args.results_root) if args.results_root else settings.experiment_root / "results"
    output_dir = Path(args.output_dir) if args.output_dir else settings.experiment_root / "summary"
    report = build_report(results_root, output_dir, metadata={"run_namespace": args.run_namespace, "sample": args.sample, "formula_mode": args.formula_mode})
    print(json.dumps({k: v for k, v in report.items() if k not in {"rows"}}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
