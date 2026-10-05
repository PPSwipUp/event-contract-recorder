"""Phase 1 of results/PLAN_CRYPTOLEAD.md: fair-value engine for Kalshi KXCRYPTOLEAD15M and its accuracy vs the market.

Fair value at minute m of a 15-min window: return so far r_i = ln(P_i(start+m) / P_i(start)) from 1-min closes
(Coinbase BTC/ETH/SOL/XRP, Bybit spot HYPE); the remaining 15-m minutes simulated by resampling JOINT 1-min return
vectors of the five coins from the previous 3 days (4,000 paths); P(i leads) = share of paths where i is highest.
Compared with the market mid ((bid+ask)/2 from Kalshi 1-min candles) at minutes 3, 7, 11.  Brier per market.
Train < 2026-09-20 <= holdout.  GATE: model Brier <= market Brier + 0.002 on the holdout.
  python backfill/cryptolead.py
"""
from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import requests

import dohfix  # noqa: F401
from collect import K, coinbase, get

D = "data_local/cryptolead"
COINS = {"BTC": "BTC-USD", "ETH": "ETH-USD", "SOL": "SOL-USD", "XRP": "XRP-USD", "HYPE": None}
SPLIT = "2026-09-20"
MINUTES = (3, 7, 11)
PATHS, LOOKBACK_MIN = 4000, 3 * 1440


def markets():
    p = f"{D}/markets.parquet"
    if os.path.exists(p):
        return pd.read_parquet(p)
    rows = []
    for base in ("/markets", "/historical/markets"):
        cur = None
        while True:
            q = {"series_ticker": "KXCRYPTOLEAD15M", "limit": 1000}
            if base == "/markets":
                q["status"] = "settled"
            if cur:
                q["cursor"] = cur
            d = get(K + base, **q) or {}
            rows += d.get("markets", [])
            cur = d.get("cursor")
            if not cur or not d.get("markets"):
                break
    M = pd.DataFrame([{"event": m["event_ticker"], "ticker": m["ticker"], "coin": m["ticker"].split("-")[-1],
                       "close": m["close_time"], "result": m.get("result")} for m in rows]).drop_duplicates("ticker")
    M.to_parquet(p)
    return M


def kget1(url, **params):
    """like collect.get but with capped back-off (collect.get can sleep for hours after network errors)"""
    for attempt in range(20):
        try:
            r = requests.get(url, params=params, timeout=15)
            if r.status_code == 404:
                return None
            if r.status_code != 429 and r.status_code < 500:
                r.raise_for_status()
                return r.json()
        except requests.RequestException:
            pass
        time.sleep(min(20, 2 ** attempt))
    raise RuntimeError(f"gave up on {url}")


DONE = [0]


def candles(ev, close_ts):
    d = kget1(f"{K}/series/KXCRYPTOLEAD15M/events/{ev}/candlesticks", period_interval=1, start_ts=close_ts - 900, end_ts=close_ts) or {}
    DONE[0] += 1
    if DONE[0] % 250 == 0:
        print(time.strftime("%H:%M:%S"), "candles", DONE[0], flush=True)
    out = []
    for t, cs in zip(d.get("market_tickers", []), d.get("market_candlesticks", [])):
        for x in cs:
            b, a = x["yes_bid"].get("close_dollars"), x["yes_ask"].get("close_dollars")
            out.append({"ticker": t, "ts": x["end_period_ts"], "bid": float(b) if b else np.nan, "ask": float(a) if a else np.nan})
    return out


