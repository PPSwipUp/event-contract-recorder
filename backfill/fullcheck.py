"""Market-making rule (frozen 8c margin) on (1) whole-hour BTC range trades and (2) BTC above/below (KXBTCD) trades.
Pure out-of-sample: nothing is tuned here.  Fill variants: 25% of each taker trade at its price, and "1c better" (we'd
be first in the queue: full trade, our price 1c worse).  Max 25 contracts per fill.  Maker fee charged.
Broken down by minute of the hour (the original backtest only had minutes 10-20) and by month; no-model baseline too.
  python backfill/fullcheck.py --series KXBTC --chunks data_local/full
"""
from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from maker import maker_fee_c, series_trades

MARGIN, CAP = 8, 25


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", default="KXBTC")
    ap.add_argument("--chunks", default="data_local/full")
    a = ap.parse_args()
    T = series_trades(a.series, "BTC-USD", a.chunks)
    T["day"] = T.close.dt.strftime("%Y-%m-%d")
    T = T[T.day != "2026-09-28"]
    y = T.yes.values
    wy = (T.result == "yes").astype(float).values
    T["our_px"] = np.where(T.taker == "yes", 1 - y, y)
    T["our_p"] = np.where(T.taker == "yes", 1 - T.p_yes, T.p_yes)
    T["won"] = np.where(T.taker == "yes", 1 - wy, wy)
    T["mins_in"] = (T.t - (T.close - pd.Timedelta(hours=1))).dt.total_seconds() // 60
    T = T[(T.our_px > 0) & (T.our_px < 1) & (T.mins_in >= 0) & (T.mins_in < 60)].copy()

    def sel(variant, model=True):
        if variant == "25% fill":
            px, n = T.our_px, np.minimum(T["count"] * 0.25, CAP)
        else:
            px, n = T.our_px + 0.01, np.minimum(T["count"], CAP)
        fee = maker_fee_c(px.clip(0.01, 0.99).values, np.maximum(n.values, 1))
        m = (px < 1) & (n >= 1)
        if model:
            m &= 100 * (T.our_p - px) - fee > MARGIN
        pnl = 100 * T.won - 100 * px - fee
        return T[m].assign(n=n[m], pnl_c=pnl[m], dollars=(pnl * n / 100)[m])

    def summ(B):
        d = B.groupby("day").dollars.sum()
        hours = T.close.nunique()
        return {"fills": len(B), "c_per_contract": round((B.pnl_c * B.n).sum() / max(1, B.n.sum()), 2),
                "total_$": round(B.dollars.sum()), "$_per_sampled_hour": round(B.dollars.sum() / hours, 2),
                "day_t": round(d.mean() / d.std() * np.sqrt(len(d)), 2) if len(d) > 2 and d.std() > 0 else np.nan}

    L = [f"# Maker rule (frozen 8c) on {a.series}, {a.chunks} ({T.close.nunique()} sampled hours, {len(T)} taker trades)", ""]
    L += [pd.DataFrame([{"variant": v, "rule": r, **summ(sel(v, r == "model"))} for v in ("25% fill", "1c better")
                        for r in ("model", "no model")]).to_markdown(index=False), ""]
    B = sel("1c better")
    for key, lab in ((pd.cut(B.mins_in, [-1, 9, 20, 30, 40, 50, 60]), "minute of the hour (1c better)"), (B.day.str[:7], "month (1c better)")):
        g = B.groupby(key, observed=True)
        L += [f"### by {lab}", "", pd.DataFrame({"fills": g.size(), "c_per_contract": (g.apply(lambda x: (x.pnl_c * x.n).sum() / x.n.sum())).round(2),
                                                 "dollars": g.dollars.sum().round(0)}).to_markdown(), ""]
    out = f"../results/FULL_{a.series}.md"
    open(out, "w").write("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    main()
