"""Data for the market-making simulator: for a sample of hourly BTC/ETH range events (Aug-Sep 2026, when Kalshi's
1-minute quote candles exist) -> every taker trade of the whole hour and the 1-minute best bid/ask, for the 10
brackets nearest the price at the open, plus strikes and results.  Read-only public endpoints.  Resumable per week.
  python backfill/simdata.py --series KXBTC --product BTC-USD --every 2
"""
from __future__ import annotations

import argparse
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from arb import candles
from collect import coinbase, event_ticker, markets_of
from fullhour import all_trades

OUT = "data_local/sim"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", default="KXBTC")
    ap.add_argument("--product", default="BTC-USD")
    ap.add_argument("--start", default="2026-08-01")
    ap.add_argument("--end", default="2026-10-01")
    ap.add_argument("--every", type=int, default=2)
    ap.add_argument("--maxm", type=int, default=10)
    ap.add_argument("--offset", type=int, default=0, help="1 = the other half of the hours (even UTC closes)")
    ap.add_argument("--even-weeks-only", action="store_true")
    a = ap.parse_args()
    start = datetime.fromisoformat(a.start).replace(tzinfo=timezone.utc)
    end = datetime.fromisoformat(a.end).replace(tzinfo=timezone.utc)
    spot = coinbase(a.product, start - timedelta(hours=3), end + timedelta(hours=2))
    px = pd.Series(spot.c.values, index=pd.to_datetime(spot.ts, unit="s", utc=True)).sort_index()

    def one(close):
        try:
            ev = event_ticker(a.series, close)
            ms = markets_of(a.series, ev)
            if not ms:
                return [], [], []
            op = close - timedelta(hours=1)
            s = px.asof(pd.Timestamp(op))
            cand = []
            for m in ms:
                lo, hi = m.get("floor_strike"), m.get("cap_strike")
                if lo is None or hi is None or not np.isfinite(s):
                    continue
                cand.append((abs((lo + hi) / 2 / s - 1), m))
            cand = [m for _, m in sorted(cand, key=lambda x: x[0])[:a.maxm]]
            mk = [{"event": ev, "close": close, "ticker": m["ticker"], "floor": m["floor_strike"], "cap": m["cap_strike"],
                   "result": m.get("result")} for m in cand]
            tr = []
            for m in cand:
                for t in all_trades(m["ticker"], int(op.timestamp()), int(close.timestamp())):
                    tr.append({"ticker": m["ticker"], "ts": t["created_time"], "taker": t.get("taker_side"),
                               "yes": float(t.get("yes_price_dollars") or np.nan), "count": float(t.get("count_fp") or 0)})
            Q, grid = candles(a.series, ev, int(close.timestamp()))
            qt = [{"ticker": tk, "ts": int(ts), "bid": b, "ask": k} for tk in (m["ticker"] for m in cand) if tk in Q
                  for ts, b, k in zip(grid, Q[tk].bid.values, Q[tk].ask.values)]
            return mk, tr, qt
        except Exception as err:
            print("skipped", close, repr(err)[:100], flush=True)
            return [], [], []

    hours = list(pd.date_range(start + timedelta(hours=1), end, freq="1h", tz="UTC").to_pydatetime())[a.offset::a.every]
    if a.even_weeks_only:
        hours = [h for h in hours if int(h.strftime("%V")) % 2 == 0]
    weeks = sorted({h.strftime("%G-W%V") for h in hours})
    for w in weeks:
        path = os.path.join(OUT, f"{a.series}_{w}{'e' if a.offset else ''}.parquet")
        if os.path.exists(path.replace(".parquet", "_trades.parquet")):
            continue
        hs = [h for h in hours if h.strftime("%G-W%V") == w]
        with ThreadPoolExecutor(6) as ex:
            res = list(ex.map(one, hs))
        os.makedirs(OUT, exist_ok=True)
        pd.DataFrame([r for m, _, _ in res for r in m]).to_parquet(path.replace(".parquet", "_markets.parquet"))
        pd.DataFrame([r for _, _, q in res for r in q]).to_parquet(path.replace(".parquet", "_quotes.parquet"))
        pd.DataFrame([r for _, t, _ in res for r in t]).to_parquet(path.replace(".parquet", "_trades.parquet"))
        print(a.series, w, len(hs), "hours", sum(len(t) for _, t, _ in res), "trades", sum(len(q) for _, _, q in res), "quote rows", flush=True)


if __name__ == "__main__":
    main()
