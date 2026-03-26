"""
parse_esg.py
------------
Fetch ESG data from yfinance and/or Alpha Vantage, then
serialize the results to JSON files under data/processed/.
"""

import sys
import json
import math
from pathlib import Path
from datetime import datetime

import yfinance as yf
import pandas as pd

# Allow imports from data/raw/
RAW_DIR = Path(__file__).resolve().parent.parent / "raw"
sys.path.insert(0, str(RAW_DIR))

from alpha_vantage_data import fetch_esg as av_fetch_esg  # noqa: E402

PROCESSED_DIR = Path(__file__).resolve().parent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clean_value(v):
    """Convert non-JSON-serialisable types (NaN, Inf, numpy scalars) to safe types."""
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    # numpy scalar → Python native
    if hasattr(v, "item"):
        return v.item()
    return v


def _df_to_records(df: pd.DataFrame) -> list[dict]:
    """Convert a DataFrame to a list of clean dicts."""
    return [
        {k: _clean_value(v) for k, v in row.items()}
        for row in df.to_dict(orient="records")
    ]


def _save_json(data: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Saved → {path}")


# ---------------------------------------------------------------------------
# Source: yfinance
# ---------------------------------------------------------------------------

ESG_COLS_YF = ["ticker", "totalEsg", "environmentScore", "socialScore", "governanceScore"]


def fetch_yfinance(tickers: list[str]) -> list[dict]:
    records = []
    for t in tickers:
        try:
            esg = yf.Ticker(t).sustainability
            if esg is None:
                print(f"[yfinance] {t}: no ESG data.")
                continue
            row = esg.T.copy()
            row["ticker"] = t
            available = [c for c in ESG_COLS_YF if c in row.columns]
            records.extend(_df_to_records(row[available]))
            print(f"[yfinance] {t}: OK")
        except Exception as e:
            print(f"[yfinance] {t} failed: {e}")
    return records


# ---------------------------------------------------------------------------
# Source: Alpha Vantage
# ---------------------------------------------------------------------------

def fetch_alpha_vantage(tickers: list[str]) -> list[dict]:
    records = []
    for t in tickers:
        try:
            esg = av_fetch_esg(t)
            if esg is None:
                continue
            esg["ticker"] = t
            records.append({k: _clean_value(v) for k, v in esg.items()})
            print(f"[alpha_vantage] {t}: OK")
        except Exception as e:
            print(f"[alpha_vantage] {t} failed: {e}")
    return records


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_and_save(tickers: list[str]) -> dict:
    """
    Fetch ESG data from both sources and save to JSON.
    Returns a dict with both result lists.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    yf_records = fetch_yfinance(tickers)
    av_records = fetch_alpha_vantage(tickers)

    if yf_records:
        _save_json(yf_records, PROCESSED_DIR / f"esg_yfinance_{timestamp}.json")

    if av_records:
        _save_json(av_records, PROCESSED_DIR / f"esg_alphavantage_{timestamp}.json")

    # Combined output
    combined = {
        "generated_at": timestamp,
        "tickers": tickers,
        "yfinance": yf_records,
        "alpha_vantage": av_records,
    }
    _save_json([combined], PROCESSED_DIR / f"esg_combined_{timestamp}.json")

    return combined


if __name__ == "__main__":
    print("Enter ticker symbol(s) (e.g. AAPL, TSLA, MSFT):")
    name_in = input().strip()
    tickers = [t.strip().upper() for t in name_in.split(",") if t.strip()]

    if not tickers:
        print("No tickers provided.")
    else:
        result = parse_and_save(tickers)
        print("\n--- Combined JSON preview ---")
        print(json.dumps(result, ensure_ascii=False, indent=2))
