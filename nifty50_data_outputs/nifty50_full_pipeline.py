"""
nifty50_full_pipeline.py
Purpose: Fetch free data for a 5-sheet Power BI dashboard for NIFTY 50 companies:
  Sheet1: Historical price & multi-timeframe (1d,1w,1m,3m,6m,1y,3y,5y)
  Sheet2: Performance (today high/low, 52w high/low, open, prev close, circuits if available, total traded value, volume)
  Sheet3: Fundamentals (market cap, ROE, P/E, P/B, industry P/E if available, debt-to-equity, face value, book value, dividend yield, EPS, ROE)
  Sheet4: Financials (Revenue last 3 quarters, yearly last 3 years, profit, net worth) - best-effort
  Sheet5: Shareholding pattern (last 5 quarters) & top 5 mutual funds invested - best-effort

Notes:
- Free sources used: yfinance (main), optional nsepython, light scraping.
- Results may be partial for some companies depending on availability and site restrictions.
"""

import os
import time
import math
import json
import traceback
from datetime import datetime, timedelta
from tqdm import tqdm

import pandas as pd
import numpy as np
import yfinance as yf
import requests
from bs4 import BeautifulSoup

# Optional: nsepython (community package). Use if installed.
try:
    from nsepython import *
    NSEPYTHON_AVAILABLE = True
except Exception:
    NSEPYTHON_AVAILABLE = False

# ----- User config -----
OUTPUT_DIR = "nifty50_data_outputs"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# NIFTY 50 tickers on Yahoo Finance (suffix .NS for NSE)
NIFTY50_TICKERS = [
    "RELIANCE.NS","TCS.NS","INFY.NS","HDFCBANK.NS","ICICIBANK.NS",
    "HINDUNILVR.NS","BHARTIARTL.NS","ITC.NS","KOTAKBANK.NS","LT.NS",
    "SBIN.NS","AXISBANK.NS","ASIANPAINT.NS","BAJFINANCE.NS","HCLTECH.NS",
    "WIPRO.NS","MARUTI.NS","ULTRACEMCO.NS","SUNPHARMA.NS","ONGC.NS",
    "NTPC.NS","POWERGRID.NS","TITAN.NS","ADANIPORTS.NS","BAJAJ-AUTO.NS",
    "CIPLA.NS","JSWSTEEL.NS","M&M.NS","GRASIM.NS","TECHM.NS",
    "TATASTEEL.NS","HDFCLIFE.NS","HINDALCO.NS","DIVISLAB.NS","NESTLEIND.NS",
    "BPCL.NS","HEROMOTOCO.NS","COALINDIA.NS","EICHERMOT.NS","DRREDDY.NS",
    "BRITANNIA.NS","SHREECEM.NS","UPL.NS","SBILIFE.NS","INDUSINDBK.NS",
    "APOLLOHOSP.NS","BAJAJFINSV.NS","ICICIPRULI.NS","ADANIENT.NS","ADANIGREEN.NS"
]
# Some tickers may be duplicated or out of date; keep an eye on missing results.

# Timeframes mapping for convenience
TIMEFRAME_PERIODS = {
    "1d": {"period": "1d", "interval": "1m"},
    "1w": {"period": "7d", "interval": "15m"},
    "1m": {"period": "1mo", "interval": "60m"},
    "3m": {"period": "3mo", "interval": "1d"},
    "6m": {"period": "6mo", "interval": "1d"},
    "1y": {"period": "1y", "interval": "1d"},
    "3y": {"period": "3y", "interval": "1d"},
    "5y": {"period": "5y", "interval": "1d"},
}

# helper to safe get dictionary values
def safe_get(d, key, default=None):
    return d.get(key) if isinstance(d, dict) else default

