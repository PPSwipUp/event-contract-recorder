"""Jan-Jul 2026 holdout for the ETH rules, using Kalshi's archived TRADES (quotes don't exist that far back).

A real trade where the taker bought YES at 12c proves YES could be bought at 12c at that moment; same for NO.
For each bracket near the money: the first YES-taker and first NO-taker trade 10-20 min after the market opened
are the prices we could have bought at; the last trade price in that window stands in for the market's odds.

Frozen rules (chosen before any of this data was looked at):
  forward   rolling vol scale + volatility view, >5c edge after fees        (the live forward test)
  sweep     fixed scale, odds pulled halfway to the market, >2c edge        (the sweep's pick)
  base      fixed scale, no filter, >5c edge                                  (reference)
plus WALK-FORWARD: every day the bot picks, from an 18-config grid, the config with the best total over the
previous 30 days (only past data), and uses it for that day.

  python backfill/tradebt.py collect --start 2026-01-01 --end 2026-02-01 --out chunk
  python backfill/tradebt.py evaluate --chunks chunks --out results/HOLDOUT_JAN_JUL.md
"""
from __future__ import annotations

import argparse
import glob
import itertools
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

import research
from backtest import fee_c, hourly, sigmas
from collect import K, coinbase, event_ticker, get, markets_of

SERIES, PRODUCT = "KXETH", "ETH-USD"
WINDOW = (600, 1200)                      # seconds after the market opens
NEAR = 0.03                               # brackets within 3% of the price at the open


def _trades(ticker, t0, t1):
    for base in (f"{K}/historical/trades", f"{K}/markets/trades"):
        d = get(base, ticker=ticker, min_ts=t0, max_ts=t1, limit=1000)
        if d and d.get("trades"):
            return d["trades"]
    return []


def collect(a):
    start = datetime.fromisoformat(a.start).replace(tzinfo=timezone.utc)
    end = datetime.fromisoformat(a.end).replace(tzinfo=timezone.utc)
    spot = coinbase(PRODUCT, start - timedelta(hours=3), end + timedelta(hours=2))
    px = pd.Series(spot.c.values, index=pd.to_datetime(spot.ts, unit="s", utc=True)).sort_index()

    def one(close):
        try:
            return _one(close)
        except Exception as err:                         # one stubborn event must not lose the whole chunk
            print(f"skipped {close:%Y-%m-%d %H}: {err}", flush=True)
            return []

    def _one(close):
        ev = event_ticker(SERIES, close)
        ms = markets_of(SERIES, ev)
        if not ms:
            return []
        op = pd.Timestamp(ms[0].get("open_time") or (close - timedelta(hours=1)).isoformat())
        s = px.asof(op)
        rows = []
        for m in ms:
            lo, hi = m.get("floor_strike"), m.get("cap_strike")
            ref = hi if lo is None else lo if hi is None else (lo + hi) / 2
            if ref is None or not np.isfinite(s) or abs(ref / s - 1) > NEAR:
                continue
            for t in _trades(m["ticker"], int(op.timestamp()) + WINDOW[0], int(op.timestamp()) + WINDOW[1]):
                rows.append({"event": ev, "close": close.isoformat(), "open": op.isoformat(), "ticker": m["ticker"],
                             "floor": lo, "cap": hi, "result": m.get("result"), "ts": t["created_time"],
                             "taker": t.get("taker_side"), "yes": float(t.get("yes_price_dollars") or np.nan),
                             "no": float(t.get("no_price_dollars") or np.nan),
                             "count": float(t.get("count_fp") or t.get("count") or 0)})
        return rows

    hours = pd.date_range(start + timedelta(hours=1), end, freq="1h", tz="UTC").to_pydatetime()
    with ThreadPoolExecutor(4) as ex:
        rows = [r for rs in ex.map(one, hours) for r in rs]
    os.makedirs(a.out, exist_ok=True)
    pd.DataFrame(rows).to_parquet(os.path.join(a.out, "trades.parquet"))
    print(f"{a.start}: {len(rows)} trades, {len({r['event'] for r in rows})} events", flush=True)


