"""Favourite-longshot bias across Kalshi (results/PLAN_FAVLONG.md, frozen).

Buy the favourite (YES or NO priced 90-97c at the ask) 6 h (primary) / 1 h (secondary) before close, hold to
settlement, net of a conservative taker fee.  Quotes = close of the last 60-min candle at or before decision time.
  python backfill/favlong.py
"""
from __future__ import annotations

import math
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

import dohfix  # noqa: F401
from collect import K
from cryptolead import kget1

D = "data_local/favlong"
START, END, SPLIT = "2026-08-15", "2026-10-04", "2026-09-15"
PER_SERIES, MIN_EVENTS, MIN_VOL = 40, 5, 1000
BAND = (0.90, 0.97)
RULES = {"6h": (6, 12), "1h": (1, 2)}                    # hours before close, min hours open before close


def markets():
    p = f"{D}/markets.parquet"
    if os.path.exists(p):
        return pd.read_parquet(p)
    rows, day = [], datetime.fromisoformat(START).replace(tzinfo=timezone.utc)
    end = datetime.fromisoformat(END).replace(tzinfo=timezone.utc)
    while day < end:
        cur, a, b = None, int(day.timestamp()), int((day + timedelta(days=1)).timestamp())
        while True:
            q = {"status": "settled", "limit": 1000, "min_close_ts": a, "max_close_ts": b, "mve_filter": "exclude"}
            if cur:
                q["cursor"] = cur
            d = kget1(K + "/markets", **q) or {}
            for m in d.get("markets", []):
                if m.get("result") in ("yes", "no") and not m.get("mve_collection_ticker"):
                    rows.append({"ticker": m["ticker"], "event": m["event_ticker"], "series": m["event_ticker"].split("-")[0],
                                 "open": m["open_time"], "close": m["close_time"], "result": m["result"],
                                 "volume": float(m.get("volume_fp") or 0)})
            cur = d.get("cursor")
            if not cur or not d.get("markets"):
                break
        print(time.strftime("%H:%M:%S"), day.date(), len(rows), flush=True)
        day += timedelta(days=1)
    M = pd.DataFrame(rows).drop_duplicates("ticker")
    M.to_parquet(p)
    return M


def sample(M):
    ev = M.groupby("event").agg(series=("series", "first")).reset_index()
    n = ev.groupby("series").event.transform("size")
    ev = ev[n >= MIN_EVENTS]
    return ev.sample(frac=1, random_state=0).groupby("series").head(PER_SERIES)


def candles(series, ev, close_ts):
    d = kget1(f"{K}/series/{series}/events/{ev}/candlesticks", period_interval=60,
              start_ts=close_ts - 13 * 3600, end_ts=close_ts) or {}
    out = []
    for t, cs in zip(d.get("market_tickers", []), d.get("market_candlesticks", [])):
        for x in cs:
            b, a = x["yes_bid"].get("close_dollars"), x["yes_ask"].get("close_dollars")
            out.append({"ticker": t, "ts": x["end_period_ts"], "bid": float(b) if b else np.nan, "ask": float(a) if a else np.nan})
    return out


def fee(p):
    return math.ceil(round(0.07 * 100 * p * (1 - p) * 100, 6)) / 100 / 100      # $ per contract, 100-lot order


def trades(M, C, hours, min_open, band):
    out = []
    C = C.sort_values("ts")
    for tk, g in C.groupby("ticker"):
        m = M.loc[tk]
        t_dec = m.close_ts - hours * 3600
        if m.open_ts > m.close_ts - min_open * 3600:
            continue
        q = g[g.ts <= t_dec]
        if q.empty:
            continue
        bid, ask = q.bid.iloc[-1], q.ask.iloc[-1]
        y = 1.0 if m.result == "yes" else 0.0
        for side, px, win in (("yes", ask, y), ("no", 1 - bid, 1 - y)):
            if np.isfinite(px) and band[0] <= px <= band[1]:
                out.append({"ticker": tk, "series": m.series, "close_ts": m.close_ts, "side": side, "px": px,
                            "win": win, "pnl": win - px - fee(px)})
    return pd.DataFrame(out)


