import yfinance as yf
import pandas as pd


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
            esg = yf.Ticker(t).sustainability
            if esg is not None:
                row = esg.T.copy()
                row["ticker"] = t
                results.append(row)
                print(f"{t}: ESG data retrieved successfully.")
            else:
                print(f"{t}: No ESG data available.")
        except Exception as e:
            print(f"{t} failed: {e}")

    if not results:
        print("No ESG data found for any of the provided tickers.")
        return None

    df = pd.concat(results, ignore_index=True)
    cols = [c for c in ["ticker", "totalEsg", "environmentScore", "socialScore", "governanceScore"] if c in df.columns]
    print("\n--- ESG Scores ---")
    print(df[cols].to_string(index=False))
    return df


if __name__ == "__main__":
    df = get_esg_data()