def brackets(T, minute):
    """one row per bracket: first YES-buy price, first NO-buy price (with their times), and the market's price as
    known at the time of our bet: the bracket's FIRST trade in the window (never a later one - that leaks the future)"""
    T = T.copy()
    T["t"] = pd.to_datetime(T.ts, utc=True, format="ISO8601")
    T = T.sort_values("t")
    g = T.groupby("ticker")
    B = g.agg(event=("event", "first"), close=("close", "first"), floor=("floor", "first"), cap=("cap", "first"),
              result=("result", "first"), mkt=("yes", "first")).reset_index()
    fy = T[T.taker == "yes"].groupby("ticker").agg(ask=("yes", "first"), t_yes=("t", "first"))
    fn = T[T.taker == "no"].groupby("ticker").agg(no_ask=("no", "first"), t_no=("t", "first"))
    B = B.join(fy, on="ticker").join(fn, on="ticker")
    B["close"] = pd.to_datetime(B.close, utc=True)
    B["win"] = B.close - pd.Timedelta(hours=1)
    B["y"] = (B.result == "yes").astype(float)
    B = B[B.result.isin(["yes", "no"])].copy()
    for side, tcol in (("yes", "t_yes"), ("no", "t_no")):
        t = B[tcol]
        # price at the end of the last COMPLETE minute before the trade (a minute bar's close is its end: using the
        # trade's own minute would peek up to 60 s ahead)
        B[f"s0_{side}"] = minute.reindex(t.dt.floor("1min") - pd.Timedelta(minutes=1)).values
        B[f"left_{side}"] = np.sqrt(np.clip((B.close - t).dt.total_seconds().values / 3600, 0.01, 1))
    return B