def clustered(T):
    if T.empty:
        return np.nan, np.nan, 0
    s = T.groupby("series").pnl.agg(["sum", "size"])
    mu = s["sum"].sum() / s["size"].sum()
    resid = T.pnl - mu
    g = resid.groupby(T.series).sum()
    se = math.sqrt((g ** 2).sum()) / len(T)
    return mu, mu / se if se > 0 else np.nan, len(s)


def main():
    os.makedirs(D, exist_ok=True)
    M = markets()
    M["close_ts"] = (pd.to_datetime(M.close, format="ISO8601") - pd.Timestamp(0, tz="UTC")) // pd.Timedelta("1s")
    M["open_ts"] = (pd.to_datetime(M.open, format="ISO8601") - pd.Timestamp(0, tz="UTC")) // pd.Timedelta("1s")
    print("markets", len(M), "series", M.series.nunique(), "events", M.event.nunique(), flush=True)
    S = sample(M)
    cp = f"{D}/candles.parquet"
    if not os.path.exists(cp):
        close = M.groupby("event").close_ts.max()
        def one(i_r):
            i, r = i_r
            if i % 1000 == 0:
                print(time.strftime("%H:%M:%S"), "candles", i, "/", len(S), flush=True)
            return candles(r.series, r.event, int(close[r.event]))
        with ThreadPoolExecutor(6) as ex:
            rows = [x for part in ex.map(one, enumerate(S.itertuples())) for x in part]
        pd.DataFrame(rows).to_parquet(cp)
    C = pd.read_parquet(cp)
    assert len(C) > 5 * len(S), f"only {len(C)} candle rows for {len(S)} events"
    M = M[M.event.isin(S.event) & (M.volume >= MIN_VOL)].set_index("ticker")
    C = C[C.ticker.isin(M.index)]
    split = (pd.Timestamp(SPLIT) - pd.Timestamp(0)) // pd.Timedelta("1s")
    L = ["# Favourite-longshot bias across Kalshi (PLAN_FAVLONG.md)", "",
         f"Sampled events: {len(S)} from {S.series.nunique()} series; markets with volume >= {MIN_VOL}: {len(M)}", ""]
    res = {}
    for name, (h, mo) in RULES.items():
        for label, band in (("favourite 90-97c", BAND), ("mirror: longshot 3-10c", (0.03, 0.10))):
            T = trades(M, C, h, mo, band)
            if T.empty:
                continue
            T["half"] = np.where(T.close_ts < split, "train", "holdout")
            T.to_parquet(f"{D}/trades_{name}_{band[0]:.2f}.parquet")
            for half in ("train", "holdout"):
                mu, t, ns = clustered(T[T.half == half])
                res[(name, label, half)] = (len(T[T.half == half]), ns, mu, t)
    R = pd.DataFrame([{"rule": k[0], "trade": k[1], "half": k[2], "n": v[0], "series": v[1],
                       "mean_pnl_c": round(100 * v[2], 3), "t_clustered": round(v[3], 2)} for k, v in res.items()])
    L += ["## Net P&L per contract (cents), SE clustered by series", "", R.to_markdown(index=False), ""]
    T = pd.read_parquet(f"{D}/trades_6h_0.90.parquet")
    T["bucket"] = (T.px * 100).round().astype(int)
    cal = T.groupby(["half", "bucket"]).agg(n=("win", "size"), win_rate=("win", "mean"), mean_pnl_c=("pnl", "mean"))
    cal["mean_pnl_c"] *= 100
    L += ["## Calibration, primary rule (price bucket in cents)", "", cal.round(3).to_markdown(), ""]
    T["cat"] = T.series.str.replace(r"^KX", "", regex=True).str[:5]
    top = T[T.half == "holdout"].groupby("cat").agg(n=("pnl", "size"), mean_pnl_c=("pnl", "mean")).sort_values("n", ascending=False).head(15)
    top["mean_pnl_c"] *= 100
    L += ["## Holdout by series prefix (top 15 by trades)", "", top.round(3).to_markdown(), ""]
    n, ns, mu, t = res[("6h", "favourite 90-97c", "holdout")]
    verdict = "PASS" if mu > 0 and t > 2 else "FAIL"
    L += [f"GATE (6h favourite, holdout): mean {100 * mu:.3f}c/contract, clustered t {t:.2f}, n {n} over {ns} series -> {verdict}", ""]
    open("../results/FAVLONG.md", "w").write("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    main()