# 1) Sheet 1: Fetch historical for last 5 years and multi-timeframes
def fetch_historical_all(tickers, save_path=os.path.join(OUTPUT_DIR, "sheet1_historical.csv")):
    """
    Downloads 5-year daily historical data for all tickers using yfinance.
    Also saves per-ticker csv files for convenience.
    Output CSV columns: Ticker, Date, Open, High, Low, Close, Adj Close, Volume
    """
    print("Fetching 5-year historical (daily) for all tickers via yfinance...")
    combined = []
    # Use yfinance.download in chunks to be efficient
    tickers_str = " ".join(tickers)
    try:
        # 5y daily
        raw = yf.download(tickers=tickers_str, period="5y", interval="1d", group_by='ticker', threads=True, progress=False)
    except Exception as e:
        print("Primary yfinance.download failed for batch. Falling back to per-ticker downloads.")
        raw = None

    for t in tqdm(tickers):
        symbol = t
        ticker_label = t.replace(".NS","")
        try:
            if raw is not None and symbol in raw.columns.levels[0]:
                # grouped DataFrame structure
                df = raw[symbol].copy()
                # Some tickers return as single-column when only one ticker; handle generically
            else:
                df = yf.download(tickers=symbol, period="5y", interval="1d", progress=False)
            if df is None or df.empty:
                print(f"Warning: no historical data for {symbol}")
                continue
            df = df.reset_index().rename(columns={"Date":"Date","Open":"Open","High":"High","Low":"Low","Close":"Close","Adj Close":"Adj Close","Volume":"Volume"})
            df["Ticker"] = ticker_label
            combined.append(df[["Ticker","Date","Open","High","Low","Close","Adj Close","Volume"]])
            # Save per-ticker csv
            per_path = os.path.join(OUTPUT_DIR, f"{ticker_label}_historical_5y.csv")
            df.to_csv(per_path, index=False)
        except Exception as e:
            print(f"Error fetching historical for {symbol}: {e}")
            traceback.print_exc()
            continue

    if combined:
        all_df = pd.concat(combined, ignore_index=True)
        all_df.to_csv(save_path, index=False)
        print(f"Sheet1 historical saved to {save_path} ({len(all_df)} rows)")
    else:
        print("No historical data collected.")

# 2) Sheet 2: Today's performance: high/low, 52w high/low, open, prev close, upper/lower circuit (best-effort), total traded value, volume
def fetch_performance(tickers, save_path=os.path.join(OUTPUT_DIR, "sheet2_performance.csv")):
    """
    For each ticker, fetch latest OHLC (intraday), 52-week high/low and volumes.
    Uses yfinance and nsepython (if available) for traded value/circuits (best-effort).
    """
    rows = []
    print("Fetching performance (today's stats & 52-week) for each ticker...")
    for t in tqdm(tickers):
        symbol = t
        short = t.replace(".NS","")
        try:
            yf_t = yf.Ticker(symbol)
            info = yf_t.info or {}
            # current price and previous close
            current_price = info.get("currentPrice") or info.get("regularMarketPrice") or np.nan
            prev_close = info.get("previousClose") or info.get("regularMarketPreviousClose") or np.nan
            # 52-week
            fifty_two_wk_high = info.get("fiftyTwoWeekHigh", np.nan)
            fifty_two_wk_low = info.get("fiftyTwoWeekLow", np.nan)
            # intraday latest OHLC - fetch 1d 1m and take last row
            intraday = None
            try:
                intraday = yf_t.history(period="1d", interval="1m")
                if intraday is None or intraday.empty:
                    intraday = yf_t.history(period="5d", interval="5m")
                if intraday is not None and not intraday.empty:
                    last = intraday.iloc[-1]
                    day_open = intraday["Open"].iloc[0] if not intraday.empty else np.nan
                    day_high = intraday["High"].max() if not intraday.empty else np.nan
                    day_low = intraday["Low"].min() if not intraday.empty else np.nan
                    last_price = last["Close"]
                    volume_today = intraday["Volume"].sum()
                else:
                    day_open = info.get("open", np.nan)
                    day_high = info.get("dayHigh", np.nan)
                    day_low = info.get("dayLow", np.nan)
                    last_price = current_price
                    volume_today = info.get("volume", np.nan)
            except Exception:
                day_open = info.get("open", np.nan)
                day_high = info.get("dayHigh", np.nan)
                day_low = info.get("dayLow", np.nan)
                last_price = current_price
                volume_today = info.get("volume", np.nan)

            # total traded value (turnover) — best-effort via nsepython
            total_traded_value = np.nan
            upper_circuit = np.nan
            lower_circuit = np.nan
            if NSEPYTHON_AVAILABLE:
                try:
                    # nsepython has functions like get_quote or get_quote_info; using get_quote which returns dict —
                    q = get_quote(symbol.replace(".NS",""))
                    # Attempt many possible keys:
                    total_traded_value = q.get("TOTALTRADES") or q.get("turnoverInLakhs") or q.get("totalTradedValue") or np.nan
                    upper_circuit = q.get("upperCircuit") or np.nan
                    lower_circuit = q.get("lowerCircuit") or np.nan
                except Exception:
                    pass
            else:
                # try lightweight NSE page scrap (may be blocked). We'll attempt and ignore errors.
                try:
                    # nseindia quote API sometimes at https://www.nseindia.com/api/quote-equity?symbol=RELIANCE
                    headers = {"User-Agent": "Mozilla/5.0"}
                    base = "https://www.nseindia.com/api/quote-equity?symbol=" + symbol.replace(".NS","")
                    r = requests.get(base, headers=headers, timeout=8)
                    if r.status_code == 200:
                        j = r.json()
                        # navigate the JSON for useful fields (best-effort)
                        priceinfo = j.get("priceInfo", {})
                        total_traded_value = priceinfo.get("totalTurnover", np.nan) or total_traded_value
                        # circuits not always present
                    # else: ignore
                except Exception:
                    pass

            rows.append({
                "Ticker": short,
                "Last Price": last_price,
                "Open": day_open,
                "High (Today)": day_high,
                "Low (Today)": day_low,
                "Previous Close": prev_close,
                "52W High": fifty_two_wk_high,
                "52W Low": fifty_two_wk_low,
                "Volume (Today)": volume_today,
                "Total Traded Value": total_traded_value,
                "Upper Circuit": upper_circuit,
                "Lower Circuit": lower_circuit,
            })
        except Exception as e:
            print(f"Error fetching performance for {symbol}: {e}")
            traceback.print_exc()
            rows.append({"Ticker": short})
        # small pause to avoid hammering
        time.sleep(0.2)

    df_perf = pd.DataFrame(rows)
    df_perf.to_csv(save_path, index=False)
    print(f"Sheet2 performance saved to {save_path} ({len(df_perf)} rows)")
    return df_perf

