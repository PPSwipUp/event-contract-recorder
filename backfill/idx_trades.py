"""Every Kalshi trade in S&P 500 / Nasdaq-100 daily-range markets near the money, Oct 2024 - Sep 2026.
Markets: the 4pm-close events, brackets with volume within 2% of the previous day's close.  Saved per month (resumable).
  python backfill/idx_trades.py --series KXINX
"""
from __future__ import annotations

import argparse
import os
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

from collect import K, get

OUT = "data_local/idx"


def trades(ticker):
    out, cur = [], None
    for base in (f"{K}/historical/trades", f"{K}/markets/trades"):
        while True:
            p = {"ticker": ticker, "limit": 1000}
            if cur:
                p["cursor"] = cur
            d = get(base, **p) or {}
            out += d.get("trades", [])
            cur = d.get("cursor")
            if not cur or not d.get("trades"):
                break
        if out:
            return out
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", default="KXINX")
    a = ap.parse_args()
    M = pd.read_parquet(f"{OUT}/{a.series}_markets.parquet")
    M["close"] = pd.to_datetime(M.close_time, format="ISO8601", utc=True)
    M = M[M.close.dt.hour == 20 if False else M.close.dt.strftime("%H:%M").isin(["20:00", "21:00"])]   # 4pm ET close (EDT / EST)
    M = M[M.close >= "2024-10-01"].copy()
    settle = M.groupby("event_ticker").agg(close=("close", "first"), value=("expiration_value", "first"))
    settle["value"] = pd.to_numeric(settle.value, errors="coerce")
    settle = settle.sort_values("close")
    settle["prev"] = settle.value.shift(1)
    M = M.merge(settle[["prev"]], left_on="event_ticker", right_index=True)
    lo, hi = pd.to_numeric(M.floor_strike), pd.to_numeric(M.cap_strike)
    ref = np.where(lo.isna(), hi, np.where(hi.isna(), lo, (lo + hi) / 2))
    M = M[(pd.to_numeric(M.volume_fp) > 0) & (np.abs(ref / M.prev - 1) <= 0.02)]
    for month, g in M.groupby(M.close.dt.strftime("%Y-%m")):
        path = f"{OUT}/{a.series}_trades_{month}.parquet"
        if os.path.exists(path):
            continue
        with ThreadPoolExecutor(6) as ex:
            res = list(ex.map(trades, g.ticker))
        rows = [{"ticker": tk, "ts": t["created_time"], "taker": t.get("taker_side"),
                 "yes": float(t.get("yes_price_dollars") or np.nan), "count": float(t.get("count_fp") or t.get("count") or 0)}
                for tk, ts in zip(g.ticker, res) for t in ts]
        pd.DataFrame(rows).to_parquet(path)
        print(a.series, month, len(g), "markets", len(rows), "trades", flush=True)


if __name__ == "__main__":
    main()