def hype(start, end):
    """Bybit spot HYPEUSDT 1-min closes (Hyperliquid's candleSnapshot only serves the latest 5,000 candles)"""
    out, t = {}, int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)
    while t < end_ms:
        u = min(end_ms, t + 1000 * 60000 - 1)
        r = kget1("https://api.bybit.com/v5/market/kline", category="spot", symbol="HYPEUSDT", interval=1, start=t, end=u, limit=1000)
        for c in r["result"]["list"]:
            out[int(c[0]) // 1000 + 60] = float(c[4])                  # close time = open + 60 s
        t = u + 1
    return pd.Series(out).sort_index()


def prices(start, end):
    p = f"{D}/prices.parquet"
    if os.path.exists(p):
        return pd.read_parquet(p)
    cols = {}
    for c, prod in COINS.items():
        if prod:
            f = coinbase(prod, start, end)
            cols[c] = pd.Series(f.c.values, index=f.ts.values + 60)              # Coinbase ts = candle open
        else:
            cols[c] = hype(start, end)
    P = pd.DataFrame(cols).sort_index()
    P = P.reindex(np.arange(P.index.min(), P.index.max() + 60, 60)).ffill()
    P.to_parquet(p)
    return P


def fair(P, rets, t_now, t_start, t_end, rng):
    """P(each coin leads) given minute closes P (index = minute end ts), using lookback joint returns"""
    r_so_far = np.log(P.loc[t_now].values / P.loc[t_start].values)
    left = int((t_end - t_now) // 60)
    hist = rets.loc[t_now - 60 * LOOKBACK_MIN:t_now].values
    hist = hist[np.isfinite(hist).all(axis=1)]
    if left <= 0 or len(hist) < 500:
        sims = np.tile(r_so_far, (1, 1))
    else:
        idx = rng.integers(0, len(hist), size=(PATHS, left))
        sims = r_so_far + hist[idx].sum(axis=1)
    win = np.argmax(sims, axis=1)
    return np.bincount(win, minlength=len(COINS)) / len(sims)


def main():
    os.makedirs(D, exist_ok=True)
    M = markets()
    M = M[M.result.isin(["yes", "no"])]
    M["close_ts"] = (pd.to_datetime(M.close, format="ISO8601") - pd.Timestamp(0, tz="UTC")) // pd.Timedelta("1s")
    ev = M.groupby("event").close_ts.first()
    cp = f"{D}/candles.parquet"
    if not os.path.exists(cp):
        res = [candles(e, int(ev[e])) for e in ev.index]                # serial: the threaded version hung
        pd.DataFrame([r for x in res for r in x]).to_parquet(cp)
    C = pd.read_parquet(cp)
    assert len(C) > 10 * len(ev), f"only {len(C)} candle rows for {len(ev)} events"
    start = datetime.fromtimestamp(int(ev.min()) - 4 * 86400, timezone.utc)
    end = datetime.fromtimestamp(int(ev.max()) + 120, timezone.utc)
    P = prices(start, end)[list(COINS)]
    rets = np.log(P).diff()
    rng = np.random.default_rng(0)
    order = list(COINS)
    rows = []
    for e, close_ts in ev.items():
        t_start, t_end = close_ts - 900, close_ts
        g = M[M.event == e].set_index("coin")
        if not set(order) <= set(g.index) or t_start not in P.index or t_end not in P.index:
            continue
        for m in MINUTES:
            t_now = t_start + 60 * m
            if t_now not in P.index or not np.isfinite(P.loc[[t_start, t_now]].values).all():
                continue
            fv = fair(P, rets, t_now, t_start, t_end, rng)
            q = C[(C.ts == t_now) & C.ticker.isin(g.ticker)].set_index("ticker")
            for i, coin in enumerate(order):
                tk = g.loc[coin, "ticker"]
                if tk not in q.index:
                    continue
                mid = (q.loc[tk, "bid"] + q.loc[tk, "ask"]) / 2
                rows.append({"event": e, "close_ts": close_ts, "minute": m, "coin": coin, "model": fv[i], "mid": mid,
                             "spread": q.loc[tk, "ask"] - q.loc[tk, "bid"], "y": float(g.loc[coin, "result"] == "yes")})
    R = pd.DataFrame(rows).dropna()
    R["half"] = np.where(pd.to_datetime(R.close_ts, unit="s") < pd.Timestamp(SPLIT), "train", "holdout")
    R.to_parquet(f"{D}/fair_vs_market.parquet")
    S = R.groupby(["half", "minute"]).apply(lambda x: pd.Series({
        "n": len(x), "model_brier": ((x.model - x.y) ** 2).mean(), "market_brier": ((x.mid - x.y) ** 2).mean(),
        "median_spread_c": 100 * x.spread.median()})).round(4)
    h = R[R.half == "holdout"]
    mb, kb = ((h.model - h.y) ** 2).mean(), ((h.mid - h.y) ** 2).mean()
    verdict = "PASS" if mb <= kb + 0.002 else "FAIL"
    L = ["# Crypto-lead 15m: fair-value model vs market mid (Phase 1 of PLAN_CRYPTOLEAD.md)", "",
         f"Windows scored: {R.event.nunique()} ({R.groupby('half').event.nunique().to_dict()})", "", S.to_markdown(), "",
         f"Holdout overall: model Brier {mb:.4f} vs market {kb:.4f} -> GATE {verdict} (needs model <= market + 0.002)", ""]
    open("../results/CRYPTOLEAD_PHASE1.md", "w").write("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    main()
