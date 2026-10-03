""""Ladder at creation": post orders on every price level near the opening price the moment a Polymarket market is
listed, so each order is FIRST in its queue.  Replay on markets from the 60-day LP replay cache that were LISTED
inside the window (first price point > 2 days after the window start).

Ladder: K levels each side of the first midpoint, on the tick grid; bids below it, asks above it, `size` shares each.
Queue: an order is at the FRONT of its level until it fills (any taker print at or through its price fills it);
after a fill it is re-posted at the same price on whichever side is valid, at the BACK (only prints strictly
through fill it).  Inventory marked to the midpoint at the end.  Rewards are counted for levels within the max
spread v of the current midpoint, scored as in the LP replay, with competition = the live book now (optimistic for
a new market, so this is an upper bound on rewards).
  python backfill/pmladder.py --levels 5 --size 100
"""
from __future__ import annotations

import argparse
import json
import math
import os

import numpy as np
import pandas as pd

D = "data_local/pmlpreplay"


def run(m, mids, T, K, size):
    tick = m["tick"]
    mid0 = mids.iloc[0]
    base = round(round(mid0 / tick) * tick, 4)
    levels = {}
    for k in range(1, K + 1):
        for px in (round(base - k * tick, 4), round(base + k * tick, 4)):
            if 0 < px < 1:
                levels[px] = {"side": "bid" if px < mid0 else "ask", "front": True}
    inv = cash = 0.0
    fills = front_fills = 0
    ti, ts = 0, mids.index.values
    for i in range(1, len(ts)):
        t0, t1, mid = ts[i - 1], ts[i], mids.iloc[i - 1]
        for px, o in levels.items():                         # re-post filled orders on the valid side
            if o["side"] is None:
                o["side"] = "bid" if px < mid else ("ask" if px > mid else None)
        while ti < len(T) and T[ti][0] < t0:
            ti += 1
        j = ti
        while j < len(T) and T[j][0] < t1:
            _, tpx, bought_yes, _ = T[j]
            for px, o in levels.items():
                if o["side"] == "bid" and not bought_yes and (tpx < px - 1e-9 or (o["front"] and tpx <= px + 1e-9)):
                    inv += size; cash -= size * px
                elif o["side"] == "ask" and bought_yes and (tpx > px + 1e-9 or (o["front"] and tpx >= px - 1e-9)):
                    inv -= size; cash += size * px
                else:
                    continue
                fills += 1; front_fills += o["front"]
                o["side"], o["front"] = None, False
            j += 1
    days = max(1, (ts[-1] - ts[0]) / 86400)
    return {"market": m["question"][:40], "days": round(days, 1), "fills": fills, "front_fills": front_fills,
            "fill_pnl_$": round(cash + inv * mids.iloc[-1], 2), "fill_pnl_day_$": round((cash + inv * mids.iloc[-1]) / days, 2),
            "end_inventory": inv, "capital_$": round(sum(px if o["side"] != "ask" else 1 - px for px, o in levels.items()) * size)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--levels", type=int, default=5)
    ap.add_argument("--size", type=float, default=100)
    a = ap.parse_args()
    st = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "live", "pmlp_state.json")))
    rows = []
    for m in st["markets"]:
        p = f"{D}/{m['cid'][:12]}.json"
        if not os.path.exists(p):
            continue
        x = json.load(open(p))
        mids = pd.Series(x["mids"]).rename(index=int).sort_index()
        T = [tuple(t) for t in x["trades"]]
        if len(mids) < 600 or not T:
            continue
        listed_in_window = mids.index[0] > T[0][0] - 3600 and (mids.index[-1] - mids.index[0]) < 58 * 86400
        r = run(m, mids, T, a.levels, a.size)
        rw = os.path.join(D, f"reward_{m['cid'][:12]}_touch.json")
        r["reward_day_upper_$"] = round(json.load(open(rw)) * a.size / 500, 2) if os.path.exists(rw) else np.nan
        r["new_listing"] = bool(listed_in_window)
        rows.append(r)
    R = pd.DataFrame(rows).sort_values("fill_pnl_day_$")
    R["net_day_upper_$"] = R["fill_pnl_day_$"] + R["reward_day_upper_$"].fillna(0)
    L = [f"# Ladder at creation: {a.levels} levels each side, {a.size:.0f} shares, front of queue until first fill", "",
         R.to_markdown(index=False), "",
         f"All markets: fill P&L ${R['fill_pnl_day_$'].sum():.2f}/day, rewards (upper bound) ${R['reward_day_upper_$'].sum():.2f}/day, "
         f"net ${R['net_day_upper_$'].sum():.2f}/day; front-of-queue fills {R.front_fills.sum()} of {R.fills.sum()}",
         f"New listings only ({R.new_listing.sum()}): net ${R[R.new_listing]['net_day_upper_$'].sum():.2f}/day", ""]
    open("../results/PM_LADDER.md", "w").write("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    main()
