"""Kalshi monthly BTC max/min ("how high / how low will BTC get this month") vs the volatility model, 2026.

YES if BTC trades above (max) / below (min) the strike at any time before month end.  Model, for a market not yet hit:
  P(touch) = min(1, 2 * P(end beyond strike))  (reflection), with P from the empirical shape z of hourly returns and
  sigma = k * (7-day mean of PPC hourly forecasts) * sqrt(hours left).  k, z from hourly data BEFORE 2026 (no tuning
  on these markets).  Spot = Coinbase, one minute stale; a market whose strike was already crossed is skipped.
Entries: per market, side and UTC day, the first real taker trade.  Size = what other takers bought on that side at our
price or better later that day (max 100).  Kalshi fees.
Pre-declared: margin picked on Jan-Apr 2026, run once on May-Sep 2026.  Profits cluster by month, so the t-stat is
also shown by month.
  python backfill/touch.py
"""
from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from backtest import fee_c, hourly, sigmas
from collect import K, coinbase, get

SERIES = {"KXBTCMAXMON": "max", "KXBTCMINMON": "min"}
TRAIN, HOLD = ("2026-01-01", "2026-05-01"), ("2026-05-01", "2026-10-01")
CAP = 100


def all_markets(s):
    out = []
    for base, ex in (("/markets", {"status": "settled"}), ("/historical/markets", {})):
        cur = None
        while True:
            p = dict(series_ticker=s, limit=1000, **ex)
            if cur:
                p["cursor"] = cur
            d = get(f"{K}{base}", **p) or {}
            out += d.get("markets", [])
            cur = d.get("cursor")
            if not cur or not d.get("markets"):
                break
    return out