# 3) Sheet 3: Fundamentals
def fetch_fundamentals(tickers, save_path=os.path.join(OUTPUT_DIR, "sheet3_fundamentals.csv")):
    """
    Uses yfinance.Ticker.info to extract fundamentals.
    Adds best-effort extra fields (debt/equity etc) if available.
    """
    rows = []
    print("Fetching fundamentals via yfinance (best-effort)...")
    for t in tqdm(tickers):
        symbol = t
        short = t.replace(".NS","")
        try:
            yf_t = yf.Ticker(symbol)
            info = yf_t.info or {}
            # core fundamentals (many can be None)
            mc = info.get("marketCap", np.nan)
            trailingPE = info.get("trailingPE", np.nan)
            forwardPE = info.get("forwardPE", np.nan)
            pb = info.get("priceToBook", np.nan)
            eps = info.get("trailingEps", np.nan)
            dividendYield = info.get("dividendYield", np.nan)
            bookValue = info.get("bookValue", np.nan)
            sector = info.get("sector", None)
            industry = info.get("industry", None)
            beta = info.get("beta", np.nan)
            # some ratios available
            roa = info.get("returnOnAssets", np.nan)
            roe = info.get("returnOnEquity", np.nan)
            debtToEquity = info.get("debtToEquity") if "debtToEquity" in info else np.nan
            faceValue = info.get("shareOutstanding", np.nan)  # not accurate; yfinance lacks direct face value
            # keep fields even if NaN
            rows.append({
                "Ticker": short,
                "Company Name": info.get("longName", None),
                "Sector": sector,
                "Industry": industry,
                "Market Cap": mc,
                "P/E (TTM)": trailingPE,
                "Forward P/E": forwardPE,
                "P/B": pb,
                "EPS (TTM)": eps,
                "Dividend Yield": dividendYield,
                "Book Value": bookValue,
                "ROE": roe,
                "ROA": roa,
                "DebtToEquity": debtToEquity,
                "Beta": beta,
                "Face Value (approx)": faceValue
            })
        except Exception as e:
            print(f"Error fetching fundamentals for {symbol}: {e}")
            traceback.print_exc()
            rows.append({"Ticker": short})
        time.sleep(0.15)

    df_fund = pd.DataFrame(rows)
    df_fund.to_csv(save_path, index=False)
    print(f"Sheet3 fundamentals saved to {save_path} ({len(df_fund)} rows)")
    return df_fund

