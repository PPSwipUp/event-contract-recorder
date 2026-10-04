"""Does re-quoting faster rescue the Polymarket liquidity provider?  Replay on the 3-second top-of-book recording
(live/pmgap.jsonl, 40 markets) against every real taker trade in the same hours.

Quotes: join the best bid and best ask (front-of-book prices; size 500 shares), refreshed every R seconds from the
recorded book (R = 3, 15, 60).  Fills: only taker prints strictly THROUGH our price (back of queue, as in the
validated replay).  A filled side re-quotes at the next refresh; inventory capped at 2x size; marked to the last
recorded mid.  Rewards are left out (identical across R); the question is only how much fill loss speed removes.
  python backfill/lpspeed.py
"""
from __future__ import annotations

import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "live"))
from pmlpreplay import trades  # noqa: E402

SIZE = 500


def replay(B, T, every):
    t0 = B.t.iloc[0]
    snap = B[((B.t - t0) // every).diff().fillna(1) != 0]            # one book snapshot per refresh interval
    inv = cash = 0.0
    fills, ti = 0, 0
    ts = snap.t.values
    for i in range(len(snap) - 1):
        r = snap.iloc[i]
        bid, ask = r.b1, r.a1
        bid_on, ask_on = inv < 2 * SIZE, inv > -2 * SIZE
        while ti < len(T) and T[ti][0] < ts[i]:
            ti += 1
        j = ti
        while j < len(T) and T[j][0] < ts[i + 1]:
            _, px, bought_yes, _ = T[j]
            if bid_on and not bought_yes and px < bid - 1e-9:
                inv += SIZE; cash -= SIZE * bid; fills += 1; bid_on = False
            if ask_on and bought_yes and px > ask + 1e-9:
                inv -= SIZE; cash += SIZE * ask; fills += 1; ask_on = False
            j += 1
    mid = (B.b1.iloc[-1] + B.a1.iloc[-1]) / 2
    return fills, cash + inv * mid


def main():
    G = pd.read_json("../live/pmgap.jsonl", lines=True)
    G["b1"] = G.b1.str[0]
    G["a1"] = G.a1.str[0]
    hours = (G.t.max() - G.t.min()) / 3600
    st = json.load(open("../live/pmlp_state.json"))
    full = {m["cid"][:12]: m["cid"] for m in st["markets"]}
    extra = json.load(open("../live/pmgap_markets.json")) if os.path.exists("../live/pmgap_markets.json") else {}
    full.update(extra)
    since = int(G.t.min())
    cids = [c for c in G.cid.unique() if c in full]
    with ThreadPoolExecutor(6) as ex:
        TR = dict(zip(cids, ex.map(lambda c: trades(full[c], since), cids)))
    rows = []
    for c in cids:
        B = G[G.cid == c].sort_values("t")
        T = [t for t in TR[c] if t[0] >= since]
        for every in (3, 15, 60):
            f, pnl = replay(B, T, every)
            rows.append({"market": c, "refresh_s": every, "trades": len(T), "fills": f, "fill_pnl_$": round(pnl, 2)})
    R = pd.DataFrame(rows)
    tot = R.groupby("refresh_s").agg(markets=("market", "nunique"), fills=("fills", "sum"), fill_pnl=("fill_pnl_$", "sum"))
    tot["per_day_$"] = (tot.fill_pnl / hours * 24).round(2)
    L = [f"# Does faster re-quoting rescue the liquidity provider? ({hours:.1f} h of 3-s books, {len(cids)} markets)", "",
         "Join best bid/ask, 500 shares, back-of-queue fills, rewards excluded.", "", tot.round(2).to_markdown(), "",
         R.pivot(index="market", columns="refresh_s", values="fill_pnl_$").round(2).to_markdown(), ""]
    open("../results/LP_SPEED.md", "w").write("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    main()
