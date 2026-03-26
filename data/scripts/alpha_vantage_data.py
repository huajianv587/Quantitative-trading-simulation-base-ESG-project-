import os
import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("ALPHA_AVANTAGE_KEY")
BASE_URL = "https://www.alphavantage.co/query"


def fetch_esg(ticker: str) -> dict | None:
    params = {
        "function": "ESG_SCORE",
        "symbol": ticker,
        "apikey": API_KEY,
    }
    resp = requests.get(BASE_URL, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    if "ESG Scores" not in data:
        print(f"{ticker}: No ESG data returned. Response: {data}")
        return None

    return data["ESG Scores"]


def get_esg_data():
    print("Enter ticker symbol(s) to search for ESG data (e.g. AAPL, TSLA, MSFT):")
    name_in = input().strip()
    tickers = [t.strip().upper() for t in name_in.split(",") if t.strip()]

    if not tickers:
        print("No tickers provided.")
        return None

    results = []
    for t in tickers:
        try:
            esg = fetch_esg(t)
            if esg:
                esg["ticker"] = t
                results.append(esg)
                print(f"{t}: ESG data retrieved successfully.")
        except requests.HTTPError as e:
            print(f"{t} HTTP error: {e}")
        except Exception as e:
            print(f"{t} failed: {e}")

    if not results:
        print("No ESG data found for any of the provided tickers.")
        return None

    df = pd.DataFrame(results)
    print("\n--- ESG Scores (Alpha Vantage) ---")
    print(df.to_string(index=False))
    return df


if __name__ == "__main__":
    df = get_esg_data()
