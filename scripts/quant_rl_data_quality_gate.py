#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quant_rl.reporting.experiment_recorder import MANUAL_STOCK_UNIVERSE


ESG_COLUMNS = {
    "house_score_v2",
    "house_score_v2_1",
    "esg_level",
    "esg_delta",
    "esg_delta_v2_1",
    "esg_confidence",
    "esg_staleness_days",
    "esg_effective_date",
    "esg_missing_flag",
    "sector_relative_esg",
    "e_score",
    "s_score",
    "g_score",
}
CRITICAL_MARKET_COLUMNS = {"open", "high", "low", "close", "volume"}


@dataclass(slots=True)
class GateCheck:
    name: str
    status: str
    severity: str
    message: str
    details: dict[str, Any] | None = None


def _all_symbols() -> list[str]:
    symbols: list[str] = []
    for values in MANUAL_STOCK_UNIVERSE.values():
        symbols.extend(values)
    return sorted(set(symbols))


def _dataset_csv(path: Path) -> Path:
    if path.is_dir():
        return path / "merged_market.csv"
    return path


def _namespace_root(namespace: str) -> Path:
    return ROOT / "storage" / "quant" / "rl-experiments" / namespace


def _read_frame(path: Path) -> tuple[pd.DataFrame | None, str | None]:
    try:
        frame = pd.read_csv(path)
    except Exception as exc:
        return None, str(exc)
    if "timestamp" in frame.columns:
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="coerce", utc=True)
    elif "date" in frame.columns:
        frame["timestamp"] = pd.to_datetime(frame["date"], errors="coerce", utc=True)
    return frame, None


def _check(status: bool, name: str, message_ok: str, message_fail: str, *, severity: str = "fail", details: dict[str, Any] | None = None) -> GateCheck:
    return GateCheck(
        name=name,
        status="pass" if status else "fail",
        severity="info" if status else severity,
        message=message_ok if status else message_fail,
        details=details or {},
    )


def _has_esg_column(columns: list[str]) -> bool:
    lowered = {column.lower() for column in columns}
    if lowered.intersection(ESG_COLUMNS):
        return True
    return any("esg" in column or column.startswith("house_score") for column in lowered)


