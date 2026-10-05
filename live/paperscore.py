"""Score the paper market-maker's fills (papermaker.jsonl) once their markets have settled.  Read-only.
  python live/paperscore.py
"""
import json
import math
import os

import pandas as pd
import requests

K = "https://api.elections.kalshi.com/trade-api/v2"
HERE = os.path.dirname(os.path.abspath(__file__))

if __name__ == "__main__":
    F = pd.DataFrame([json.loads(l) for l in open(os.path.join(HERE, "papermaker.jsonl"))])
    res = {}
    for tk in F.ticker.unique():
        m = requests.get(f"{K}/markets/{tk}", timeout=20).json().get("market", {})
        res[tk] = m.get("result")
    F["result"] = F.ticker.map(res)
    F = F[F.result.isin(["yes", "no"])].copy()
    F["our_px"] = F.apply(lambda r: r.yes_px if r.we_hold == "yes" else 1 - r.yes_px, axis=1)
    F["fee_c"] = [math.ceil(1.75 * n * p * (1 - p)) / n for p, n in zip(F.our_px, F.n.clip(lower=1))]
    F["won"] = (F.we_hold == F.result).astype(float)
    F["pnl_$"] = (100 * F.won - 100 * F.our_px - F.fee_c) * F.n / 100
    if "n_big" in F:                                          # same fills with a 100-contract cap
        F["n_big"] = F.n_big.fillna(F.n)
        F["pnl_big_$"] = (100 * F.won - 100 * F.our_px - F.fee_c) * F.n_big / 100
        print(f"100-contract cap: contracts {F.n_big.sum():.0f}, pnl ${F['pnl_big_$'].sum():.2f}")
    F["model_edge_c"] = [100 * ((p if h == "yes" else 1 - p) - o) for p, h, o in zip(F.p_yes, F.we_hold, F.our_px)]
    F["tested_window"] = F.mins_in.between(10, 21)
    F["hour"] = F.t.str[:13]
    print(f"settled fills {len(F)}, contracts {F.n.sum():.0f}, hours {F.hour.nunique()}")
    print(F.groupby("tested_window").agg(fills=("n", "size"), contracts=("n", "sum"), pnl=("pnl_$", "sum"),
                                         model_edge_c=("model_edge_c", "mean")).round(2).to_string())
    h = F.groupby("hour")["pnl_$"].sum()
    print(f"total ${F['pnl_$'].sum():.2f}  per hour ${h.sum() / max(1, len(h)):.2f}  "
          f"hour-level t {h.mean() / h.std() * len(h) ** .5 if len(h) > 2 and h.std() > 0 else float('nan'):.2f}")
