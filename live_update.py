# pip install yfinance pandas schedule requests

import yfinance as yf
import pandas as pd
import time
import schedule
from datetime import datetime

# -------------------------
# NIFTY 50 Stock List
# -------------------------
nifty50_tickers = [
    "RELIANCE.NS","TCS.NS","INFY.NS","HDFCBANK.NS","ICICIBANK.NS",
    "HINDUNILVR.NS","BHARTIARTL.NS","ITC.NS","KOTAKBANK.NS","LT.NS",
    "SBIN.NS","AXISBANK.NS","ASIANPAINT.NS","BAJFINANCE.NS","HCLTECH.NS",
    "WIPRO.NS","MARUTI.NS","ULTRACEMCO.NS","SUNPHARMA.NS","ONGC.NS",
    "NTPC.NS","ADANIGREEN.NS","POWERGRID.NS","TITAN.NS","ADANIPORTS.NS",
    "BAJAJ-AUTO.NS","CIPLA.NS","JSWSTEEL.NS","M&M.NS","GRASIM.NS",
    "TECHM.NS","TATASTEEL.NS","HDFCLIFE.NS","HINDALCO.NS","DIVISLAB.NS",
    "NESTLEIND.NS","BPCL.NS","HEROMOTOCO.NS","COALINDIA.NS","EICHERMOT.NS",
    "DRREDDY.NS","BRITANNIA.NS","SHREECEM.NS","ADANIENT.NS","UPL.NS",
    "SBILIFE.NS","INDUSINDBK.NS","APOLLOHOSP.NS","BAJAJFINSV.NS","ICICIPRULI.NS"
]

# -------------------------
# Fetch All Data Function
# -------------------------
def fetch_nifty50_data():
    all_data = []

    for ticker in nifty50_tickers:
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            hist = stock.history(period="5y")

            latest = hist.iloc[-1]

            all_data.append({
                "Time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "Ticker": ticker.replace(".NS", ""),
                
                # --- Performance ---
                "Current Price": info.get("currentPrice"),
                "Day High": info.get("dayHigh"),
                "Day Low": info.get("dayLow"),
                "52W High": info.get("fiftyTwoWeekHigh"),
                "52W Low": info.get("fiftyTwoWeekLow"),
                "Open": info.get("open"),
                "Prev Close": info.get("previousClose"),
                "Volume": info.get("volume"),
                "Total Traded Value": info.get("regularMarketVolume") * info.get("currentPrice", 0),
                
                # --- Fundamentals ---
                "Market Cap": info.get("marketCap"),
                "P/E Ratio": info.get("trailingPE"),
                "P/B Ratio": info.get("priceToBook"),
                "EPS": info.get("trailingEps"),
                "Dividend Yield": info.get("dividendYield"),
                "Book Value": info.get("bookValue"),
                "ROE": info.get("returnOnEquity"),
                "Industry": info.get("industry"),
                "Sector": info.get("sector"),
                
                # --- Financials (limited in free API) ---
                "Revenue (TTM)": info.get("totalRevenue"),
                "Net Income (TTM)": info.get("netIncomeToCommon"),
                
                # --- Placeholders for Shareholding (requires paid API) ---
                "Promoter Holding": None,
                "FII Holding": None,
                "DII Holding": None,
                "Public Holding": None,
                "Top 5 MFs": None
            })

        except Exception as e:
            print(f"Error fetching {ticker}: {e}")

    # Save to CSV for Power BI
    df = pd.DataFrame(all_data)
    df.to_csv("nifty50_live.csv", index=False)
    print("✅ Data updated at", datetime.now())

# -------------------------
# Scheduler (Every 1 Min)
# -------------------------
schedule.every(1).minutes.do(fetch_nifty50_data)

print("🔄 Live update started... Press Ctrl+C to stop.")
while True:
    schedule.run_pending()
    time.sleep(1)