def evaluate(a):
    T = pd.concat([pd.read_parquet(f) for f in sorted(glob.glob(os.path.join(a.chunks, "*", "trades.parquet")))],
                  ignore_index=True)
    spot = coinbase(PRODUCT, datetime(2025, 7, 1, tzinfo=timezone.utc), datetime(2026, 8, 2, tzinfo=timezone.utc))
    W, minute = hourly(spot)
    S = sigmas(W)
    B = brackets(T, minute)
    B["sig_raw"] = S.ppc.reindex(B.win).values
    tr = (W.index < pd.Timestamp("2026-01-01", tz="UTC")) & S.ppc.notna()
    k_fixed = float(np.median(np.abs(W.ret[tr]) / S.ppc[tr]))
    z = np.sort((W.ret[tr] / (k_fixed * S.ppc[tr])).values)
    k_roll = (np.abs(W.ret) / S.ppc).shift(1).rolling(24 * 30, min_periods=24 * 7).median().reindex(B.win).values
    k_roll = np.where(np.isfinite(k_roll), k_roll, k_fixed)
    B["day"] = B.close.dt.strftime("%Y-%m-%d")

    def p_of(side, k):
        X = B.assign(s0=B[f"s0_{side}"], left=B[f"left_{side}"])
        return research.probs(X, z, k)

    def implied(k):
        """per event: vol multiplier whose bracket odds best match the last trade prices"""
        X = B.assign(s0=B.s0_yes.fillna(B.s0_no), left=B.left_yes.fillna(B.left_no))
        ok = np.isfinite(X.s0) & np.isfinite(X.mkt)
        err = np.stack([np.where(ok, (research.probs(X, z, k, m) - X.mkt.values) ** 2, 0) for m in research.MULTS], 1)
        best = pd.DataFrame(err, index=B.index).groupby(B.event).sum().idxmin(axis=1).map(lambda j: research.MULTS[j])
        return B.event.map(best).values, X

    configs = {}
    for scale, filt, margin in itertools.product(("fixed", "rolling"), ("none", "volview", "shrink50"), (2, 5, 10)):
        k = np.full(len(B), k_fixed) if scale == "fixed" else k_roll
        py, pn = p_of("yes", k), p_of("no", k)
        ay = an = np.ones(len(B), bool)
        if filt == "shrink50":
            py, pn = B.mkt.values + 0.5 * (py - B.mkt.values), B.mkt.values + 0.5 * (pn - B.mkt.values)
        if filt == "volview":
            m, X = implied(k)
            centre = np.where(B.floor.isna(), B.cap, np.where(B.cap.isna(), B.floor, (B.floor + B.cap) / 2))
            outer = np.abs(np.log(centre) - X.s0.values) / (k * B.sig_raw.values * X.left.values) > 1.0
            more, less = m < 1 / 1.2, m > 1.2
            ay, an = (more & outer) | (less & ~outer), (more & ~outer) | (less & outer)
        ask, nask, y = B.ask.values, B.no_ask.values, B.y.values
        by = np.isfinite(ask) & np.isfinite(py) & ay & (100 * (py - ask) - fee_c(ask, 100) > margin)
        bn = np.isfinite(nask) & np.isfinite(pn) & an & (100 * ((1 - pn) - nask) - fee_c(nask, 100) > margin)
        pnl = np.r_[(100 * y - 100 * ask - fee_c(ask, 100))[by], (100 * (1 - y) - 100 * nask - fee_c(nask, 100))[bn]]
        day = np.r_[B.day.values[by], B.day.values[bn]]
        configs[(scale, filt, margin)] = pd.DataFrame({"day": day, "pnl_c": pnl})

    def summary(name, D):
        d = D.groupby("day").pnl_c.sum()
        t = d.mean() / (d.std(ddof=1) / np.sqrt(len(d))) if len(d) > 2 and d.std() > 0 else np.nan
        months = D.assign(m=D.day.str[:7]).groupby("m").pnl_c.sum()
        return {"rule": name, "bets": len(D), "c_per_bet": D.pnl_c.mean() if len(D) else np.nan,
                "dollars_100": D.pnl_c.sum(), "day_t": t, "days_with_bets": len(d),
                "months_positive": f"{int((months > 0).sum())}/{len(months)}"}

    rows = [summary("forward  (rolling, volview, 5c)", configs[("rolling", "volview", 5)]),
            summary("sweep    (fixed, shrink50, 2c)", configs[("fixed", "shrink50", 2)]),
            summary("base     (fixed, none, 5c)", configs[("fixed", "none", 5)])]

    # walk-forward: each day use the config with the best trailing-30-day total (past only)
    days = sorted(B.day.unique())
    daily = pd.DataFrame({c: D.groupby("day").pnl_c.sum() for c, D in configs.items()}).reindex(days).fillna(0)
    chosen, picks = [], []
    for i, d in enumerate(days):
        if i < 30:
            continue
        past = daily.iloc[i - 30:i].sum()
        c = past.idxmax()
        picks.append(c)
        D = configs[c]
        chosen.append(D[D.day == d])
    WF = pd.concat(chosen, ignore_index=True) if chosen else pd.DataFrame(columns=["day", "pnl_c"])
    rows.append(summary("walk-forward (re-picks settings daily)", WF))
    R = pd.DataFrame(rows)
    pc = pd.Series([str(p) for p in picks]).value_counts().head(5)
    L = ["# Jan-Jul 2026 holdout (ETH hourly ranges, real trade prices 10-20 min after open)", "",
         f"{B.event.nunique()} events, {len(B)} brackets that traded near the money. Rules frozen beforehand; "
         "nothing was tuned on this period. day_t = t-statistic with each day as one observation.", "",
         R.round(2).to_markdown(index=False), "",
         "Settings the walk-forward bot picked most often (scale, filter, margin): "
         + ", ".join(f"{k} x{v}" for k, v in pc.items()), "",
         "## Month by month", "",
         pd.DataFrame({name: D.assign(m=D.day.str[:7]).groupby("m").pnl_c.sum()
                       for name, D in (("forward", configs[("rolling", "volview", 5)]),
                                       ("sweep", configs[("fixed", "shrink50", 2)]),
                                       ("base", configs[("fixed", "none", 5)]),
                                       ("walk-forward", WF))}).round(0).to_markdown(), "",
         "(dollars at 100 contracts per bet)"]
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    open(a.out, "w").write("\n".join(L))
    print("\n".join(L))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["collect", "evaluate"])
    ap.add_argument("--start")
    ap.add_argument("--end")
    ap.add_argument("--out", default="chunk")
    ap.add_argument("--chunks", default="chunks")
    a = ap.parse_args()
    collect(a) if a.cmd == "collect" else evaluate(a)


if __name__ == "__main__":
    main()
