"""Equity curve: lower-drawdown range bot vs current bot, Nov 2024 - Sep 2026 (28 Sep excluded).  Runs on a laptop.
  python backfill/equity.py --chunks data_local/chunks --out ../results/equity.png
"""
from __future__ import annotations

import argparse

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.rcParams["text.parse_math"] = False             # plain "$" in labels
import pandas as pd

from improve import HOLD, PAIRS, load, run

BOTS = {"Current bot (no controls)": (0, 100, 0, 0, 0, 5),
        "New rules (>12c edge, max 25, crowd 200, calm 2, stop $200)": (0, 25, 200, 2.0, 200, 12)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", default="data_local/chunks")
    ap.add_argument("--out", default="../results/equity.png")
    a = ap.parse_args()
    C = pd.concat([load(s, p, a.chunks) for s, p in PAIRS.items()], ignore_index=True)
    days = pd.date_range(C.day.min(), C.day.max(), freq="D")
    fig, ax = plt.subplots(figsize=(11, 5.5))
    curves = {}
    for name, g in BOTS.items():
        D = run(C, *g)
        eq = D.groupby(pd.to_datetime(D.day)).dollars.sum().reindex(days, fill_value=0).cumsum()
        curves[name] = eq
        ax.plot(eq.index, eq.values, label=f"{name}: ${eq.iloc[-1]:,.0f}, max DD ${(eq.cummax() - eq).max():,.0f}")
    ax.axvline(pd.Timestamp(HOLD[0]), color="grey", ls="--")
    ax.text(pd.Timestamp(HOLD[0]), ax.get_ylim()[1] * 0.95, "  holdout (rules never saw this) ->", color="grey")
    ax.axhline(0, color="black", lw=0.5)
    ax.set_title("Kalshi BTC + ETH hourly ranges: cumulative profit ($), volume-capped, after fees")
    ax.set_ylabel("cumulative profit ($)")
    ax.legend(loc="upper left")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(a.out, dpi=130)
    pd.DataFrame(curves).to_csv(a.out.replace(".png", ".csv"))
    print({k: round(v.iloc[-1], 2) for k, v in curves.items()})


if __name__ == "__main__":
    main()
