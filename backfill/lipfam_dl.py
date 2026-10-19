"""Cloud downloader for PLAN_LIP_FAMILIES (GitHub Actions, branch lipfam).  Public unauthenticated Kalshi GET only: no keys, no orders.
Copies of lip_sports.Api / dl_markets_batch / dl_trades_h / dl_candles_h / fetch_family that import only kalshi_lip_bt, so the job does
not need the rest of the research code.  Resumable through the sqlite 'done' table.  Exit 3 = stopped at the deadline, not finished.
Usage: python lipfam_dl.py --windows lipfam_windows.csv --family F1_CARBONARC --db F1_CARBONARC.sqlite --deadline-min 320"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time

import pandas as pd

import kalshi_lip_bt as klb


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


class Api(klb.Api):
    def get(self, path, **p):
        for r in range(6):
            try:
                return super().get(path, **p)
            except Exception as e:                           # noqa
                log("api retry", path[:60], type(e).__name__)
                time.sleep(min(120, 10 * (r + 1)))
        raise RuntimeError("api gave up " + path)


def dl_markets_batch(api, c, tickers):
    have = {r[0] for r in c.execute("select ticker from markets")}
    todo = sorted(set(tickers) - have)
    log(f"markets: {len(have)} cached, {len(todo)} to fetch")
    for i in range(0, len(todo), 100):
        chunk = todo[i:i + 100]
        got = set()
        for path, tag in (("/markets", "live"), ("/historical/markets", "hist")):
            need = [t for t in chunk if t not in got]
            if not need:
                break
            cur = None
            while True:
                p = {"tickers": ",".join(need), "limit": 1000}
                if cur:
                    p["cursor"] = cur
                d = api.get(path, **p) or {}
                ms = d.get("markets", [])
                c.executemany("insert or replace into markets values(?,?,?)", [(m["ticker"], m["ticker"].split("-")[0], json.dumps(m)) for m in ms])
                c.executemany("insert or replace into done values('origin',?,?)", [(m["ticker"], 1 if tag == "hist" else 0) for m in ms])
                got |= {m["ticker"] for m in ms}
                cur = d.get("cursor")
                if not cur or not ms:
                    break
        c.executemany("insert or ignore into done values('origin',?,-1)", [(t,) for t in chunk if t not in got])   # not found anywhere
        c.commit()


def dl_trades_h(api, c, P):
    T = P.groupby("ticker").agg(s0=("s0", "min"), s1=("s1", "max")).reset_index()
    done = {r[0] for r in c.execute("select key from done where kind='trades'")}
    for r in T[~T.ticker.isin(done)].itertuples():
        rows = []
        for path in ("/markets/trades", "/historical/trades"):
            cur = None
            while True:
                p = {"ticker": r.ticker, "min_ts": int(r.s0 - 60), "max_ts": int(r.s1 + 60), "limit": 1000}
                if cur:
                    p["cursor"] = cur
                d = api.get(path, **p) or {}
                for x in d.get("trades", []):
                    rows.append((x["trade_id"], x["ticker"], klb.iso(x["created_time"]), klb.fl(x["yes_price_dollars"]), klb.fl(x["no_price_dollars"]),
                                 klb.fl(x["count_fp"]), x["taker_side"]))
                cur = d.get("cursor")
                if not cur or not d.get("trades"):
                    break
        c.executemany("insert or ignore into trades values(?,?,?,?,?,?,?)", rows)
        c.execute("insert or replace into done values('trades',?,?)", (r.ticker, len(rows)))
        c.commit()


def dl_candles_h(api, c, P):
    hist = {r[0] for r in c.execute("select key from done where kind='origin' and n=1")}
    done = {r[0] for r in c.execute("select key from done where kind='candles'")}
    T = P.groupby("ticker").agg(s0=("s0", "min"), s1=("s1", "max")).reset_index()
    for r in T[T.ticker.isin(hist) & ~T.ticker.isin(done)].itertuples():
        rows = []
        lo, hi = int(r.s0 - 120), int(r.s1 + 60)
        for x0 in range(lo, hi, 4000 * 60):
            d = api.get(f"/historical/markets/{r.ticker}/candlesticks", start_ts=x0, end_ts=min(hi, x0 + 4000 * 60), period_interval=1) or {}
            for k in d.get("candlesticks", []):
                f = lambda a_, b_: (k.get(a_) or {}).get(b_)
                rows.append((r.ticker, k["end_period_ts"], klb.fl(f("yes_bid", "close")), klb.fl(f("yes_ask", "close")), klb.fl(f("yes_bid", "low")),
                             klb.fl(f("yes_bid", "high")), klb.fl(f("yes_ask", "low")), klb.fl(f("yes_ask", "high")), klb.fl(f("price", "close")),
                             klb.fl(k.get("volume"))))
        c.executemany("insert or replace into candles values(?,?,?,?,?,?,?,?,?,?)", rows)
        c.execute("insert or replace into done values('candles',?,?)", (r.ticker, len(rows)))
        c.commit()
    rest = T[~T.ticker.isin(hist)]
    if len(rest):
        klb.dl_candles(api, c, rest.assign(series=rest.ticker.str.split("-").str[0]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--windows", required=True)
    ap.add_argument("--family", required=True)
    ap.add_argument("--db", required=True)
    ap.add_argument("--deadline-min", type=float, default=320)
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--nshards", type=int, default=1)
    ap.add_argument("--gap", type=float, default=0.1, help="seconds between requests (cloud IPs are not shared with the bots)")
    a = ap.parse_args()
    stop = time.time() + 60 * a.deadline_min
    W = pd.read_csv(a.windows)
    P = W[W.family == a.family][["ticker", "series", "s0", "s1"]].copy()
    P = P[P.ticker.map(lambda t: int(hashlib.md5(t.encode()).hexdigest(), 16) % a.nshards == a.shard)]
    api, c = Api(gap=a.gap), klb.db(a.db)
    dl_markets_batch(api, c, sorted(P.ticker.unique()))
    tk = sorted(P.ticker.unique())
    for i in range(0, len(tk), 40):
        if time.time() > stop:
            log("deadline reached; resume in the next run")
            sys.exit(3)
        sub = P[P.ticker.isin(tk[i:i + 40])]
        for fn in (dl_trades_h, dl_candles_h):
            for att in range(3):
                try:
                    fn(api, c, sub)
                    break
                except Exception as e:                       # noqa
                    log("download retry", fn.__name__, type(e).__name__, str(e)[:100])
                    time.sleep(20)
        log(f"{a.family}: {min(i + 40, len(tk))}/{len(tk)} tickers")
    dn = {r[0] for r in c.execute("select key from done where kind='trades'")}
    dc = {r[0] for r in c.execute("select key from done where kind='candles'")}
    miss = [t for t in tk if t not in dn or t not in dc]
    log(f"{a.family}: complete except {len(miss)} tickers")
    sys.exit(3 if miss else 0)


if __name__ == "__main__":
    main()
