"""Adverse selection: can order flow BEFORE our entry warn us off the bets that lose (the big-volume ones)?

Uses the cached bet table (capacity.py) and the database trades.  Features, all known at the moment of entry:
  entry_size   size of the real trade that showed us the price
  opp_before   contracts bought on the OTHER side of the same bracket earlier in the window
  ev_before    contracts traded in the whole hourly event earlier in the window (how busy / informed the hour is)
  drift_c      how far our side's price moved since the bracket's first trade (positive = moved our way)
Pre-declared: look at TRAIN only (2024-11..2025-12) for the new-rules bets with NO size cap; pick at most one simple
skip rule there; run it once on HOLDOUT (2026-01..09) at several size caps.
  python backfill/adverse.py
"""
from __future__ import annotations

import glob

import numpy as np
import pandas as pd

from improve import HOLD, TRAIN, run, score

if __name__ == "__main__":
    C = pd.read_parquet("data_local/bets_all.parquet")
    T = pd.concat([pd.read_parquet(f) for f in sorted(glob.glob("data_local/chunks/db-*/trades.parquet"))], ignore_index=True)
    T["t"] = pd.to_datetime(T.ts, utc=True, format="ISO8601")
    T["px_side"] = np.where(T.taker == "yes", T.yes, T.no)
    # match each bet to the trade it came from -> ticker
    key = T[["event", "ticker", "taker", "t", "px_side"]].rename(columns={"taker": "side"})
    C = C.merge(key, on=["event", "side", "t"], how="left")
    C = C[np.isclose(C.px_side, C.px)].drop_duplicates(["event", "side", "t", "edge_c"])
    first = T.sort_values("t").groupby("ticker").agg(first_yes=("yes", "first"))
    C = C.join(first, on="ticker")
    C["drift_c"] = 100 * np.where(C.side == "yes", C.first_yes - C.px, C.px - (1 - C.first_yes))   # + = cheaper now
    Tt = T[["ticker", "event", "taker", "t", "count"]]
    J = C[["ticker", "side", "t"]].reset_index().merge(Tt, on="ticker", suffixes=("", "_o"))
    C["opp_before"] = J[(J.t_o < J.t) & (J.taker != J.side)].groupby("index")["count"].sum().reindex(C.index).fillna(0)
    J = C[["event", "t"]].reset_index().merge(Tt[["event", "t", "count"]], on="event", suffixes=("", "_o"))
    C["ev_before"] = J[J.t_o < J.t].groupby("index")["count"].sum().reindex(C.index).fillna(0)
    print("bets matched:", len(C))

    D = run(C, 0, 10 ** 9, 200, 2.0, 0, 12)                      # new rules, no size cap
    D["per_contract_c"] = D.pnl_c
    tr = D[(D.day >= TRAIN[0]) & (D.day < TRAIN[1])]
    L = ["# Order flow before entry vs results (TRAIN only, new rules, no size cap)", ""]
    for f, bins in (("entry_size", [0, 5, 25, 100, 1e9]), ("opp_before", [-1, 0, 25, 200, 1e9]),
                    ("ev_before", [-1, 100, 1000, 5000, 1e9]), ("drift_c", [-100, -2, 0, 2, 100]),
                    ("avail", [0, 10, 50, 200, 1e9])):
        g = tr.groupby(pd.cut(tr[f], bins), observed=True)
        L += [f"### {f}", "", pd.DataFrame({"bets": g.size(), "c_per_contract": g.pnl_c.mean().round(2),
                                             "$_uncapped": g.dollars.sum().round(0), "avg_size": g.n.mean().round(0)}).to_markdown(), ""]
    print("\n".join(L))
    C.to_parquet("data_local/bets_features.parquet")
