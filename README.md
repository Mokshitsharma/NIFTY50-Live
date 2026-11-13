<!-- readme-refresh 2026-11 -->
<div align="center">

# ⏱️ NIFTY 50 Live

**Polls prices and fundamentals for all 50 NIFTY stocks every minute**

<img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python" /> <img src="https://img.shields.io/badge/yfinance-720E9E?style=for-the-badge&logo=yahoo&logoColor=white" alt="yfinance" /> <img src="https://img.shields.io/badge/pandas-150458?style=for-the-badge&logo=pandas&logoColor=white" alt="pandas" />

</div>

## ✨ Highlights

- All 50 constituents
- Updates every minute
- Writes CSV outputs

<!-- body -->
This project provides a robust Python pipeline to fetch and aggregate free data for ALL NIFTY 50 companies, producing five ready-to-use CSV sheets for a comprehensive Power BI dashboard. Data sources include `yfinance`, optional `nsepython`, and light web scraping, ensuring maximum coverage from public APIs.

## Features

- **Sheet 1: Historical Price Data**
  - Daily prices for last 5 years
  - Multi-timeframe aggregation (1d, 1w, 1m, 3m, 6m, 1y, 3y, 5y)

- **Sheet 2: Performance Data**
  - Today’s high/low, open, last price, previous close
  - 52-week high/low, volume, total traded value, circuit limits

- **Sheet 3: Fundamentals**
  - Market cap, ROE, PE & PB ratios, industry PE (if available)
  - Debt-to-equity ratio, face value, book value, dividend yield, EPS

- **Sheet 4: Financials (Best-effort)**
  - Revenue last 3 quarters, yearly revenue last 3 years
  - Net income, net worth

- **Sheet 5: Shareholding Pattern (Best-effort)**
  - Shareholding for last 5 quarters
  - Top 5 mutual funds’ holdings

## Requirements

- Python 3.x
- pandas
- numpy
- yfinance
- requests
- beautifulsoup4
- tqdm
- Optional: nsepython

Install dependencies:

```bash
pip install pandas numpy yfinance requests beautifulsoup4 tqdm
```

To optionally enable deeper NSE-based data, install `nsepython`:

```bash
pip install nsepython
```

## Usage

1. Run the complete pipeline script:

    ```bash
    python nifty50_full_pipeline.py
    ```

2. All output files will be saved in the `nifty50_data_outputs` directory:
    - `sheet1_historical.csv`
    - `sheet2_performance.csv`
    - `sheet3_fundamentals.csv`
    - `sheet4_financials.csv`
    - `sheet5_shareholding.csv`

3. Load these CSV sheets into your Power BI dashboard and design the report for each tab.

## Data Sources & Notes

- Uses multiple free sources; some fields may be incomplete due to API/site restrictions.
- Financial and shareholding data employs fallback strategies and may be partial.
- Web scraping is lightweight and purposely minimal to avoid service blocks.

## Limitations

- Site/API changes, rate limits, or missing ticker mappings may produce missing/incomplete data for some companies.
- Shareholding and mutual funds info is best-effort and not guaranteed for every company.

## License

Open-source under the MIT License.

---

<div align="center"><sub>Built by <a href="https://github.com/Mokshitsharma">Mokshit Sharma</a> · <a href="https://mokshitsharma27.vercel.app/">Portfolio</a> · <a href="https://www.linkedin.com/in/mokshit-sharma-75b5ab305">LinkedIn</a></sub></div>
