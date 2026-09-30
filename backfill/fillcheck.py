"""Could the model's bets actually have been filled?

For every bet the backtest picked (ppc, 5c margin), look at Kalshi's real trade tape for that bracket from the
quote minute to 2 minutes after it.  A bet counts as fillable if someone actually bought the same side at a price
no worse than ours in that window; the contracts they got show how much size was really there.

  python backfill/fillcheck.py --data out
"""
from __future__ import annotations

import argparse
import os
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

from collect import K, get


def trades(row):
    t0 = int(row.quote_ts) - 60                      # candle end = end of the quote minute
    d = get(f"{K}/markets/trades", ticker=row.ticker, min_ts=t0, max_ts=t0 + 180, limit=1000) or {}
    got = 0.0
    for t in d.get("trades", []):
        side = t.get("taker_side")
        px = float(t.get("yes_price_dollars" if row.side == "yes" else "no_price_dollars") or 1)
        if side == row.side and px <= row.price + 1e-9:
            got += float(t.get("count_fp") or t.get("count") or 0)
    return got


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="out")
    a = ap.parse_args()
    P = pd.read_parquet(os.path.join(a.data, "picks.parquet"))
    P = P[P.quote_ts.notna()].reset_index(drop=True)
    with ThreadPoolExecutor(4) as ex:
        P["filled_contracts"] = list(ex.map(trades, P.itertuples()))
    P.to_parquet(os.path.join(a.data, "picks_filled.parquet"))
    lines = ["", "## Fill check: could the model's bets (5c margin) have been bought?", "",
             "Fillable = someone else really bought the same side at our price or better within 2 minutes.", ""]
    rows = []
    for (series, lag), g in P.groupby(["series", "lag_min"]):
        f = g[g.filled_contracts > 0]
        cap = np.minimum(f.filled_contracts, 100)            # at most what actually traded, 100 max
        rows.append({"series": series, "min_after_open": lag, "bets": len(g), "fillable": len(f),
                     "share_fillable": len(f) / len(g) if len(g) else np.nan,
                     "median_contracts": f.filled_contracts.median() if len(f) else 0,
                     "cents_per_bet_all": g.pnl_c.mean(), "cents_per_bet_fillable": f.pnl_c.mean() if len(f) else np.nan,
                     "dollars_if_filled_at_real_size": float((f.pnl_c * cap).sum() / 100)})
    lines += [pd.DataFrame(rows).round(3).to_markdown(index=False), ""]
    text = "\n".join(lines)
    with open(os.path.join(a.data, "RESULTS.md"), "a") as fh:
        fh.write(text)
    print(text)


if __name__ == "__main__":
    main()
