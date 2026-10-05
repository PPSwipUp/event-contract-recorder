"""How much can the lower-drawdown range bot make if it takes ALL the volume others traded at its price?
Same rules (>12c edge, crowd 200, calm 2, $200 daily stop), contract cap varied.  Caches the bet table.
  python backfill/capacity.py --chunks data_local/chunks
"""
from __future__ import annotations

import argparse
import os

import pandas as pd

from improve import HOLD, PAIRS, TRAIN, load, run, score


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", default="data_local/chunks")
    ap.add_argument("--cache", default="data_local/bets_all.parquet")
    a = ap.parse_args()
    if os.path.exists(a.cache):
        C = pd.read_parquet(a.cache)
    else:
        C = pd.concat([load(s, p, a.chunks) for s, p in PAIRS.items()], ignore_index=True)
        C.to_parquet(a.cache)
    rows = []
    for size in (25, 50, 100, 250, 1000, 10 ** 9):
        for stop in (200, 0):
            D = run(C, 0, size, 200, 2.0, stop, 12)
            for name, (s, e) in (("train", TRAIN), ("holdout", HOLD)):
                r = score(D, s, e)
                rows.append({"max_contracts": "no cap" if size > 1e6 else size, "daily_stop": stop or "none", "period": name,
                             "bets": r["bets"], "total_$": round(r["total_$"]), "per_month_$": round(r["per_month_$"]),
                             "max_dd_$": round(r["max_dd_$"]), "sharpe": round(r["sharpe"], 2),
                             "avg_contracts": round(D[(D.day >= s) & (D.day < e)].n.mean(), 1)})
    print(pd.DataFrame(rows).to_markdown(index=False))
    D = run(C, 0, 10 ** 9, 200, 2.0, 0, 12)
    print("\nfillable contracts per bet (no cap):", D.n.describe().round(1).to_dict())


if __name__ == "__main__":
    main()
