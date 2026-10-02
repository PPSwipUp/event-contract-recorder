"""Fake-checks for the market-making result (maker.py): is it the model, or just the spread, or a leak?
HOLDOUT 2026 only, margin 8c (as chosen on TRAIN).
  1 no model: sell to EVERY taker              2 random selection of the same number of trades
  3 model fed a 5-minute-old spot price        4 fill 10% / 25% / 50%
  5 by series, month, taker trade size, minutes into the window
  python backfill/makercheck.py
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

import maker
from maker import HOLD, maker_fee_c

MARGIN = 8


def prep(T):
    T = T.copy()
    T["day"] = T.close.dt.strftime("%Y-%m-%d")
    T = T[~T.day.isin(maker.EXCLUDE) & (T.day >= HOLD[0]) & (T.day < HOLD[1])]
    y = T.yes.values
    wy = (T.result == "yes").astype(float).values
    T["our_px"] = np.where(T.taker == "yes", 1 - y, y)
    T["our_p"] = np.where(T.taker == "yes", 1 - T.p_yes, T.p_yes)
    T["won"] = np.where(T.taker == "yes", 1 - wy, wy)
    return T[(T.our_px > 0) & (T.our_px < 1)].copy()


def stats(T, mask, fill=0.25, cap=25):
    B = T[mask].copy()
    B["n"] = np.minimum(B["count"] * fill, cap)
    B = B[B.n >= 1]
    fee = maker_fee_c(B.our_px.values, B.n.values)
    B["pnl_c"] = 100 * B.won - 100 * B.our_px - fee
    B["dollars"] = B.pnl_c * B.n / 100
    d = B.groupby("day").dollars.sum()
    t = d.mean() / d.std() * np.sqrt(len(d)) if len(d) > 2 and d.std() > 0 else np.nan
    return {"fills": len(B), "c_per_contract": round((B.pnl_c * B.n).sum() / max(1, B.n.sum()), 2),
            "per_month_$": round(B.dollars.sum() / 9), "day_t": round(t, 2)}, B


def edge(T, fill=0.25, cap=25):
    n = np.maximum(np.minimum(T["count"].values * fill, cap), 1)
    return 100 * (T.our_p - T.our_px) - maker_fee_c(T.our_px.values, n)


if __name__ == "__main__":
    T = prep(pd.read_parquet("data_local/maker_trades.parquet"))
    sel = edge(T) > MARGIN
    rows = [{"check": "model, margin 8c (25% fill, max 25)", **stats(T, sel)[0]},
            {"check": "1 no model: sell to every taker", **stats(T, np.ones(len(T), bool))[0]}]
    rng = np.random.default_rng(0)
    r = np.zeros(len(T), bool)
    r[rng.choice(len(T), sel.sum(), replace=False)] = True
    rows.append({"check": "2 random trades, same count", **stats(T, r)[0]})
    stale_cache = "data_local/maker_trades_stale5.parquet"
    if not os.path.exists(stale_cache):
        orig = maker.series_trades

        def stale_series(series, product):                     # spot 5 minutes older than in the real test
            import backtest
            h0 = backtest.hourly

            def hourly_shift(spot):
                W, minute = h0(spot)
                return W, minute.shift(5)
            maker.hourly = hourly_shift
            try:
                return orig(series, product)
            finally:
                maker.hourly = h0
        pd.concat([stale_series(s, p) for s, p in maker.PAIRS.items()], ignore_index=True).to_parquet(stale_cache)
    Ts = prep(pd.read_parquet(stale_cache))
    rows.append({"check": "3 model given a 5-min-old spot", **stats(Ts, edge(Ts) > MARGIN)[0]})
    for f in (0.10, 0.25, 0.5):
        rows.append({"check": f"4 fill {int(f * 100)}%, max 25", **stats(T, edge(T, f) > MARGIN, f)[0]})
    L = ["# Market-making fake-checks (HOLDOUT 2026)", "", pd.DataFrame(rows).to_markdown(index=False), ""]
    _, B = stats(T, sel)
    B["mins_in"] = ((B.t - (B.close - pd.Timedelta(hours=1))).dt.total_seconds() // 60).astype(int)
    for key, lab in ((B.series, "series"), (B.day.str[:7], "month"),
                     (pd.cut(B["count"], [0, 5, 25, 100, 500, 1e9]), "taker trade size"),
                     (pd.cut(B.mins_in, [9, 12, 15, 18, 21]), "minutes after open"),
                     (B.taker, "taker side"), (pd.cut(B.our_px, [0, .15, .5, .85, 1]), "our price")):
        g = B.groupby(key, observed=True)
        L += [f"### by {lab}", "", pd.DataFrame({"fills": g.size(), "c_per_contract": g.pnl_c.mean().round(2),
                                                 "dollars": g.dollars.sum().round(0)}).to_markdown(), ""]
    open("../results/MAKER_CHECKS.md", "w").write("\n".join(L))
    print("\n".join(L))