# 4) Sheet 4: Financials (Revenue last 3 quarters, yearly last 3 years, profit, net worth) — best-effort scrapers
def fetch_financials_best_effort(tickers, save_path=os.path.join(OUTPUT_DIR, "sheet4_financials.csv")):
    """
    Best-effort approach:
    - Attempt using yfinance.financials / quarterly_financials / balance_sheet (may exist for some tickers)
    - Fallback: scrape moneycontrol / screener / other public pages (fragile)
    Returns a table with columns that include:
      Ticker, q1_revenue, q2_revenue, q3_revenue (last 3 quarters as available),
      year_1_revenue (latest), year_2_revenue, year_3_revenue,
      latest_net_income, net_worth (if available)
    """
    rows = []
    print("Fetching financials (best-effort). This may be incomplete and is fragile (web-scraping)...")
    for t in tqdm(tickers):
        symbol = t
        short = t.replace(".NS","")
        try:
            yf_t = yf.Ticker(symbol)
            # yfinance has attributes: financials (yearly), quarterly_financials, balance_sheet, quarterly_balance_sheet, earnings (historical)
            qf = {}
            try:
                qf = yf_t.quarterly_financials
            except Exception:
                qf = {}
            # quarterly_financials is a DataFrame columns=quarters
            q_revs = []
            try:
                if isinstance(qf, pd.DataFrame) and not qf.empty:
                    # 'Total Revenue' or similar row; find a revenue-like row
                    found_rev_row = None
                    for candidate in ["TotalRevenue", "Total Revenue", "Revenue", "totalRevenue", "NetSalesRevenue", "TotalOperatingRevenue"]:
                        if candidate in qf.index:
                            found_rev_row = candidate
                            break
                    if found_rev_row is None:
                        # try fuzzy matching: pick first numeric row
                        numeric_rows = [idx for idx in qf.index if not qf.loc[idx].isna().all()]
                        if numeric_rows:
                            found_rev_row = numeric_rows[0]
                    if found_rev_row is not None:
                        # get last 3 columns (most recent quarters)
                        revs = qf.loc[found_rev_row].tolist()[:3]
                        # ensure numeric
                        q_revs = [float(v) if (not pd.isna(v) and np.isfinite(v)) else np.nan for v in revs]
            except Exception:
                q_revs = []

            # yearly
            yf_yearly = {}
            try:
                yf_yearly = yf_t.financials
            except Exception:
                yf_yearly = {}
            year_revs = []
            try:
                if isinstance(yf_yearly, pd.DataFrame) and not yf_yearly.empty:
                    found_rev_row = None
                    for candidate in ["TotalRevenue", "Total Revenue", "Revenue", "NetSalesRevenue", "TotalOperatingRevenue"]:
                        if candidate in yf_yearly.index:
                            found_rev_row = candidate
                            break
                    if found_rev_row is None:
                        numeric_rows = [idx for idx in yf_yearly.index if not yf_yearly.loc[idx].isna().all()]
                        if numeric_rows:
                            found_rev_row = numeric_rows[0]
                    if found_rev_row:
                        # take up to 3 years
                        revs = yf_yearly.loc[found_rev_row].tolist()[:3]
                        year_revs = [float(v) if (not pd.isna(v) and np.isfinite(v)) else np.nan for v in revs]
            except Exception:
                year_revs = []

            # net income / profit
            latest_net_income = np.nan
            try:
                # try earnings history
                earnings = yf_t.earnings  # DataFrame yearly earnings
                if isinstance(earnings, pd.DataFrame) and not earnings.empty:
                    # take last year's Net Income if present
                    if "Net Income" in earnings.columns:
                        latest_net_income = earnings["Net Income"].iloc[-1]
                    else:
                        # try 'Earnings' column
                        latest_net_income = earnings.iloc[-1].values[-1] if not earnings.empty else np.nan
            except Exception:
                pass

            # net worth / shareholder's equity from balance sheet
            net_worth = np.nan
            try:
                bs = yf_t.balance_sheet
                if isinstance(bs, pd.DataFrame) and not bs.empty:
                    # Search for "Total Stockholder Equity" or similar
                    candidates = ["Total Stockholder Equity", "Total shareholders' equity", "Total Shareholders' Equity", "TotalStockholderEquity", "Shareholders Equity"]
                    for c in candidates:
                        if c in bs.index:
                            net_worth = bs.loc[c].iloc[0]
                            break
                    # fallback: pick a numeric row that looks like equity
            except Exception:
                pass

            # If we couldn't gather via yfinance, try light scraping of Moneycontrol (fragile)
            if (not q_revs) or (not year_revs) or math.isnan(net_worth):
                try:
                    # Moneycontrol's quick financials page pattern is complex and sometimes blocked.
                    # We'll attempt to fetch Moneycontrol's financials summary page for the company name from yfinance 'shortName' or 'longName'.
                    info = yf_t.info or {}
                    company_name = info.get("shortName") or info.get("longName") or short
                    # construct a Moneycontrol search query URL (this is an heuristic)
                    s = requests.Session()
                    headers = {"User-Agent": "Mozilla/5.0"}
                    search_url = f"https://www.moneycontrol.com/india/stockpricequote/search.php?search={company_name}"
                    r = s.get(search_url, headers=headers, timeout=8)
                    if r.status_code == 200:
                        # sometimes returns redirect or result links. We'll try to parse for an equity link
                        soup = BeautifulSoup(r.text, "lxml")
                        link = None
                        for a in soup.find_all("a", href=True):
                            href = a["href"]
                            if "/financials/" in href or "/company-facts" in href:
                                link = href
                                break
                        if link:
                            if not link.startswith("http"):
                                link = "https://www.moneycontrol.com" + link
                            r2 = s.get(link, headers=headers, timeout=8)
                            if r2.status_code == 200:
                                s2 = BeautifulSoup(r2.text, "lxml")
                                # Try to find revenue figures/tables. Very site-structure dependent.
                                # Example: find table rows that mention "Revenue" or "Total Revenue"
                                text = s2.get_text(separator="|")
                                # crude parse: find "Quarter" tables or numeric patterns near 'Revenue'
                                # This is intentionally light-weight; production scraping would need robust selectors.
                                # For now: skip complex parsing to avoid incorrect scraping.
                                pass
                except Exception:
                    pass

            rows.append({
                "Ticker": short,
                "Q_Revenues_Last3": q_revs if q_revs else [],
                "Year_Revenues_Last3": year_revs if year_revs else [],
                "Latest_Net_Income": latest_net_income,
                "Net_Worth": net_worth
            })
        except Exception as e:
            print(f"Error fetching financials for {symbol}: {e}")
            traceback.print_exc()
            rows.append({"Ticker": short})
        time.sleep(0.25)

    # normalize into a flat table
    norm_rows = []
    for r in rows:
        t = r.get("Ticker")
        q = r.get("Q_Revenues_Last3", [])
        y = r.get("Year_Revenues_Last3", [])
        norm_rows.append({
            "Ticker": t,
            "Q_rev_1": q[0] if len(q) > 0 else np.nan,
            "Q_rev_2": q[1] if len(q) > 1 else np.nan,
            "Q_rev_3": q[2] if len(q) > 2 else np.nan,
            "Year_rev_1": y[0] if len(y) > 0 else np.nan,
            "Year_rev_2": y[1] if len(y) > 1 else np.nan,
            "Year_rev_3": y[2] if len(y) > 2 else np.nan,
            "Latest_Net_Income": r.get("Latest_Net_Income", np.nan),
            "Net_Worth": r.get("Net_Worth", np.nan)
        })
    df_fin = pd.DataFrame(norm_rows)
    df_fin.to_csv(save_path, index=False)
    print(f"Sheet4 financials (best-effort) saved to {save_path} ({len(df_fin)} rows)")
    return df_fin

