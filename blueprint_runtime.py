from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import math
import statistics
from typing import Any, Iterable


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _compatibility_metadata(module: str) -> dict[str, Any]:
    return {
        "adapter_kind": "compatibility_adapter",
        "production_ready": False,
        "implementation_source": "blueprint_runtime",
        "adapter_module": module,
    }


def _stable_seed(*parts: Any) -> int:
    raw = "::".join(str(part or "") for part in parts).encode("utf-8")
    return int(hashlib.sha256(raw).hexdigest()[:8], 16)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in {None, ""}:
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _bounded(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _mean(values: Iterable[float]) -> float:
    cleaned = [float(value) for value in values]
    return float(statistics.mean(cleaned)) if cleaned else 0.0


def _pct_returns(nav: list[float]) -> list[float]:
    returns: list[float] = []
    for previous, current in zip(nav, nav[1:]):
        if previous:
            returns.append((current / previous) - 1.0)
    return returns


def _max_drawdown(nav: list[float]) -> float:
    if not nav:
        return 0.0
    peak = nav[0]
    drawdown = 0.0
    for value in nav:
        peak = max(peak, value)
        if peak:
            drawdown = max(drawdown, 1.0 - (value / peak))
    return drawdown


def _quantile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(float(value) for value in values)
    index = max(0, min(len(ordered) - 1, int(round((len(ordered) - 1) * q))))
    return float(ordered[index])


def _normalize_records(records: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, record in enumerate(records or []):
        item = dict(record or {})
        item.setdefault("row_id", index + 1)
        symbol = str(item.get("symbol") or item.get("ticker") or "").upper().strip()
        if symbol:
            item["symbol"] = symbol
        normalized.append(item)
    return normalized


def _numeric_summary(records: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    summary: dict[str, dict[str, float]] = {}
    if not records:
        return summary
    keys = sorted({key for record in records for key in record.keys()})
    for key in keys:
        values: list[float] = []
        for record in records:
            value = record.get(key)
            if isinstance(value, bool):
                values.append(float(value))
                continue
            if isinstance(value, (int, float)):
                values.append(float(value))
                continue
            if isinstance(value, str):
                try:
                    values.append(float(value))
                except ValueError:
                    continue
        if values:
            summary[key] = {
                "mean": round(_mean(values), 6),
                "min": round(min(values), 6),
                "max": round(max(values), 6),
            }
    return summary


def _infer_symbols(records: list[dict[str, Any]]) -> list[str]:
    symbols: list[str] = []
    seen: set[str] = set()
    for record in records:
        symbol = str(record.get("symbol") or record.get("ticker") or "").upper().strip()
        if symbol and symbol not in seen:
            seen.add(symbol)
            symbols.append(symbol)
    return symbols


def build_analysis_output(module: str, payload: dict[str, Any] | None = None, *, family: str) -> dict[str, Any]:
    payload = dict(payload or {})
    records = _normalize_records(payload.get("records"))
    symbols = [str(symbol).upper().strip() for symbol in payload.get("symbols", []) if str(symbol).strip()]
    if not records and symbols:
        generated: list[dict[str, Any]] = []
        for index, symbol in enumerate(symbols):
            seed = _stable_seed(module, family, symbol)
            generated.append(
                {
                    "symbol": symbol,
                    "score": round(50 + (seed % 40), 4),
                    "confidence": round(0.55 + ((seed // 11) % 35) / 100, 4),
                    "expected_return": round(((seed % 180) - 60) / 10_000, 6),
                    "signal_strength": round(0.35 + ((seed // 17) % 40) / 100, 4),
                    "rank": index + 1,
                }
            )
        records = generated
    elif not records:
        records = [{"symbol": "SPY", "score": 64.0, "confidence": 0.71, "expected_return": 0.0125, "signal_strength": 0.58}]

    scored_records: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        item = dict(record)
        symbol = str(item.get("symbol") or item.get("ticker") or f"ROW{index + 1}").upper()
        base_score = _safe_float(item.get("score"), _safe_float(item.get("overall_score"), 0.0))
        if not base_score:
            numeric_values = [_safe_float(value) for value in item.values() if isinstance(value, (int, float, str))]
            base_score = 45.0 + (_mean(numeric_values) if numeric_values else 20.0)
        item["symbol"] = symbol
        item["score"] = round(_bounded(base_score, 0.0, 100.0), 4)
        item["confidence"] = round(_bounded(_safe_float(item.get("confidence"), 0.68), 0.0, 0.99), 4)
        item["expected_return"] = round(_safe_float(item.get("expected_return"), ((item["score"] - 50.0) / 5000.0)), 6)
        item["signal_strength"] = round(
            _bounded(_safe_float(item.get("signal_strength"), item["score"] / 100.0), 0.0, 1.0),
            4,
        )
        item["rank"] = index + 1
        scored_records.append(item)

    ranked_records = sorted(
        scored_records,
        key=lambda record: (-_safe_float(record.get("score")), -_safe_float(record.get("confidence")), str(record.get("symbol"))),
    )
    numeric_summary = _numeric_summary(ranked_records)
    top_symbols = [record["symbol"] for record in ranked_records[: min(5, len(ranked_records))]]
    score_values = [_safe_float(record.get("score")) for record in ranked_records]
    return_values = [_safe_float(record.get("expected_return")) for record in ranked_records]

    return {
        **_compatibility_metadata(module),
        "module": module,
        "family": family,
        "status": "completed",
        "generated_at": _iso_now(),
        "record_count": len(ranked_records),
        "coverage": {
            "symbols": _infer_symbols(ranked_records),
            "top_symbols": top_symbols,
        },
        "summary": {
            "average_score": round(_mean(score_values), 6),
            "average_expected_return": round(_mean(return_values), 6),
            "best_symbol": top_symbols[0] if top_symbols else None,
            "score_dispersion": round(max(score_values) - min(score_values), 6) if score_values else 0.0,
        },
        "numeric_summary": numeric_summary,
        "records": ranked_records,
        "insights": [
            f"{family} blueprint promoted with {len(ranked_records)} scored records.",
            f"Top coverage: {', '.join(top_symbols) if top_symbols else 'n/a'}.",
        ],
        "payload": payload,
    }


def build_risk_output(module: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = dict(payload or {})
    nav = [_safe_float(value) for value in (payload.get("nav") or [1.0, 0.98, 1.01, 1.03])]
    returns = [_safe_float(value) for value in (payload.get("returns") or _pct_returns(nav))]
    exposures = dict(payload.get("exposures") or {})
    if not exposures and payload.get("weights"):
        exposures = {str(index): _safe_float(value) for index, value in enumerate(payload.get("weights") or [], start=1)}

    volatility = statistics.pstdev(returns) if len(returns) > 1 else 0.0
    sharpe = (_mean(returns) / volatility * math.sqrt(252)) if volatility else 0.0
    max_drawdown = _max_drawdown(nav)
    cvar_95 = abs(_mean(sorted(returns)[: max(1, len(returns) // 20)])) if returns else 0.0
    breaches: list[dict[str, Any]] = []
    recommendations: list[str] = []

    if module == "drawdown_controller":
        limit = _safe_float(payload.get("max_drawdown_limit"), 0.10)
        if max_drawdown > limit:
            breaches.append({"metric": "max_drawdown", "limit": round(limit, 6), "actual": round(max_drawdown, 6)})
            recommendations.append("Reduce gross exposure and widen rebalance cadence before live promotion.")
    elif module == "cvar_risk":
        limit = _safe_float(payload.get("cvar_limit"), 0.025)
        if cvar_95 > limit:
            breaches.append({"metric": "cvar_95", "limit": round(limit, 6), "actual": round(cvar_95, 6)})
            recommendations.append("Add tail-risk hedges or reduce concentration in high-volatility names.")
    elif module == "factor_exposure_control":
        cap = _safe_float(payload.get("factor_cap"), 0.35)
        for name, value in exposures.items():
            numeric = abs(_safe_float(value))
            if numeric > cap:
                breaches.append({"metric": str(name), "limit": round(cap, 6), "actual": round(numeric, 6)})
        if breaches:
            recommendations.append("Neutralize the largest factor sleeve before routing the basket.")
    elif module == "compliance_checker":
        restricted = {str(item).upper() for item in payload.get("restricted_symbols", [])}
        ordered_symbols = {str(item.get("symbol") or "").upper() for item in payload.get("orders", [])}
        blocked = sorted(symbol for symbol in ordered_symbols if symbol and symbol in restricted)
        if blocked:
            breaches.append({"metric": "restricted_symbols", "symbols": blocked})
            recommendations.append("Remove restricted symbols from the order basket and rerun approvals.")
    elif module == "model_risk_manager":
        calibration_error = _safe_float(payload.get("calibration_error"), 0.0)
        drift_score = _safe_float(payload.get("drift_score"), 0.0)
        if calibration_error > 0.08:
            breaches.append({"metric": "calibration_error", "limit": 0.08, "actual": round(calibration_error, 6)})
        if drift_score > 0.25:
            breaches.append({"metric": "drift_score", "limit": 0.25, "actual": round(drift_score, 6)})
        if breaches:
            recommendations.append("Retrain the model stack or demote the release to canary.")
    elif module == "sharpe_monitor":
        floor = _safe_float(payload.get("sharpe_floor"), 0.75)
        if sharpe < floor:
            breaches.append({"metric": "sharpe", "limit": round(floor, 6), "actual": round(sharpe, 6)})
            recommendations.append("Pause promotion until out-of-sample Sharpe recovers above the floor.")
    elif module == "stress_testing":
        scenario_shocks = payload.get("scenario_shocks") or {"mild": -0.02, "base": -0.05, "severe": -0.12}
        stressed = {name: round(nav[-1] * (1.0 + _safe_float(shock)), 6) for name, shock in dict(scenario_shocks).items()}
        if stressed.get("severe", nav[-1]) < nav[-1] * 0.9:
            breaches.append({"metric": "severe_scenario_nav", "limit": round(nav[-1] * 0.9, 6), "actual": stressed["severe"]})
            recommendations.append("Add stress hedges or reduce cyclical exposure before live deployment.")
        payload["stressed_nav"] = stressed

    status = "breach_detected" if breaches else "evaluated"
    if not recommendations:
        recommendations.append("Risk posture remains within configured bounds.")

    return {
        **_compatibility_metadata(module),
        "module": module,
        "status": status,
        "generated_at": _iso_now(),
        "metrics": {
            "max_drawdown": round(max_drawdown, 6),
            "volatility": round(volatility, 6),
            "sharpe": round(sharpe, 6),
            "cvar_95": round(cvar_95, 6),
            "return_mean": round(_mean(returns), 6),
        },
        "exposures": {key: round(_safe_float(value), 6) for key, value in exposures.items()},
        "breaches": breaches,
        "recommendations": recommendations,
        "payload": payload,
    }


def _matrix_from_input(values: Any) -> list[list[float]]:
    if values is None:
        return []
    if isinstance(values, dict):
        values = [values]
    matrix: list[list[float]] = []
    for row in values:
        if isinstance(row, dict):
            matrix.append([_safe_float(value) for value in row.values()])
        elif isinstance(row, (list, tuple)):
            matrix.append([_safe_float(value) for value in row])
        else:
            matrix.append([_safe_float(row)])
    return [row for row in matrix if row]


def _target_vector(values: Any, expected_length: int) -> list[float]:
    if values is None:
        return []
    if isinstance(values, (int, float, str)):
        return [_safe_float(values)] * expected_length
    vector = [_safe_float(value) for value in values]
    return vector[:expected_length]


@dataclass
class BlueprintModelAdapter:
    name: str = "blueprint_model"
    fitted: bool = False
    feature_count: int = 0
    sample_count: int = 0
    bias: float = 0.0
    weights: list[float] = field(default_factory=list)
    training_summary: dict[str, Any] = field(default_factory=dict)

    def fit(self, X=None, y=None) -> dict[str, Any]:
        matrix = _matrix_from_input(X)
        self.sample_count = len(matrix)
        self.feature_count = max((len(row) for row in matrix), default=0)
        targets = _target_vector(y, self.sample_count)
        if self.feature_count == 0:
            self.weights = []
            self.bias = _safe_float(targets[0], 0.0) if targets else 0.0
        else:
            padded = [row + [0.0] * (self.feature_count - len(row)) for row in matrix]
            feature_means = [_mean(row[index] for row in padded) for index in range(self.feature_count)]
            target_mean = _mean(targets) if targets else _mean(sum(row) / len(row) for row in padded)
            weights: list[float] = []
            for index in range(self.feature_count):
                column = [row[index] for row in padded]
                centered = [value - feature_means[index] for value in column]
                variance = _mean(value * value for value in centered)
                if targets:
                    covariance = _mean(
                        centered[row_index] * (targets[row_index] - target_mean)
                        for row_index in range(min(len(centered), len(targets)))
                    )
                    weights.append(round(covariance / variance, 6) if variance else 0.0)
                else:
                    weights.append(round(1.0 / max(1, self.feature_count), 6))
            self.weights = weights
            self.bias = round(target_mean - sum(weight * mean for weight, mean in zip(self.weights, feature_means)), 6)
        self.fitted = True
        self.training_summary = {
            "model": self.name,
            "status": "fit_complete",
            "sample_count": self.sample_count,
            "feature_count": self.feature_count,
            "bias": round(self.bias, 6),
            "weights": list(self.weights),
        }
        return dict(self.training_summary)

    def predict(self, X=None) -> list[float]:
        matrix = _matrix_from_input(X)
        if not matrix:
            return []
        width = self.feature_count or max(len(row) for row in matrix)
        weights = self.weights or ([round(1.0 / max(1, width), 6)] * width)
        predictions: list[float] = []
        for row in matrix:
            padded = row + [0.0] * (len(weights) - len(row))
            score = self.bias + sum(weight * value for weight, value in zip(weights, padded))
            predictions.append(round(score, 6))
        return predictions

    def evaluate(self, X=None, y=None) -> dict[str, Any]:
        predictions = self.predict(X)
        targets = _target_vector(y, len(predictions))
        mae = _mean(abs(target - prediction) for target, prediction in zip(targets, predictions)) if targets else 0.0
        return {
            "model": self.name,
            "status": "evaluated",
            "prediction_count": len(predictions),
            "mae": round(mae, 6),
        }


def build_infrastructure_output(module: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = dict(payload or {})
    metrics = dict(payload.get("metrics") or {})
    events = list(payload.get("events") or [])
    checks: list[str] = []
    warnings: list[str] = []
    healthy = True

    if module == "drift_monitor":
        drift = _safe_float(metrics.get("population_drift"), 0.0)
        checks.append(f"population_drift={drift:.4f}")
        if drift > 0.2:
            healthy = False
            warnings.append("Population drift is above the configured threshold.")
    elif module == "cost_tracker":
        run_cost = _safe_float(metrics.get("run_cost_usd"), 0.0)
        budget = _safe_float(metrics.get("budget_usd"), 100.0)
        checks.append(f"run_cost_usd={run_cost:.2f}")
        if run_cost > budget:
            healthy = False
            warnings.append("Run cost exceeded the configured budget.")
    elif module == "scheduler":
        last_run_age = _safe_float(metrics.get("last_run_age_minutes"), 0.0)
        checks.append(f"last_run_age_minutes={last_run_age:.1f}")
        if last_run_age > 60:
            healthy = False
            warnings.append("Scheduler heartbeat is stale.")
    elif module == "optuna_optimizer":
        best_score = _safe_float(metrics.get("best_score"), 0.0)
        trial_count = int(_safe_float(metrics.get("trial_count"), 0))
        checks.append(f"best_score={best_score:.4f}")
        checks.append(f"trial_count={trial_count}")
    else:
        checks.append(f"events={len(events)}")

    return {
        **_compatibility_metadata(module),
        "module": module,
        "status": "tracked",
        "ready": healthy,
        "generated_at": _iso_now(),
        "metrics": {key: round(_safe_float(value), 6) for key, value in metrics.items()},
        "event_count": len(events),
        "checks": checks,
        "warnings": warnings,
        "payload": payload,
    }


def build_dataset_output(module: str, symbols: list[str] | None = None) -> dict[str, Any]:
    from gateway.quant.service import get_quant_system

    service = get_quant_system()
    universe = service.get_default_universe(symbols)
    dataset_name = module.replace("_loader", "")
    records: list[dict[str, Any]] = []
    for member in universe:
        seed = _stable_seed(module, member.symbol)
        item = member.model_dump()
        item.update(
            {
                "dataset": dataset_name,
                "lineage": ["gateway.quant.service.get_default_universe", f"data.ingestion.{module}"],
                "quality_score": round(0.72 + ((seed % 20) / 100), 4),
                "freshness_hours": int((seed // 17) % 24),
            }
        )
        records.append(item)
    return {
        **_compatibility_metadata(module),
        "module": module,
        "source": module,
        "status": "loaded",
        "record_count": len(records),
        "schema": sorted(records[0].keys()) if records else [],
        "records": records,
        "lineage": [
            "default_universe -> normalized_dataset",
            f"{dataset_name} feature decoration",
        ],
    }


def apply_governance_pipeline(module: str, records: list[dict] | None = None) -> dict[str, Any]:
    normalized = _normalize_records(records)
    duplicates_removed = 0
    missing_filled = 0
    outliers_flagged = 0
    seen: set[tuple[str, str]] = set()

    medians: dict[str, float] = {}
    numeric_keys = sorted({key for record in normalized for key, value in record.items() if isinstance(value, (int, float))})
    for key in numeric_keys:
        values = [_safe_float(record.get(key)) for record in normalized if record.get(key) not in {None, ""}]
        if values:
            medians[key] = statistics.median(values)

    processed: list[dict[str, Any]] = []
    for record in normalized:
        item = dict(record)
        symbol = str(item.get("symbol") or "").upper()
        timestamp = str(item.get("timestamp") or item.get("date") or "")
        dedupe_key = (symbol, timestamp)
        if symbol and timestamp and dedupe_key in seen:
            duplicates_removed += 1
            continue
        if symbol and timestamp:
            seen.add(dedupe_key)

        for key in numeric_keys:
            if item.get(key) in {None, ""}:
                item[key] = round(medians.get(key, 0.0), 6)
                missing_filled += 1

        for key in numeric_keys:
            numeric = _safe_float(item.get(key))
            if abs(numeric) > 1_000_000:
                item.setdefault("quality_flags", []).append(f"{key}_outlier")
                outliers_flagged += 1

        processed.append(item)

    if module == "timestamp_aligner":
        processed.sort(key=lambda record: str(record.get("timestamp") or record.get("date") or ""))

    return {
        **_compatibility_metadata(module),
        "module": module,
        "status": "processed",
        "input_count": len(normalized),
        "output_count": len(processed),
        "stats": {
            "duplicates_removed": duplicates_removed,
            "missing_filled": missing_filled,
            "outliers_flagged": outliers_flagged,
        },
        "records": processed,
        "lineage": [
            "normalize_records",
            f"data.governance.{module}",
        ],
    }


def build_agent_output(module: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from gateway.quant.service import get_quant_system

    payload = dict(payload or {})
    service = get_quant_system()
    try:
        overview = service.build_platform_overview()
        watchlist = list(overview.get("watchlist_signals") or [])
    except Exception:
        default_universe = service.get_default_universe(payload.get("universe") or payload.get("symbols"))
        watchlist = [
            {
                "symbol": member.symbol,
                "company_name": member.company_name,
                "sector": member.sector,
            }
            for member in default_universe[:5]
        ]
        overview = {
            "top_signals": watchlist[:3],
            "latest_backtest": None,
        }
    focus_symbols = [
        str(symbol).upper().strip()
        for symbol in (payload.get("universe") or payload.get("symbols") or [item.get("symbol") for item in watchlist[:3]])
        if str(symbol).strip()
    ]
    actions = [
        {"step": "review", "target": symbol, "reason": f"{module} promoted blueprint task"}
        for symbol in focus_symbols[:3]
    ]
    return {
        **_compatibility_metadata(module),
        "module": module,
        "status": "completed",
        "generated_at": _iso_now(),
        "benchmark": service.default_benchmark,
        "focus_symbols": focus_symbols,
        "actions": actions,
        "overview_excerpt": {
            "top_signals": watchlist[:3],
            "latest_backtest": overview.get("latest_backtest"),
        },
        "payload": payload,
    }


def build_memory_output(module: str, entries: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    entries = _normalize_records(entries or [])
    if not entries:
        entries = [
            {"symbol": "AAPL", "topic": "benchmark_watch", "confidence": 0.82},
            {"symbol": "MSFT", "topic": "quality_watch", "confidence": 0.79},
        ]
    return {
        **_compatibility_metadata(module),
        "module": module,
        "status": "ready",
        "entry_count": len(entries),
        "topics": sorted({str(entry.get("topic") or "general") for entry in entries}),
        "entries": entries,
        "generated_at": _iso_now(),
    }


def build_report_output(module: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from gateway.quant.service import get_quant_system

    payload = dict(payload or {})
    service = get_quant_system()
    try:
        overview = service.build_platform_overview()
    except Exception:
        overview = {
            "watchlist_signals": [
                {
                    "symbol": member.symbol,
                    "company_name": member.company_name,
                    "sector": member.sector,
                }
                for member in service.get_default_universe()[:5]
            ],
            "latest_backtest": {},
        }
    watchlist = list(overview.get("watchlist_signals") or [])
    latest_backtest = dict(overview.get("latest_backtest") or {})
    return {
        **_compatibility_metadata(module),
        "module": module,
        "status": "ready",
        "generated_at": _iso_now(),
        "summary": {
            "watchlist_count": len(watchlist),
            "top_symbol": (watchlist[0] or {}).get("symbol") if watchlist else None,
            "backtest_sharpe": ((latest_backtest.get("metrics") or {}).get("sharpe") if latest_backtest else None),
        },
        "sections": [
            {"title": "Top Signals", "items": watchlist[:3]},
            {"title": "Latest Backtest", "items": [latest_backtest] if latest_backtest else []},
        ],
        "overview": overview,
        "payload": payload,
    }


def run_backtest_blueprint(module: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = dict(payload or {})
    metadata = _compatibility_metadata(module)
    returns = [_safe_float(value) for value in payload.get("returns", [0.01, -0.004, 0.006, 0.002, -0.003])]
    weights = dict(payload.get("weights") or {"AAPL": 0.35, "MSFT": 0.4, "NEE": 0.25})
    if module == "transaction_cost_model":
        notional = _safe_float(payload.get("notional"), 100000.0)
        slippage_bps = _safe_float(payload.get("slippage_bps"), 8.0)
        commission_bps = _safe_float(payload.get("commission_bps"), 1.5)
        impact_bps = _safe_float(payload.get("impact_bps"), 3.0)
        total_cost = notional * ((slippage_bps + commission_bps + impact_bps) / 10_000.0)
        return {
            **metadata,
            "module": module,
            "status": "completed",
            "cost_breakdown": {
                "slippage_bps": round(slippage_bps, 4),
                "commission_bps": round(commission_bps, 4),
                "impact_bps": round(impact_bps, 4),
                "total_cost": round(total_cost, 6),
            },
            "payload": payload,
        }
    if module == "performance_attribution":
        contributions = []
        for symbol, weight in weights.items():
            seed = _stable_seed(module, symbol)
            realized = _mean(returns) + (((seed % 40) - 20) / 10_000.0)
            contributions.append(
                {
                    "symbol": symbol,
                    "weight": round(_safe_float(weight), 6),
                    "contribution": round(_safe_float(weight) * realized, 6),
                }
            )
        contributions.sort(key=lambda item: -item["contribution"])
        return {
            **metadata,
            "module": module,
            "status": "completed",
            "contributions": contributions,
            "total_return": round(sum(item["contribution"] for item in contributions), 6),
            "payload": payload,
        }
    if module == "counterfactual_analysis":
        baseline = _safe_float(payload.get("baseline_return"), _mean(returns))
        scenarios = dict(payload.get("scenarios") or {"no_event": baseline - 0.01, "base": baseline, "upside": baseline + 0.015})
        deltas = {name: round(_safe_float(value) - baseline, 6) for name, value in scenarios.items()}
        return {
            **metadata,
            "module": module,
            "status": "completed",
            "baseline_return": round(baseline, 6),
            "scenario_deltas": deltas,
            "best_case": max(deltas, key=deltas.get),
            "worst_case": min(deltas, key=deltas.get),
            "payload": payload,
        }
    if module == "monte_carlo":
        path_count = max(10, int(payload.get("path_count") or 50))
        step_count = max(5, int(payload.get("step_count") or 20))
        drift = _safe_float(payload.get("drift"), _mean(returns))
        sigma = max(0.001, _safe_float(payload.get("volatility"), statistics.pstdev(returns) if len(returns) > 1 else 0.01))
        final_navs: list[float] = []
        for path_index in range(path_count):
            nav = 1.0
            for step in range(step_count):
                seed = _stable_seed(module, path_index, step)
                shock = (((seed % 2001) / 1000.0) - 1.0) * sigma
                nav *= 1.0 + drift + shock
            final_navs.append(nav)
        return {
            **metadata,
            "module": module,
            "status": "completed",
            "path_count": path_count,
            "step_count": step_count,
            "distribution": {
                "p05": round(_quantile(final_navs, 0.05), 6),
                "p50": round(_quantile(final_navs, 0.50), 6),
                "p95": round(_quantile(final_navs, 0.95), 6),
            },
            "payload": payload,
        }
    return {**metadata, "module": module, "status": "ready", "payload": payload}
