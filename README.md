# Trend Momentum 4 — Streamlit Trading Research App

A deployable Streamlit app for a rules-based Indian equity swing strategy.

## Features
- Nifty 50 momentum scanner
- Weekly + daily trend filters
- RSI and relative-volume confirmation
- 10-day breakout signal
- Risk-based position sizing
- Single-stock historical backtest
- Trade planner
- CSV exports

## Important
This is a research/decision-support tool, not a guarantee of returns or investment advice. The default market-data source is Yahoo Finance via `yfinance`, which is not an exchange-grade execution feed.

## Deploy on Streamlit Community Cloud
1. Create a GitHub repository.
2. Upload `app.py` and `requirements.txt`.
3. Go to Streamlit Community Cloud and create an app using `app.py`.
4. Select Python 3.12 if offered.
5. Deploy.

No API key is required for the default Yahoo Finance data source.

## Suggested repository structure
trend-momentum-4/
  app.py
  requirements.txt
  README.md
