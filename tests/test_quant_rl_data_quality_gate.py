from __future__ import annotations

from pathlib import Path

import pandas as pd

from scripts.quant_rl_data_quality_gate import run_quality_gate


def _base_market_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": ["2022-01-03", "2022-01-04", "2025-12-30"],
            "symbol": ["AAPL", "AAPL", "AAPL"],
            "open": [100.0, 101.0, 102.0],
            "high": [101.0, 102.0, 103.0],
            "low": [99.0, 100.0, 101.0],
            "close": [100.5, 101.5, 102.5],
            "volume": [1000, 1100, 1200],
            "provider": ["alpaca", "alpaca", "alpaca"],
        }
    )


def test_data_quality_gate_passes_neutral_missing_esg(tmp_path: Path):
    frame = _base_market_frame()
    frame["house_score_v2"] = [0.5, 0.5, 0.7]
    frame["house_score_v2_1"] = [0.5, 0.5, 0.72]
    frame["esg_confidence"] = [0.0, 0.0, 0.8]
    frame["esg_delta"] = [0.0, 0.0, 0.04]
    frame["esg_delta_v2_1"] = [0.0, 0.0, 0.05]
    frame["sector_relative_esg"] = [0.0, 0.0, 0.2]
    frame["esg_missing_flag"] = [1, 1, 0]
    frame["esg_effective_date"] = ["", "", "2025-04-01"]
    path = tmp_path / "house_esg.csv"
    frame.to_csv(path, index=False)

    report = run_quality_gate(
        dataset_path=path,
        namespace="smoke",
        dataset_kind="house-esg",
        expected_symbols=["AAPL"],
        min_rows_per_symbol=2,
        output_dir=tmp_path / "quality",
    )

    assert report["status"] == "pass"


def test_data_quality_gate_fails_no_esg_with_esg_fields(tmp_path: Path):
    frame = _base_market_frame()
    frame["house_score_v2"] = 0.5
    path = tmp_path / "no_esg.csv"
    frame.to_csv(path, index=False)

    report = run_quality_gate(
        dataset_path=path,
        namespace="smoke",
        dataset_kind="no-esg",
        expected_symbols=["AAPL"],
        min_rows_per_symbol=2,
        output_dir=tmp_path / "quality",
    )

    assert report["status"] == "fail"
    assert any(check["name"] == "no_esg_field_isolation" for check in report["checks"])


def test_data_quality_gate_fails_missing_esg_leakage(tmp_path: Path):
    frame = _base_market_frame()
    frame["house_score_v2"] = [0.55, 0.5, 0.7]
    frame["house_score_v2_1"] = [0.5, 0.5, 0.72]
    frame["esg_confidence"] = [0.0, 0.0, 0.8]
    frame["esg_delta"] = [0.0, 0.0, 0.04]
    frame["esg_delta_v2_1"] = [0.0, 0.0, 0.05]
    frame["sector_relative_esg"] = [0.0, 0.0, 0.2]
    frame["esg_missing_flag"] = [1, 1, 0]
    path = tmp_path / "house_esg_bad.csv"
    frame.to_csv(path, index=False)

    report = run_quality_gate(
        dataset_path=path,
        namespace="smoke",
        dataset_kind="house-esg",
        expected_symbols=["AAPL"],
        min_rows_per_symbol=2,
        output_dir=tmp_path / "quality",
    )

    assert report["status"] == "fail"
    assert any(check["name"] == "missing_esg_neutral_guard" and check["status"] == "fail" for check in report["checks"])


def test_data_quality_gate_fails_future_esg_effective_date(tmp_path: Path):
    frame = _base_market_frame()
    frame["house_score_v2"] = [0.5, 0.5, 0.7]
    frame["house_score_v2_1"] = [0.5, 0.5, 0.72]
    frame["esg_confidence"] = [0.0, 0.0, 0.8]
    frame["esg_delta"] = [0.0, 0.0, 0.04]
    frame["esg_delta_v2_1"] = [0.0, 0.0, 0.05]
    frame["sector_relative_esg"] = [0.0, 0.0, 0.2]
    frame["esg_missing_flag"] = [1, 1, 0]
    frame["esg_effective_date"] = ["", "", "2026-01-05"]
    path = tmp_path / "house_esg_future.csv"
    frame.to_csv(path, index=False)

    report = run_quality_gate(
        dataset_path=path,
        namespace="smoke",
        dataset_kind="house-esg",
        expected_symbols=["AAPL"],
        min_rows_per_symbol=2,
        output_dir=tmp_path / "quality",
    )

    assert report["status"] == "fail"
    assert any(check["name"] == "esg_effective_date_no_leakage" and check["status"] == "fail" for check in report["checks"])


def test_data_quality_gate_treats_split_like_jump_as_info(tmp_path: Path):
    frame = pd.DataFrame(
        {
            "timestamp": ["2022-06-03", "2022-06-06", "2025-12-30"],
            "symbol": ["AMZN", "AMZN", "AMZN"],
            "open": [2450.0, 122.0, 130.0],
            "high": [2500.0, 130.0, 131.0],
            "low": [2400.0, 120.0, 129.0],
            "close": [2446.0, 124.0, 130.0],
            "volume": [1000, 20000, 30000],
            "provider": ["alpaca", "alpaca", "alpaca"],
        }
    )
    path = tmp_path / "split_like.csv"
    frame.to_csv(path, index=False)

    report = run_quality_gate(
        dataset_path=path,
        namespace="paper-run",
        dataset_kind="no-esg",
        expected_symbols=["AMZN"],
        start_date="2022-06-01",
        end_date="2025-12-31",
        min_rows_per_symbol=2,
        output_dir=tmp_path / "quality",
    )

    assert report["status"] == "pass"
    assert any(check["name"] == "split_like_price_jumps" for check in report["checks"])
