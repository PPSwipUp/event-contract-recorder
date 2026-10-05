"""Collect EVERY trade of the whole hour (not just minutes 10-20) for the markets nearest the price, for a sample of
hourly events.  Same columns as db.py, so maker.py can read it.  Read-only public endpoints.
  python backfill/fullhour.py --series KXBTC --product BTC-USD --start 2026-01-01 --end 2026-10-01 --every 4 --out data_local/full
"""
from __future__ import annotations

import argparse
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from collect import K, coinbase, event_ticker, get, markets_of


def all_trades(ticker, t0, t1):
    out = []
    for base in (f"{K}/historical/trades", f"{K}/markets/trades"):
        cur = None
        while True:
            p = {"ticker": ticker, "min_ts": t0, "max_ts": t1, "limit": 1000}
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
    ap.add_argument("--series", required=True)
    ap.add_argument("--product", required=True)
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--every", type=int, default=4, help="use every n-th hour")
    ap.add_argument("--maxm", type=int, default=10)
    ap.add_argument("--out", default="data_local/full")
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
                return []
            op = pd.Timestamp(ms[0].get("open_time") or (close - timedelta(hours=1)).isoformat())
            s = px.asof(op)
            cand = []
            for m in ms:
                lo, hi = m.get("floor_strike"), m.get("cap_strike")
                ref = hi if lo is None else lo if hi is None else (lo + hi) / 2
                if ref is not None and np.isfinite(s) and abs(ref / s - 1) <= 0.03:
                    cand.append((abs(ref / s - 1), m))
            rows = []
            for _, m in sorted(cand, key=lambda x: x[0])[:a.maxm]:
                for t in all_trades(m["ticker"], int(op.timestamp()), int(close.timestamp())):
                    rows.append({"event": ev, "close": close.isoformat(), "open": op.isoformat(), "ticker": m["ticker"],
                                 "floor": m.get("floor_strike"), "cap": m.get("cap_strike"), "result": m.get("result"),
                                 "ts": t["created_time"], "taker": t.get("taker_side"),
                                 "yes": float(t.get("yes_price_dollars") or np.nan), "no": float(t.get("no_price_dollars") or np.nan),
                                 "count": float(t.get("count_fp") or t.get("count") or 0)})
            return rows
        except Exception as err:
            print("skipped", close, repr(err)[:100], flush=True)
            return []

    hours = list(pd.date_range(start + timedelta(hours=1), end, freq="1h", tz="UTC").to_pydatetime())[::a.every]
    for m0 in sorted({h.strftime("%Y-%m") for h in hours}):
        d = os.path.join(a.out, f"db-{a.series}-{m0}")
        if os.path.exists(os.path.join(d, "trades.parquet")):
            continue
        hs = [h for h in hours if h.strftime("%Y-%m") == m0]
        with ThreadPoolExecutor(6) as ex:
            rows = [r for rs in ex.map(one, hs) for r in rs]
        os.makedirs(d, exist_ok=True)
        pd.DataFrame(rows).to_parquet(os.path.join(d, "trades.parquet"))
        print(a.series, m0, len(hs), "hours", len(rows), "trades", flush=True)


if __name__ == "__main__":
    main()