def trades(ticker):
    out = []
    for base in (f"{K}/historical/trades", f"{K}/markets/trades"):
        cur = None
        while True:
            p = {"ticker": ticker, "limit": 1000}
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
    cache = "data_local/touch_trades.parquet"
    if os.path.exists(cache):
        T = pd.read_parquet(cache)
    else:
        rows = []
        for s, kind in SERIES.items():
            ms = [m for m in all_markets(s) if m.get("result") in ("yes", "no")]
            with ThreadPoolExecutor(4) as ex:
                for m, ts in zip(ms, ex.map(trades, [m["ticker"] for m in ms])):
                    strike = m.get("floor_strike") if kind == "max" else (m.get("cap_strike") or m.get("floor_strike"))
                    for t in ts:
                        rows.append({"series": s, "kind": kind, "ticker": m["ticker"], "strike": float(strike),
                                     "open_time": m["open_time"], "close_time": m["close_time"], "result": m["result"],
                                     "ts": t["created_time"], "taker": t.get("taker_side"),
                                     "yes": float(t.get("yes_price_dollars") or np.nan), "count": float(t.get("count_fp") or 0)})
            print(s, len(ms), "markets", flush=True)
        T = pd.DataFrame(rows)
        T.to_parquet(cache)
    print("trades", len(T), flush=True)

    spot = coinbase("BTC-USD", datetime(2025, 6, 1, tzinfo=timezone.utc), datetime(2026, 10, 2, tzinfo=timezone.utc))
    W, minute = hourly(spot)
    S = sigmas(W)
    tr = (W.index < pd.Timestamp("2026-01-01", tz="UTC")) & S.ppc.notna()
    k = float(np.median(np.abs(W.ret[tr]) / S.ppc[tr]))
    z = np.sort((W.ret[tr] / (k * S.ppc[tr])).values)
    sig7 = S.ppc.rolling(24 * 7, min_periods=24).mean()

    T["t"] = pd.to_datetime(T.ts, format="ISO8601", utc=True)
    T["day"] = T.t.dt.strftime("%Y-%m-%d")
    T["px"] = np.where(T.taker == "yes", T.yes, 1 - T.yes)
    T = T.sort_values("t")
    E = T.groupby(["ticker", "taker", "day"]).head(1).copy()
    J = E[["ticker", "taker", "day", "t", "px"]].merge(T[["ticker", "taker", "day", "t", "px", "count"]],
                                                        on=["ticker", "taker", "day"], suffixes=("", "_o"))
    av = J[(J.t_o > J.t) & (J.px_o <= J.px + 1e-9)].groupby(["ticker", "taker", "day"])["count"].sum()
    E = E.join(av.rename("avail"), on=["ticker", "taker", "day"])
    E["avail"] = E.avail.fillna(0)

    E["s0"] = minute.reindex(E.t.dt.floor("1min") - pd.Timedelta(minutes=1)).values
    # running max / min since the market opened, up to one minute before the trade
    lp = minute
    run_hi, run_lo = [], []
    for o, t in zip(pd.to_datetime(E.open_time, format="ISO8601", utc=True), E.t.dt.floor("1min") - pd.Timedelta(minutes=1)):
        seg = lp.loc[o:t]
        run_hi.append(seg.max() if len(seg) else np.nan)
        run_lo.append(seg.min() if len(seg) else np.nan)
    E["hi"], E["lo"] = run_hi, run_lo
    hours = (pd.to_datetime(E.close_time, format="ISO8601", utc=True).groupby(E.ticker).transform("max") - E.t).dt.total_seconds() / 3600
    # month end: the scheduled close of the series' month (an early close means it was hit; use the latest close in the event)
    ev_end = pd.to_datetime(E.close_time, format="ISO8601", utc=True)
    ev_end = ev_end.groupby(E.ticker.str.rsplit("-", n=1).str[0]).transform("max")
    hours = (ev_end - E.t).dt.total_seconds() / 3600
    sig = k * sig7.reindex(E.t.dt.floor("1h")).values * np.sqrt(np.clip(hours.values, 0.1, None))
    lk = np.log(E.strike.values)
    xmax = (lk - E.s0.values) / sig
    xmin = (lk - E.s0.values) / sig
    p_end_above = 1 - np.searchsorted(z, np.nan_to_num(xmax)) / len(z)
    p_end_below = np.searchsorted(z, np.nan_to_num(xmin)) / len(z)
    p_touch = np.where(E.kind == "max", np.minimum(1, 2 * p_end_above), np.minimum(1, 2 * p_end_below))
    already = np.where(E.kind == "max", E.hi >= lk, E.lo <= lk)
    E["p_yes"] = p_touch
    E = E[~already & np.isfinite(E.s0) & np.isfinite(sig) & (E.px > 0) & (E.px < 1)].copy()
    E["p"] = np.where(E.taker == "yes", E.p_yes, 1 - E.p_yes)
    E["won"] = np.where(E.taker == "yes", E.result == "yes", E.result == "no").astype(float)
    E["fee"] = fee_c(E.px.values, 100)
    E["edge_c"] = 100 * (E.p - E.px) - E.fee
    E["pnl_c"] = 100 * E.won - 100 * E.px - E.fee
    E["month"] = E.day.str[:7]

    def run(margin, s, e, cap=CAP):
        B = E[(E.edge_c > margin) & (E.avail > 0) & (E.day >= s) & (E.day < e)].copy()
        B["n"] = np.minimum(B.avail, cap)
        B["dollars"] = B.pnl_c * B.n / 100
        d = B.groupby("day").dollars.sum()
        mo = B.groupby("month").dollars.sum()
        t = d.mean() / d.std() * np.sqrt(len(d)) if len(d) > 2 and d.std() > 0 else np.nan
        return {"bets": len(B), "c_per_bet": round(B.pnl_c.mean(), 2) if len(B) else np.nan, "total_$": round(B.dollars.sum()),
                "per_month_$": round(mo.sum() / max(1, len(mo))), "months_pos": f"{(mo > 0).sum()}/{len(mo)}",
                "day_t": round(t, 2), "avg_contracts": round(B.n.mean(), 1) if len(B) else 0}

    L = ["# Kalshi monthly BTC max/min vs volatility model (2026)", "",
         f"Entries (first trade per market/side/day, strike not yet hit): {len(E)}; k = {k:.2f}", "",
         "Brier (lower better): model "
         f"{((E.p - E.won) ** 2).mean():.4f} vs traded price {((E.px - E.won) ** 2).mean():.4f}", ""]
    G = pd.DataFrame([{"margin_c": mg, **{f"train_{a}": b for a, b in run(mg, *TRAIN).items()}} for mg in (3, 5, 8, 12, 20)])
    ok = G[G.train_bets >= 50]
    best = int(ok.sort_values("train_day_t", ascending=False).margin_c.iloc[0]) if len(ok) else 8
    L += ["## Margin picked on Jan-Apr", "", G.to_markdown(index=False), "", f"Chosen {best}c", "",
          "## Holdout May-Sep (run once)", "",
          pd.DataFrame([{"cap": c, **run(best, *HOLD, cap=c)} for c in (100, 500)]).to_markdown(index=False), ""]
    B = E[(E.edge_c > best) & (E.avail > 0) & (E.day >= HOLD[0])]
    L += ["### Holdout by series / side", "",
          B.groupby(["series", "taker"]).agg(bets=("pnl_c", "size"), c_per_bet=("pnl_c", "mean")).round(2).to_markdown(), ""]
    open("../results/TOUCH.md", "w").write("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    main()
