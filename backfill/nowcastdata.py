"""Data for nowcast-market backtests (AAA gas daily/weekly, TSA weekly, jobless claims): every settled market of a
series (strikes, result, settlement value) and every real trade over its life.  Read-only public endpoints.
  python backfill/nowcastdata.py KXAAAGASD KXAAAGASW KXTSAW KXJOBLESSCLAIMS
"""
from __future__ import annotations

import os
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import numpy as np
import pandas as pd

from collect import K, get
from fullhour import all_trades

OUT = "data_local/nowcast"


def markets(series):
    rows = []
    for base in (f"{K}/markets", f"{K}/historical/markets"):
        cur = None
        while True:
            p = {"series_ticker": series, "limit": 1000}
            if base.endswith("/markets") and "historical" not in base:
                p["status"] = "settled"
            if cur:
                p["cursor"] = cur
            d = get(base, **p) or {}
            rows += d.get("markets", [])
            cur = d.get("cursor")
            if not cur or not d.get("markets"):
                break
    M = pd.DataFrame([{"event": m["event_ticker"], "ticker": m["ticker"], "strike_type": m.get("strike_type"),
                       "floor": m.get("floor_strike"), "cap": m.get("cap_strike"), "result": m.get("result"),
                       "value": pd.to_numeric(m.get("expiration_value"), errors="coerce"),
                       "open": m.get("open_time"), "close": m.get("close_time"),
                       "volume": float(m.get("volume_fp") or m.get("volume") or 0)} for m in rows])
    return M.drop_duplicates("ticker")


def ts(s):
    return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())


def trades(M):
    def one(r):
        try:
            return [{"ticker": r.ticker, "ts": t["created_time"], "taker": t.get("taker_side"),
                     "yes": float(t.get("yes_price_dollars") or np.nan), "count": float(t.get("count_fp") or 0)}
                    for t in all_trades(r.ticker, ts(r.open), ts(r.close) + 60)]
        except Exception as e:
            print("skip", r.ticker, repr(e)[:80], flush=True)
            return []
    with ThreadPoolExecutor(6) as ex:
        res = list(ex.map(one, M[M.volume > 0].itertuples()))
    return pd.DataFrame([t for r in res for t in r])


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for s in sys.argv[1:]:
        p = f"{OUT}/{s}"
        if not os.path.exists(f"{p}_markets.parquet"):
            markets(s).to_parquet(f"{p}_markets.parquet")
        M = pd.read_parquet(f"{p}_markets.parquet")
        print(s, len(M), "markets", M.event.nunique(), "events", M.close.min(), M.close.max(), flush=True)
        if not os.path.exists(f"{p}_trades.parquet"):
            T = trades(M)
            T.to_parquet(f"{p}_trades.parquet")
            print(s, len(T), "trades", flush=True)
