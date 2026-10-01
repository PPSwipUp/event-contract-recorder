"""Riskless arbitrage inside Kalshi: hourly range brackets (KXBTC/KXETH) vs hourly above/below (KXBTCD/KXETHD).
Both settle on the same number (60-second average of CF Benchmarks' index before the hour), and the strikes line up:
range [L, L+99.99] pays exactly what "above L-0.01" minus "above L+99.99" pays.

Two locked-in trades per bracket and minute (all legs bought as a taker at the ask, Kalshi fees on each leg):
  A  YES range + YES above(U) + NO above(L-)    always pays $1   -> profit if total cost < $1
  B  NO range  + NO above(U)  + YES above(L-)   always pays $2   -> profit if total cost < $2
Plus whole-event checks: buy YES on every range bracket (pays $1), buy NO on every bracket (pays N-1).

Quotes: Kalshi's 1-minute candlesticks (close bid/ask), forward-filled; they exist from ~Aug 2026.  An ask of $1 or a
bid of $0 counts as no order.  Depth isn't in the candles, so this finds how often and how big the gaps were;
the live scanner (live/arbscan.py) checks the order books.
  python backfill/arb.py --start 2026-08-01 --end 2026-10-01 --out data_local/arb
Read-only public endpoints; never trades.
"""
from __future__ import annotations

import argparse
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from backtest import fee_c
from collect import K, event_ticker, get, markets_of

PAIRS = {"KXBTC": "KXBTCD", "KXETH": "KXETHD"}
N = 100                                                  # contracts per leg, for the fee rounding


def candles(series, ev, c):
    """{ticker: DataFrame(minute -> bid, ask)} for the hour before close c, paging through Kalshi's cap"""
    out, start = {}, c - 3600
    while start < c:
        d = get(f"{K}/series/{series}/events/{ev}/candlesticks", period_interval=1, start_ts=start, end_ts=c)
        if not d:
            break
        for t, cs in zip(d.get("market_tickers", []), d.get("market_candlesticks", [])):
            for x in cs:
                b, a = x["yes_bid"].get("close_dollars"), x["yes_ask"].get("close_dollars")
                out.setdefault(t, []).append((x["end_period_ts"], float(b) if b else np.nan, float(a) if a else np.nan))
        nxt = d.get("adjusted_end_ts")
        if not nxt or nxt >= c or nxt <= start:
            break
        start = nxt
    grid = np.arange(c - 3600 + 60, c + 1, 60)
    res = {}
    for t, rows in out.items():
        f = pd.DataFrame(rows, columns=["ts", "bid", "ask"]).drop_duplicates("ts", keep="last").set_index("ts").sort_index()
        f = f.reindex(grid).ffill()
        f.loc[f.ask >= 1, "ask"] = np.nan                # $1 ask = nobody selling
        f.loc[f.bid <= 0, "bid"] = np.nan                # $0 bid = nobody buying
        res[t] = f
    return res, grid


def one_hour(args):
    rng, ab, c = args
    ts = int(c.timestamp())
    er, ea = event_ticker(rng, c), event_ticker(ab, c)
    mr, ma = markets_of(rng, er), markets_of(ab, ea)
    if not mr or not ma:
        return []
    Qr, grid = candles(rng, er, ts)
    Qa, _ = candles(ab, ea, ts)
    above = {round(float(m["floor_strike"]), 2): m["ticker"] for m in ma if m.get("floor_strike") is not None}
    rows = []
    # bracket legs
    for m in mr:
        lo, hi = m.get("floor_strike"), m.get("cap_strike")
        if lo is None or hi is None or m["ticker"] not in Qr:
            continue
        tl, th = above.get(round(float(lo) - 0.01, 2)), above.get(round(float(hi), 2))
        if tl not in Qa or th not in Qa:
            continue
        R, L, H = Qr[m["ticker"]], Qa[tl], Qa[th]
        # A: YES range (ask) + YES above(U) (ask) + NO above(L) (1 - bid)
        a_legs = np.c_[R.ask, H.ask, 1 - L.bid]
        # B: NO range (1 - bid) + NO above(U) (1 - bid) + YES above(L) (ask)
        b_legs = np.c_[1 - R.bid, 1 - H.bid, L.ask]
        for kind, legs, pay in (("A", a_legs, 1.0), ("B", b_legs, 2.0)):
            cost = 100 * legs.sum(1) + fee_c(legs, N).sum(1)
            edge = 100 * pay - cost
            for i in np.flatnonzero(np.isfinite(edge) & (edge > -3)):   # keep near-misses for context
                rows.append({"pair": rng, "event": er, "close": c, "ts": int(grid[i]), "min_left": int((ts - grid[i]) // 60),
                             "kind": kind, "bracket": m["ticker"], "edge_c": float(edge[i]),
                             "legs": tuple(np.round(legs[i], 2))})
    # whole-event: YES on every bracket / NO on every bracket
    ticks = [m["ticker"] for m in mr]
    if all(t in Qr for t in ticks):
        A = np.stack([Qr[t].ask.values for t in ticks], 1)
        B = np.stack([Qr[t].bid.values for t in ticks], 1)
        n = len(ticks)
        for kind, legs, pay in (("ALL_YES", A, 1.0), ("ALL_NO", 1 - B, n - 1.0)):
            cost = 100 * legs.sum(1) + fee_c(legs, N).sum(1)
            edge = 100 * pay - cost
            for i in np.flatnonzero(np.isfinite(edge) & (edge > -3)):
                rows.append({"pair": rng, "event": er, "close": c, "ts": int(grid[i]), "min_left": int((ts - grid[i]) // 60),
                             "kind": kind, "bracket": "", "edge_c": float(edge[i]), "legs": ()})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2026-08-01")
    ap.add_argument("--end", default="2026-10-01")
    ap.add_argument("--out", default="data_local/arb")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    t0 = datetime.fromisoformat(a.start).replace(tzinfo=timezone.utc)
    t1 = datetime.fromisoformat(a.end).replace(tzinfo=timezone.utc)
    hours = [t0 + timedelta(hours=h) for h in range(int((t1 - t0).total_seconds() // 3600))]
    for rng, ab in PAIRS.items():
        jobs = [(rng, ab, c) for c in hours]
        rows, done = [], 0
        with ThreadPoolExecutor(4) as ex:
            for r in ex.map(one_hour, jobs):
                rows += r
                done += 1
                if done % 100 == 0:
                    print(rng, done, "/", len(jobs), flush=True)
        df = pd.DataFrame(rows)
        if len(df):
            df["legs"] = df.legs.astype(str)
        df.to_parquet(os.path.join(a.out, f"{rng}.parquet"))
        print(rng, "rows", len(df), flush=True)


if __name__ == "__main__":
    main()