def _date_key_frame(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["timestamp_key"] = pd.to_datetime(result["timestamp"], errors="coerce", utc=True).dt.strftime("%Y-%m-%d")
    return result[["symbol", "timestamp_key"]].drop_duplicates()


def run_quality_gate(
    *,
    dataset_path: str | Path,
    namespace: str = "smoke",
    dataset_kind: str = "auto",
    paired_dataset_path: str | Path | None = None,
    expected_symbols: list[str] | None = None,
    start_date: str = "2022-01-01",
    end_date: str = "2025-12-31",
    output_dir: str | Path | None = None,
    min_rows_per_symbol: int = 700,
    allow_synthetic: bool = False,
) -> dict[str, Any]:
    csv_path = _dataset_csv(Path(dataset_path))
    checks: list[GateCheck] = []
    frame, read_error = _read_frame(csv_path)
    expected_symbols = sorted(set(expected_symbols or _all_symbols()))

    checks.append(_check(
        frame is not None and read_error is None,
        "dataset_readable",
        "Dataset CSV is readable.",
        f"Dataset CSV could not be read: {read_error or csv_path}",
        details={"path": str(csv_path)},
    ))
    if frame is None:
        return _write_report(namespace, output_dir, checks, csv_path, dataset_kind)

    columns = list(frame.columns)
    checks.append(_check(len(frame) > 0, "row_count", "Dataset has rows.", "Dataset is empty.", details={"rows": int(len(frame))}))
    checks.append(_check("symbol" in frame.columns, "symbol_column", "Dataset has a symbol column.", "Dataset is missing symbol column."))
    checks.append(_check("timestamp" in frame.columns, "timestamp_column", "Dataset has a timestamp/date column.", "Dataset is missing timestamp/date column."))
    missing_market = sorted(CRITICAL_MARKET_COLUMNS - set(column.lower() for column in columns))
    checks.append(_check(
        not missing_market,
        "critical_market_columns",
        "Dataset has OHLCV critical columns.",
        f"Dataset is missing OHLCV columns: {missing_market}",
        details={"missing": missing_market},
    ))

    if "symbol" in frame.columns:
        symbols = sorted({str(item).upper() for item in frame["symbol"].dropna().unique()})
        missing_symbols = sorted(set(expected_symbols) - set(symbols))
        checks.append(_check(
            not missing_symbols,
            "expected_symbol_coverage",
            "Expected symbol coverage is acceptable for this namespace.",
            f"Missing expected symbols: {missing_symbols}",
            severity="fail" if namespace == "paper-run" else "warn",
            details={"symbols": symbols, "missing_symbols": missing_symbols},
        ))
        row_counts = frame.groupby(frame["symbol"].astype(str).str.upper()).size().to_dict()
        thin_symbols = sorted(symbol for symbol in expected_symbols if int(row_counts.get(symbol, 0)) < min_rows_per_symbol)
        checks.append(_check(
            not thin_symbols,
            "min_rows_per_symbol",
            "Per-symbol row counts are acceptable.",
            f"Symbols below min_rows_per_symbol={min_rows_per_symbol}: {thin_symbols}",
            severity="fail" if namespace == "paper-run" else "warn",
            details={"thin_symbols": thin_symbols, "row_counts": row_counts},
        ))

    if "timestamp" in frame.columns:
        valid_dates = frame["timestamp"].dropna()
        date_min = valid_dates.min() if not valid_dates.empty else None
        date_max = valid_dates.max() if not valid_dates.empty else None
        start_ts = pd.Timestamp(start_date, tz="UTC")
        end_ts = pd.Timestamp(end_date, tz="UTC")
        date_ok = date_min is not None and date_max is not None and date_min <= start_ts + pd.Timedelta(days=10) and date_max >= end_ts - pd.Timedelta(days=10)
        checks.append(_check(
            bool(date_ok),
            "date_range",
            "Date range covers the requested protocol window.",
            f"Date range is insufficient: {date_min} -> {date_max}",
            severity="fail" if namespace == "paper-run" else "warn",
            details={"date_min": str(date_min), "date_max": str(date_max), "start_date": start_date, "end_date": end_date},
        ))
        if "symbol" in frame.columns:
            duplicated = int(frame.duplicated(subset=["symbol", "timestamp"]).sum())
            checks.append(_check(duplicated == 0, "duplicate_symbol_dates", "No duplicate symbol/date rows.", f"Duplicate symbol/date rows: {duplicated}", details={"duplicates": duplicated}))

    for column in CRITICAL_MARKET_COLUMNS.intersection({column.lower() for column in columns}):
        original = next(item for item in columns if item.lower() == column)
        nan_count = int(pd.to_numeric(frame[original], errors="coerce").isna().sum())
        checks.append(_check(nan_count == 0, f"nan_{column}", f"{column} has no NaN values.", f"{column} has {nan_count} NaN values.", details={"nan_count": nan_count}))

    if {"symbol", "timestamp", "close"}.issubset(frame.columns):
        sorted_frame = frame.sort_values(["symbol", "timestamp"]).copy()
        sorted_frame["close_num"] = pd.to_numeric(sorted_frame["close"], errors="coerce")
        sorted_frame["prev_close"] = sorted_frame.groupby("symbol")["close_num"].shift(1)
        sorted_frame["close_ratio"] = sorted_frame["close_num"] / sorted_frame["prev_close"]
        jumps = sorted_frame.groupby("symbol")["close_num"].pct_change().abs()
        split_ratios = [1 / 20, 1 / 10, 1 / 5, 1 / 4, 1 / 3, 1 / 2, 2, 3, 4, 5, 10, 20]
        split_like = sorted_frame["close_ratio"].apply(
            lambda value: any(math.isfinite(float(value)) and abs(float(value) - ratio) / ratio <= 0.08 for ratio in split_ratios)
            if pd.notna(value) else False
        )
        extreme_jump = jumps > 0.5
        split_like_count = int((extreme_jump & split_like).sum())
        jump_count = int((extreme_jump & ~split_like).sum())
        checks.append(_check(
            jump_count == 0,
            "price_jump_guard",
            "No extreme close-to-close jumps detected.",
            f"Extreme close-to-close jumps detected: {jump_count}",
            severity="fail" if namespace == "paper-run" else "warn",
            details={"jump_count": jump_count, "split_like_jump_count": split_like_count},
        ))
        if split_like_count:
            checks.append(GateCheck(
                name="split_like_price_jumps",
                status="pass",
                severity="info",
                message=f"Detected {split_like_count} split-like price jumps and treated them as corporate-action events.",
                details={"split_like_jump_count": split_like_count},
            ))

    if "provider" in frame.columns or "market_data_source" in frame.columns:
        provider_col = "provider" if "provider" in frame.columns else "market_data_source"
        providers = sorted({str(item).lower() for item in frame[provider_col].dropna().unique()})
        has_synthetic = "synthetic" in providers
        checks.append(_check(
            not has_synthetic or allow_synthetic,
            "provider_no_synthetic",
            "Provider source is acceptable.",
            f"Synthetic provider is present in formal data: {providers}",
            severity="fail" if namespace == "paper-run" else "warn",
            details={"providers": providers},
        ))
    else:
        checks.append(_check(
            False,
            "provider_column",
            "Provider column is optional outside paper-run.",
            "Provider column is required for paper-run.",
            severity="fail" if namespace == "paper-run" else "warn",
        ))

    kind = dataset_kind.lower()
    has_esg = _has_esg_column(columns)
    if kind in {"no-esg", "no_esg"}:
        checks.append(_check(not has_esg, "no_esg_field_isolation", "No-ESG dataset has no ESG fields.", "No-ESG dataset contains ESG fields."))
    if kind in {"house-esg", "house_esg", "esg"}:
        required_esg = {"house_score_v2", "house_score_v2_1", "esg_confidence", "esg_missing_flag", "esg_delta", "esg_delta_v2_1", "sector_relative_esg"}
        missing_esg = sorted(required_esg - set(columns))
        checks.append(_check(not missing_esg, "esg_required_fields", "ESG dataset has required ESG fields.", f"ESG dataset missing fields: {missing_esg}", details={"missing": missing_esg}))
        if not missing_esg:
            missing_rows = frame[pd.to_numeric(frame["esg_missing_flag"], errors="coerce").fillna(1) >= 1]
            leakage = 0
            if not missing_rows.empty:
                score_bad = (pd.to_numeric(missing_rows["house_score_v2"], errors="coerce") - 0.5).abs() > 1e-9
                score_v2_1_bad = (pd.to_numeric(missing_rows["house_score_v2_1"], errors="coerce") - 0.5).abs() > 1e-9
                conf_bad = pd.to_numeric(missing_rows["esg_confidence"], errors="coerce").fillna(1).abs() > 1e-9
                delta_bad = pd.to_numeric(missing_rows["esg_delta"], errors="coerce").fillna(0).abs() > 1e-9
                delta_v2_1_bad = pd.to_numeric(missing_rows["esg_delta_v2_1"], errors="coerce").fillna(0).abs() > 1e-9
                rel_bad = pd.to_numeric(missing_rows["sector_relative_esg"], errors="coerce").fillna(0).abs() > 1e-9
                leakage = int((score_bad | score_v2_1_bad | conf_bad | delta_bad | delta_v2_1_bad | rel_bad).sum())
            checks.append(_check(
                leakage == 0,
                "missing_esg_neutral_guard",
                "Missing ESG rows are neutral and zero-confidence.",
                f"Missing ESG rows leaked non-neutral values: {leakage}",
                details={"leakage_rows": leakage},
            ))
            if "esg_effective_date" in frame.columns and "timestamp" in frame.columns:
                active_rows = frame[pd.to_numeric(frame["esg_missing_flag"], errors="coerce").fillna(1) < 1]
                effective = pd.to_datetime(active_rows["esg_effective_date"], errors="coerce", utc=True)
                timestamps = pd.to_datetime(active_rows["timestamp"], errors="coerce", utc=True)
                future_rows = int(((effective.notna()) & (timestamps.notna()) & (effective > timestamps)).sum())
                missing_effective = int(effective.isna().sum())
                checks.append(_check(
                    future_rows == 0 and missing_effective == 0,
                    "esg_effective_date_no_leakage",
                    "Active ESG rows only use scores effective on or before the market date.",
                    f"Active ESG rows have future/missing effective dates: future={future_rows}, missing={missing_effective}",
                    details={"future_rows": future_rows, "missing_effective_rows": missing_effective},
                ))

    if paired_dataset_path:
        paired_csv = _dataset_csv(Path(paired_dataset_path))
        paired, paired_error = _read_frame(paired_csv)
        checks.append(_check(paired is not None and paired_error is None, "paired_dataset_readable", "Paired dataset is readable.", f"Paired dataset could not be read: {paired_error or paired_csv}", details={"path": str(paired_csv)}))
        if paired is not None and {"symbol", "timestamp"}.issubset(frame.columns) and {"symbol", "timestamp"}.issubset(paired.columns):
            left = _date_key_frame(frame)
            right = _date_key_frame(paired)
            left_keys = set(map(tuple, left.to_numpy()))
            right_keys = set(map(tuple, right.to_numpy()))
            checks.append(_check(
                left_keys == right_keys,
                "paired_symbol_date_alignment",
                "Paired ESG/no-ESG datasets share the same symbol/date keys.",
                "Paired ESG/no-ESG datasets have different symbol/date keys.",
                details={"left_only": len(left_keys - right_keys), "right_only": len(right_keys - left_keys)},
            ))
            checks.append(_check(
                not _has_esg_column(list(paired.columns)),
                "paired_no_esg_field_isolation",
                "Paired no-ESG dataset has no ESG fields.",
                "Paired no-ESG dataset contains ESG fields.",
            ))

    return _write_report(namespace, output_dir, checks, csv_path, dataset_kind)


def _write_report(namespace: str, output_dir: str | Path | None, checks: list[GateCheck], csv_path: Path, dataset_kind: str) -> dict[str, Any]:
    out_dir = Path(output_dir) if output_dir else _namespace_root(namespace) / "quality"
    out_dir.mkdir(parents=True, exist_ok=True)
    failed = [check for check in checks if check.status == "fail" and check.severity == "fail"]
    warned = [check for check in checks if check.status == "fail" and check.severity == "warn"]
    status = "fail" if failed else "pass"
    payload = {
        "status": status,
        "namespace": namespace,
        "dataset_kind": dataset_kind,
        "dataset_path": str(csv_path),
        "checks": [asdict(check) for check in checks],
        "fail_count": len(failed),
        "warning_count": len(warned),
    }
    json_path = out_dir / "data_quality_report.json"
    csv_out = out_dir / "data_quality_report.csv"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    with csv_out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["name", "status", "severity", "message", "details"])
        writer.writeheader()
        for check in checks:
            writer.writerow({
                "name": check.name,
                "status": check.status,
                "severity": check.severity,
                "message": check.message,
                "details": json.dumps(check.details or {}, ensure_ascii=False, default=str),
            })
    payload["json_path"] = str(json_path)
    payload["csv_path"] = str(csv_out)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Run RL formal dataset quality gates before AutoDL training.")
    parser.add_argument("--dataset-path", required=True)
    parser.add_argument("--paired-dataset-path", default=None)
    parser.add_argument("--namespace", "--run-namespace", default="smoke", choices=["smoke", "dev", "paper-run"])
    parser.add_argument("--dataset-kind", default="auto", choices=["auto", "no-esg", "no_esg", "house-esg", "house_esg", "esg"])
    parser.add_argument("--expected-symbols", default=",".join(_all_symbols()))
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--end-date", default="2025-12-31")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--min-rows-per-symbol", type=int, default=700)
    parser.add_argument("--allow-synthetic", action="store_true")
    args = parser.parse_args()

    expected_symbols = [item.strip().upper() for item in args.expected_symbols.split(",") if item.strip()]
    report = run_quality_gate(
        dataset_path=args.dataset_path,
        paired_dataset_path=args.paired_dataset_path,
        namespace=args.namespace,
        dataset_kind=args.dataset_kind,
        expected_symbols=expected_symbols,
        start_date=args.start_date,
        end_date=args.end_date,
        output_dir=args.output_dir,
        min_rows_per_symbol=args.min_rows_per_symbol,
        allow_synthetic=args.allow_synthetic,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    return 1 if args.namespace == "paper-run" and report["status"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
