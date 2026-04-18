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


def build_report(results_root: Path, output_dir: Path, *, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    rows = _load_rows(results_root)
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
    payload = {
        "metadata": metadata or {},
        "results_root": str(results_root),
        "rows": rows,
        "grouped": grouped,
        "comparisons": comparisons,
        "paper_readout": {
            "primary_claim_metric": "B4_sac_esg minus B3_sac_noesg Sharpe",
            "primary_result": comparisons[0]["interpretation"] if comparisons else "missing",
            "negative_result_is_publishable": True,
        },
    }
    json_path = output_dir / "esg_contribution_report.json"
    csv_path = output_dir / "esg_contribution_rows.csv"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    pd.DataFrame(rows).to_csv(csv_path, index=False)
    payload["json_path"] = str(json_path)
    payload["csv_path"] = str(csv_path)
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
        namespace_root = ROOT / "storage" / "quant" / "rl-experiments" / args.run_namespace
        if args.formula_mode:
            namespace_root = namespace_root / f"formula_{args.formula_mode}"
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
