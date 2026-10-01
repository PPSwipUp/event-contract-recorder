"""Where does the range bot's edge come from, and does it behave like a real edge?  (runs fine on a laptop)

Uses the base bot (fixed scale, > 5c edge, sized to the volume others traded at our price, max 100).
  python backfill/diagnose.py --chunks data_local/chunks --out ../results/DIAGNOSE.md
"""
from __future__ import annotations

import argparse
import os

import numpy as np
import pandas as pd

from improve import PAIRS, load, run


def table(D, key, label):
    g = D.groupby(key, observed=True)
    R = pd.DataFrame({"bets": g.size(), "win_rate": g.won.mean(), "avg_edge_predicted_c": g.edge_c.mean(),
                      "avg_profit_c": g.pnl_c.mean(), "total_$": g.dollars.sum()})
    return [f"### {label}", "", R.round(3).to_markdown(), ""]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", default="data_local/chunks")
    ap.add_argument("--out", default="../results/DIAGNOSE.md")
    a = ap.parse_args()
    C = pd.concat([load(s, p, a.chunks) for s, p in PAIRS.items()], ignore_index=True)
    D = run(C, 0, 100, 0, 0, 0, 5)
    D["hour_utc"] = pd.to_datetime(D.t).dt.hour
    D["price_band"] = pd.cut(D.px, [0, .15, .5, .85, 1.0], labels=["<15c", "15-50c", "50-85c", ">85c"])
    D["edge_band"] = pd.cut(D.edge_c, [5, 8, 12, 20, 100], labels=["5-8c", "8-12c", "12-20c", ">20c"])
    D["hours"] = pd.cut(D.hour_utc, [-1, 5, 11, 17, 23], labels=["00-05", "06-11", "12-17", "18-23"])
    L = ["# Diagnosing the range bot (BTC + ETH hourly ranges, Nov 2024 - Sep 2026, 28 Sep excluded)", "",
         f"{len(D)} bets, total ${D.dollars.sum():.0f}.", "",
         "A real edge should make MORE money where the model predicts a BIGGER edge (first table).", ""]
    L += table(D, "edge_band", "By predicted edge")
    L += table(D, "price_band", "By contract price")
    L += table(D, "side", "By side")
    L += table(D, "series", "By market")
    L += table(D, "hours", "By time of day (UTC)")
    m = D.groupby(D.day.str[:7]).dollars.sum()
    loo = {k: m.drop(k).sum() for k in m.index}
    L += ["### Remove one month at a time", "",
          f"Total with each month removed: min ${min(loo.values()):.0f}, max ${max(loo.values()):.0f} "
          f"(removing {min(loo, key=loo.get)} hurts most). Months positive: {(m > 0).sum()}/{len(m)}.", ""]
    D["model_p"] = (D.edge_c + D.cost_c) / 100                 # edge = 100*p - cost, so p = (edge + cost) / 100
    cal = D.groupby(pd.cut(D.model_p, [0, .1, .3, .5, .7, .9, 1.01]), observed=True).agg(
        bets=("won", "size"), model_says=("model_p", "mean"), price_paid=("px", "mean"), actually_won=("won", "mean"))
    L += ["### Calibration of the bets taken (does the model's probability match reality?)", "", cal.round(3).to_markdown(), ""]
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    open(a.out, "w").write("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    main()
