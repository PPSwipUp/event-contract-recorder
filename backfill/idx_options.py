"""Kalshi S&P 500 daily ranges vs same-day SPX options (SPXW, PM-settled) on OLD data.

For a sample of 2026 trading days: 1-minute trade prices of SPXW calls (Massive free tier) at strikes K-5 and K+5 around
each bracket edge K near the money.  P(close >= K) = (C(K-5) - C(K+5)) / 10, using only minutes where both options
traded in the last 2 minutes.  A bracket's options probability = P(>= L) - P(>= U).
Kalshi side = the same real trade entries as idx_backtest.py (first taker trade per market/side/30-min slot).
Tests:
  1. Relative value: buy on Kalshi when the options say it's worth > margin more than we pay (after fees), hold to
     settlement.  Margin picked on the first half of the sampled days, judged once on the second half.
  2. Locked-in arbitrage: same, but the options legs must be traded too - checked against a cost of half an assumed
     option bid/ask spread per leg (SPXW near the money: $0.10-0.30 wide).
  python backfill/idx_options.py --days 40
"""
from __future__ import annotations

import argparse
import os

import numpy as np
import pandas as pd

from idx_backtest import CAP, D, ET, bars, entries
from massive import minutes


def opt_ticker(day, k):
    return f"O:SPXW{pd.Timestamp(day):%y%m%d}C{int(round(k * 1000)):08d}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=40)
    ap.add_argument("--near", type=float, default=0.0075)
    a = ap.parse_args()
    m, _ = bars("SPY")
    E = entries("KXINX", m)
    E = E[(E.day >= "2026-01-01") & np.isfinite(E.ratio)].copy()
    days = sorted(E.day.unique())
    pick = days[::max(1, len(days) // a.days)][:a.days]
    E = E[E.day.isin(pick)].copy()
    prev = E.groupby("day").ratio.first() * m.groupby("day").c.last().shift(1).reindex(pick).values   # previous official close
    # strikes needed per day: K-5, K+5 for every bracket edge within `near` of the previous close
    probs = {}
    for d in pick:
        p0 = prev.get(d)
        if not np.isfinite(p0):
            continue
        edges = sorted({x for x in pd.concat([E[E.day == d].floor, E[E.day == d].cap + 1e-4]).dropna().round(2)
                        if abs(x / p0 - 1) <= a.near})
        C = {}
        for k in sorted({e + s for e in edges for s in (-5, 5)}):
            f = minutes(opt_ticker(d, k), d, d)
            C[k] = f.c
        for K in edges:
            lo, hi = C.get(K - 5), C.get(K + 5)
            if lo is None or hi is None or not len(lo) or not len(hi):
                continue
            g = pd.DataFrame({"lo": lo, "hi": hi})
            g = g.reindex(pd.date_range(g.index.min(), g.index.max(), freq="1min")).ffill(limit=2)  # only <= 2-min-old prices
            probs[(d, K)] = ((g.lo - g.hi) / 10).clip(0, 1)
        print(d, len(edges), "edges", flush=True)

    def p_at(d, K, t):
        if K is None or not np.isfinite(K):
            return None
        s = probs.get((d, round(K, 2)))
        if s is None:
            return np.nan
        v = s.asof(t - pd.Timedelta(minutes=1))
        return v

    E["tmin"] = E.t.dt.floor("1min")
    pa = [p_at(d, L, t) if np.isfinite(L) else 1.0 for d, L, t in zip(E.day, E.floor, E.tmin)]
    pb = [p_at(d, U + 1e-4, t) if np.isfinite(U) else 0.0 for d, U, t in zip(E.day, E.cap, E.tmin)]
    E["p_opt_yes"] = np.array(pa, float) - np.array(pb, float)
    E = E[np.isfinite(E.p_opt_yes)].copy()
    E["p"] = np.where(E.taker == "yes", E.p_opt_yes, 1 - E.p_opt_yes).clip(0, 1)
    from backtest import fee_c
    E["fee"] = fee_c(E.px.values, 100)
    E["edge_c"] = 100 * (E.p - E.px) - E.fee
    E["pnl_c"] = 100 * E.won - 100 * E.px - E.fee
    E = E[(E.px > 0) & (E.px < 1)]
    half = pick[len(pick) // 2]
    L = [f"# Kalshi S&P daily ranges vs SPX same-day options ({len(pick)} sampled 2026 days)", "",
         f"Kalshi entries with an options price at the same minute: {len(E)}", "",
         "## Who is more accurate? (Brier, lower is better)", "",
         f"options: {((E.p - E.won) ** 2).mean():.4f}   Kalshi traded price: {((E.px - E.won) ** 2).mean():.4f}", "",
         f"Average gap options minus Kalshi (cents, same side): {100 * (E.p - E.px).mean():.2f}; "
         f"absolute gap median {100 * (E.p - E.px).abs().median():.2f}c, 90th pct {100 * (E.p - E.px).abs().quantile(.9):.2f}c", ""]

    def run(margin, lo, hi, cost=0.0):
        B = E[(E.edge_c - cost > margin) & (E.avail > 0) & (E.day >= lo) & (E.day < hi)].copy()
        B["n"] = np.minimum(B.avail, CAP)
        B["dollars"] = (B.pnl_c - cost) * B.n / 100
        d = B.groupby("day").dollars.sum()
        t = d.mean() / d.std() * np.sqrt(len(d)) if len(d) > 2 and d.std() > 0 else np.nan
        return {"bets": len(B), "c_per_bet": round(B.pnl_c.mean() - cost, 2) if len(B) else np.nan,
                "total_$": round(B.dollars.sum()), "day_t": round(t, 2), "days": B.day.nunique()}

    rows = [{"margin_c": mg, **{f"first_half_{k}": v for k, v in run(mg, pick[0], half).items()}} for mg in (2, 5, 8, 12)]
    R = pd.DataFrame(rows)
    ok = R[R.first_half_bets >= 30]
    best = int(ok.sort_values("first_half_day_t", ascending=False).margin_c.iloc[0]) if len(ok) else 5
    L += ["## Relative value: margin picked on the first half", "", R.to_markdown(index=False), "",
          f"Chosen margin {best}c. Second half (run once): {run(best, half, '9999')}", ""]
    # locked-in version: options legs cost half a spread each; 4 legs over a 10-point package = 4 * half / 10 per $1
    for hs in (0.05, 0.10, 0.15):
        cost = 100 * 4 * hs / 10
        L.append(f"Locked-in arbitrage, option half-spread ${hs:.2f}/leg (= {cost:.0f}c per contract), all days, margin 0: "
                 f"{run(0, pick[0], '9999', cost)}")
    out = "../results/IDX_OPTIONS.md"
    open(out, "w").write("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    main()
