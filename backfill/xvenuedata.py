"""Same contract on two venues: Polymarket "Bitcoin/Ethereum above $K on <date>" (Binance 1-min close at 12:00 ET)
vs Kalshi KXBTCD/KXETHD hourly "above K-0.01" for the 12:00 ET close (CF benchmark 60-s average).  For each day
and matched strike, the last hour before noon: Polymarket minute price history (CLOB prices-history, fidelity 1)
and Kalshi 1-minute yes bid/ask candles, plus results.  Read-only public endpoints.
  python backfill/xvenuedata.py --start 2026-08-01 --end 2026-10-03
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import requests

import dohfix  # noqa: F401
from arb import candles
from collect import ET, event_ticker, markets_of

OUT = "data_local/xvenue"
PM = requests.Session()
ASSETS = {"bitcoin": "KXBTCD", "ethereum": "KXETHD"}


def pm_event(asset, day):
    slug = f"{asset}-above-on-{day:%B}-{day.day}-{day.year}".lower()
    r = PM.get("https://gamma-api.polymarket.com/events", params={"slug": slug}, timeout=30).json()
    return r[0] if r else None


def pm_history(token, t0, t1):
    r = PM.get("https://clob.polymarket.com/prices-history",
               params={"market": token, "startTs": t0, "endTs": t1, "fidelity": 1}, timeout=30).json()
    return pd.Series({int(x["t"]): float(x["p"]) for x in r.get("history", [])}, dtype=float)


def one_day(asset, day):
    noon = datetime(day.year, day.month, day.day, 12, tzinfo=ET)
    c = int(noon.timestamp())
    e = pm_event(asset, day)
    if not e:
        return []
    series = ASSETS[asset]
    ev = event_ticker(series, noon)
    km = {round(float(m["floor_strike"]) + 0.01): m for m in markets_of(series, ev) if m.get("floor_strike") is not None}
    if not km:
        return []
    Q, grid = candles(series, ev, c)
    rows = []
    for m in e["markets"]:
        K = float(m["question"].split("$")[1].split(" ")[0].replace(",", ""))
        k = km.get(round(K))
        if k is None or k["ticker"] not in Q:
            continue
        yes_token = json.loads(m["clobTokenIds"])[0]
        h = pm_history(yes_token, c - 3600 - 300, c)
        pm_res = json.loads(m.get("outcomePrices") or "[]")
        q = Q[k["ticker"]]
        for ts in grid:
            prev = h[h.index <= ts]
            rows.append({"asset": asset, "day": day.isoformat(), "strike": K, "ts": int(ts),
                         "pm_p": prev.iloc[-1] if len(prev) else np.nan,
                         "pm_age": ts - prev.index[-1] if len(prev) else np.nan,
                         "k_bid": q.bid.get(ts, np.nan), "k_ask": q.ask.get(ts, np.nan),
                         "k_result": k.get("result"), "pm_result": pm_res[0] if pm_res else None})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2026-08-01")
    ap.add_argument("--end", default="2026-10-03")
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    days = pd.date_range(a.start, a.end, freq="D", inclusive="left").date
    for asset in ASSETS:
        path = f"{OUT}/{asset}.parquet"
        if os.path.exists(path):
            continue
        rows = []
        for d in days:
            try:
                r = one_day(asset, d)
            except Exception as err:
                print("skip", asset, d, repr(err)[:100], flush=True)
                r = []
            rows += r
            print(asset, d, len(r), flush=True)
        pd.DataFrame(rows).to_parquet(path)


if __name__ == "__main__":
    main()
