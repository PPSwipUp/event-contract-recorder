"""Combine the monthly backtest chunks: month-by-month results, how concentrated the profit is in a few days,
and how fast you would have had to be.

  python backfill/aggregate.py --chunks chunks --out results/MONTHLY.md
(chunks/<name>/picks_filled.parquet from each monthly job)
"""
from __future__ import annotations

import argparse
import glob
import os

import numpy as np
import pandas as pd

AFTER = (5, 15, 30, 60)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", default="chunks")
    ap.add_argument("--out", default="results/MONTHLY.md")
    ap.add_argument("--latency", default="")
    a = ap.parse_args()
    parts = [pd.read_parquet(f) for f in sorted(glob.glob(os.path.join(a.chunks, "*", "picks_filled.parquet")))]
    P = pd.concat(parts, ignore_index=True)
    P["close"] = pd.to_datetime(P.close, utc=True)
    P["month"] = P.close.dt.strftime("%Y-%m")
    P["day"] = P.close.dt.strftime("%Y-%m-%d")
    P["fillable"] = P.filled_contracts > 0
    P["dollars"] = np.where(P.fillable, P.pnl_c * np.minimum(P.filled_contracts, 100) / 100, 0.0)
    L = ["# Monthly backtest: volatility model vs Kalshi hourly ranges (bets at a 5c margin, <=100 contracts)", ""]

    rows = []
    for (series, lag, month), g in P.groupby(["series", "lag_min", "month"]):
        rows.append({"series": series, "min_after_open": lag, "month": month, "bets": len(g),
                     "cents_per_bet": g.pnl_c.mean(), "se": g.pnl_c.std() / np.sqrt(len(g)) if len(g) > 1 else np.nan,
                     "share_fillable": g.fillable.mean(), "dollars_at_real_size": g.dollars.sum()})
    M = pd.DataFrame(rows)
    L += ["## Month by month", "", M.round(2).to_markdown(index=False), ""]

    L += ["## Totals and concentration", ""]
    rows = []
    for (series, lag), g in P.groupby(["series", "lag_min"]):
        d = g.groupby("day").dollars.sum().sort_values(ascending=False)
        tot = d.sum()
        rows.append({"series": series, "min_after_open": lag, "bets": len(g), "cents_per_bet": g.pnl_c.mean(),
                     "t_stat": g.pnl_c.mean() / (g.pnl_c.std() / np.sqrt(len(g))) if len(g) > 1 else np.nan,
                     "dollars_total": tot, "days_with_bets": len(d),
                     "share_of_profit_from_top_5_days": d.head(5).sum() / tot if tot > 0 else np.nan,
                     "dollars_without_top_5_days": d.iloc[5:].sum(), "months_positive": int((M[(M.series == series) & (M.min_after_open == lag)].cents_per_bet > 0).sum()),
                     "months": int(((M.series == series) & (M.min_after_open == lag)).sum())})
    L += [pd.DataFrame(rows).round(3).to_markdown(index=False), ""]

    L += ["## How fast would you have needed to be? (bets 1 min after open)", "",
          "Share of bets where others were still buying at our price or better N seconds after the market opened.", ""]
    rows = []
    for series, g in P[P.lag_min == 1].groupby("series"):
        if not len(g):
            continue
        r = {"series": series, "bets": len(g), "bets_with_trade_data": int((g.tape_trades > 0).sum())}
        for s in AFTER:
            c = f"avail_after_{s}s"
            if c in g:
                r[f"after_{s}s"] = (g[c] > 0).mean()
                r[f"median_contracts_after_{s}s"] = g.loc[g[c] > 0, c].median() if (g[c] > 0).any() else 0
        rows.append(r)
    if rows:
        L += [pd.DataFrame(rows).round(3).to_markdown(index=False), ""]
    if a.latency and os.path.exists(a.latency):
        L += ["## Network latency to Kalshi from a GitHub (Azure, US) runner", "", "```", open(a.latency).read().strip(), "```", ""]
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    open(a.out, "w").write("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    main()