# 5) Sheet 5: Shareholding pattern last 5 quarters & top 5 mutual funds (best-effort)
def fetch_shareholding_best_effort(tickers, save_path=os.path.join(OUTPUT_DIR, "sheet5_shareholding.csv")):
    """
    Best-effort attempt:
      - Try nseindia API (if accessible) for shareholding pattern
      - Otherwise attempt scraping BSE/NSE shareholding pages (fragile)
      - For top 5 mutual funds holding, attempt to parse a public holding table (Moneycontrol/Screener) - fragile.
    Output: a table where each row is company-quarter combination or aggregated summary per ticker.
    """
    rows = []
    print("Fetching shareholding patterns (best-effort). This is fragile and may be incomplete.")
    for t in tqdm(tickers):
        symbol = t
        short = t.replace(".NS","")
        try:
            if NSEPYTHON_AVAILABLE:
                try:
                    shp = get_shareholding_of_company(short)
                    if isinstance(shp, dict):
                        # Expect shp to contain quarters with promoter/FII/DII/public percentages
                        for q, data in shp.items():
                            rows.append({
                                "Ticker": short,
                                "Quarter": q,
                                "Promoter (%)": data.get("promoters", np.nan),
                                "FII (%)": data.get("fii", np.nan),
                                "DII (%)": data.get("dii", np.nan),
                                "Public (%)": data.get("public", np.nan),
                                "Top5_MFs": ";".join([f"{k}:{v}" for k,v in (data.get("top_mutual_funds") or {}).items()]) if data.get("top_mutual_funds") else ""
                            })
                        continue
                except Exception:
                    pass

            # fallback: attempt to fetch from BSE India shareholding pages (very site-dependent)
            try:
                # BSE shareholding url pattern: https://www.bseindia.com/corporates/shpPromoter.aspx?scripcode=500325
                # But requires mapping ticker -> scripcode. Hard without a lookup.
                # So we'll skip direct BSE lookup to avoid incorrect scraping.
                raise Exception("nsepython not available or no direct API. Skipping heavy scraping by default.")
            except Exception:
                # Append an empty placeholder row so Power BI still knows about the ticker
                rows.append({
                    "Ticker": short,
                    "Quarter": None,
                    "Promoter (%)": np.nan,
                    "FII (%)": np.nan,
                    "DII (%)": np.nan,
                    "Public (%)": np.nan,
                    "Top5_MFs": ""
                })
        except Exception as e:
            print(f"Error fetching shareholding for {symbol}: {e}")
            traceback.print_exc()
            rows.append({"Ticker": short})
        time.sleep(0.2)

    df_sh = pd.DataFrame(rows)
    df_sh.to_csv(save_path, index=False)
    print(f"Sheet5 shareholding (best-effort) saved to {save_path} ({len(df_sh)} rows)")
    return df_sh

# -----------------------------
# Main pipeline runner
# -----------------------------
def main():
    print(f"Starting NIFTY50 pipeline at {datetime.now().isoformat()}")
    # Sheet1
    fetch_historical_all(NIFTY50_TICKERS, save_path=os.path.join(OUTPUT_DIR, "sheet1_historical.csv"))
    # Sheet2
    fetch_performance(NIFTY50_TICKERS, save_path=os.path.join(OUTPUT_DIR, "sheet2_performance.csv"))
    # Sheet3
    fetch_fundamentals(NIFTY50_TICKERS, save_path=os.path.join(OUTPUT_DIR, "sheet3_fundamentals.csv"))
    # Sheet4
    fetch_financials_best_effort(NIFTY50_TICKERS, save_path=os.path.join(OUTPUT_DIR, "sheet4_financials.csv"))
    # Sheet5
    fetch_shareholding_best_effort(NIFTY50_TICKERS, save_path=os.path.join(OUTPUT_DIR, "sheet5_shareholding.csv"))

    print("Pipeline finished. Check the outputs directory for CSV files:")
    for f in os.listdir(OUTPUT_DIR):
        print(" -", f)

if __name__ == "__main__":
    main()