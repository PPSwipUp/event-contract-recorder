"""Collect Kalshi's history for hourly BTC/ETH range events: every bracket's strikes and result, plus its
yes bid/ask one hour before settlement (when the hour being predicted starts). Also Coinbase 1-minute prices.

  python backfill/collect.py --start 2026-01-01 --out backfill/out
Read-only public endpoints; no account, never trades.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pandas as pd
import requests

import dohfix  # noqa: F401  (EE hotspot DNS block)

K = "https://api.elections.kalshi.com/trade-api/v2"
ET = ZoneInfo("America/New_York")
SERIES = {"KXBTC": "BTC-USD", "KXETH": "ETH-USD"}
OFFSETS = (1, 5, 15)                                   # minutes after the market opens
MON = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
S = requests.Session()
S.headers["User-Agent"] = "research backfill (read-only)"


def get(url, **params):
    for attempt in range(14):                            # ~10 min of back-off before giving up
        try:
            r = S.get(url, params=params, timeout=30)
        except requests.RequestException:
            time.sleep(2 ** attempt)
            continue
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(min(60, 2 ** attempt))
            continue
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()
    raise RuntimeError(f"gave up on {url}")


def event_ticker(series, close_utc):
    t = close_utc.astimezone(ET)
    return f"{series}-{t:%y}{MON[t.month - 1]}{t:%d%H}"


def markets_of(series, ev):
    """strikes + results; live API for recent events, historical API for older ones"""
    for base in (f"{K}/markets", f"{K}/historical/markets"):
        d = get(base, event_ticker=ev, limit=1000)
        if d and d.get("markets"):
            return d["markets"]
    return []


def one_event(args):
    series, close = args
    ev = event_ticker(series, close)
    ms = markets_of(series, ev)
    if not ms:
        return []
    c = int(close.timestamp())
    # quotes start when the market opens, ~59 min before settlement.  Keep the quote 1, 5 and 15 minutes into
    # trading (the backtest checks whether any edge survives once traders have arrived)
    d = get(f"{K}/series/{series}/events/{ev}/candlesticks", period_interval=1, start_ts=c - 3600, end_ts=c - 2640)
    quote = {}
    if d:
        for t, cs in zip(d.get("market_tickers", []), d.get("market_candlesticks", [])):
            cs = [x for x in cs if x["yes_ask"].get("close_dollars") is not None]
            if not cs:
                continue
            first = cs[0]["end_period_ts"]
            for lag in OFFSETS:
                q = [x for x in cs if x["end_period_ts"] <= first + 60 * (lag - 1)]
                if q:
                    q = q[-1]
                    quote[(t, lag)] = (q["yes_bid"].get("close_dollars"), q["yes_ask"].get("close_dollars"),
                                       q.get("volume_fp"), q["end_period_ts"])
    rows = []
    for m in ms:
        for lag in OFFSETS:
            bid, ask, vol, qts = quote.get((m["ticker"], lag), (None, None, None, None))
            rows.append({"series": series, "event": ev, "close": close.isoformat(), "ticker": m["ticker"],
                         "floor": m.get("floor_strike"), "cap": m.get("cap_strike"), "strike_type": m.get("strike_type"),
                         "result": m.get("result"), "settle_value": m.get("expiration_value"), "lag_min": lag,
                         "bid": bid, "ask": ask, "vol_1m": vol, "quote_ts": qts, "open_time": m.get("open_time"),
                         "volume_total": m.get("volume_fp") or m.get("volume")})
    return rows


def coinbase(product, start, end):
    out, t = [], start
    while t < end:
        u = min(end, t + timedelta(minutes=300))
        d = get(f"https://api.exchange.coinbase.com/products/{product}/candles", granularity=60,
                start=t.strftime("%Y-%m-%dT%H:%M:%SZ"), end=u.strftime("%Y-%m-%dT%H:%M:%SZ"))
        out += d or []
        t = u
        time.sleep(0.12)                                  # public limit ~10 requests/s
    df = pd.DataFrame(out, columns=["ts", "l", "h", "o", "c", "v"]).drop_duplicates("ts").sort_values("ts")
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2026-01-01")
    ap.add_argument("--spot-start", default="2025-01-01")
    ap.add_argument("--out", default="backfill/out")
    ap.add_argument("--end", default="", help="last event day (exclusive), default: now")
    ap.add_argument("--threads", type=int, default=4)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0) - timedelta(hours=2)
    if a.end:
        now = min(now, datetime.fromisoformat(a.end).replace(tzinfo=timezone.utc) - timedelta(hours=1))
    start = datetime.fromisoformat(a.start).replace(tzinfo=timezone.utc)
    hours = pd.date_range(start, now, freq="1h", tz="UTC").to_pydatetime()
    for series, product in SERIES.items():
        t0 = time.time()
        with ThreadPoolExecutor(a.threads) as ex:
            rows = [r for rs in ex.map(one_event, [(series, h) for h in hours]) for r in rs]
        df = pd.DataFrame(rows)
        df.to_parquet(os.path.join(a.out, f"{series}.parquet"))
        if len(df):
            a_ = pd.to_numeric(df.ask, errors="coerce")
            print(f"{series}: real offer (ask < $1) for {a_.lt(1).mean():.0%} of bracket quotes; "
                  f"bid>0 {pd.to_numeric(df.bid, errors='coerce').gt(0).mean():.0%}", flush=True)
        print(f"{series}: {len(rows)} brackets in {len({r['event'] for r in rows})} events "
              f"({time.time() - t0:.0f}s)", flush=True)
        t0 = time.time()
        spot = coinbase(product, datetime.fromisoformat(a.spot_start).replace(tzinfo=timezone.utc), now + timedelta(hours=2))
        spot.to_parquet(os.path.join(a.out, f"{product}.parquet"))
        print(f"{product}: {len(spot)} minutes ({time.time() - t0:.0f}s)", flush=True)
    json.dump({"start": a.start, "collected": datetime.now(timezone.utc).isoformat()}, open(os.path.join(a.out, "meta.json"), "w"))


if __name__ == "__main__":
    main()
