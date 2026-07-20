"""Download the market data the notebook needs and cache it in data/.

Run once, then the notebook is offline and reproducible:
    python fetch_data.py  # defaults used in the published analysis
    python fetch_data.py --start 2015-01-01 --end 2021-01-01 --valuation-date 2020-01-02
"""

import argparse
import json
from pathlib import Path

import pandas as pd
import yfinance as yf

TICKERS = ["IVV", "EWJ", "EWU", "MCHI", "EWC", "EWQ", "EWG", "EWL", "INDA", "EWT"]
DATA = Path(__file__).parent / "data"


def risk_free(valuation_date):
    """1-year Treasury (FRED DGS1) on the valuation date, or the last quote before it."""
    fred = pd.read_csv(
        "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS1"
        f"&cosd=2000-01-01&coed={valuation_date}",
        index_col=0,
    )
    return float(pd.to_numeric(fred.iloc[:, 0], errors="coerce").dropna().iloc[-1]) / 100


def main():
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--start", default="2018-02-24")
    p.add_argument("--end", default="2024-02-24")
    p.add_argument("--valuation-date", default="2023-02-24")
    p.add_argument("--tickers", nargs="+", default=TICKERS)
    args = p.parse_args()

    cols = ["ACWI"] + args.tickers
    raw = yf.download(cols, start=args.start, end=args.end, auto_adjust=False, progress=False)
    prices = pd.concat({"adj_close": raw["Adj Close"][cols], "close": raw["Close"][cols]}, axis=1)
    prices = prices.dropna()

    # every fund distributes over a multi-year window, so total return must beat price return;
    # otherwise Yahoo served closes with the dividend adjustment missing -- re-run
    growth = prices.iloc[-1] / prices.iloc[0]
    assert (growth["adj_close"] > growth["close"]).all(), "dividend adjustment missing, re-run"
    assert args.start <= args.valuation_date <= args.end, "valuation date outside the sample"

    DATA.mkdir(exist_ok=True)
    prices.to_csv(DATA / "prices.csv")
    params = {
        "start": args.start,
        "end": args.end,
        "valuation_date": args.valuation_date,
        "tickers": args.tickers,
        "r_usd": risk_free(args.valuation_date),
    }
    (DATA / "params.json").write_text(json.dumps(params, indent=2) + "\n")

    print(f"{len(prices)} rows, {prices.index[0]:%Y-%m-%d} to {prices.index[-1]:%Y-%m-%d}")
    print(f"risk-free rate on {args.valuation_date}: {params['r_usd']:.2%}")
    print(f"wrote {DATA / 'prices.csv'} and {DATA / 'params.json'}")


if __name__ == "__main__":
    main()
