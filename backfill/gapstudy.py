"""'Be first at a fresh price level': when a Polymarket spread opens to 2+ ticks, post the improving order (alone at
the new level, so first in its queue) and measure what happens after it fills.

Data: live/pmgap.jsonl (best bid/ask every ~3 s, 40 markets) + every real taker trade (data-api, 1-s timestamps).
Event: a snapshot with spread >= 2 ticks.  Our orders: bid at best bid + 1 tick and ask at best ask - 1 tick, 100
shares each, live until the next snapshot.  Being alone at the level, ANY taker print at or through our price fills
us (front of queue is the point of the idea).
Mark-out: mid 1, 5 and 30 minutes after the fill minus our price (buys; reversed for sells), in cents per share.
Positive mark-out = the fill was worth having; negative = we were picked off.  Rewards are not included.
  python backfill/gapstudy.py
"""
from __future__ import annotations

import os
import sys
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "live"))
from pmlpreplay import trades  # noqa: E402
from pmtouchdata import jget  # noqa: E402

SIZE = 100


def full_cids(prefixes):
    """the recorder stored 12-char condition-id prefixes; recover full ids from the reward list"""
    out, cur = {}, ""
    while True:
        r = jget("https://clob.polymarket.com/rewards/markets/current", **({"next_cursor": cur} if cur else {}))
        for x in r.get("data", []):
            if x["condition_id"][:12] in prefixes:
                out[x["condition_id"][:12]] = x["condition_id"]
        cur = r.get("next_cursor")
        if not cur or cur == "LTE=" or not r.get("data"):
            return out


def main():
    G = pd.read_json("../live/pmgap.jsonl", lines=True)
    G["bid"], G["ask"] = G.b1.str[0], G.a1.str[0]
    G["mid"] = (G.bid + G.ask) / 2
    G = G.sort_values(["cid", "t"])
    ids = full_cids(set(G.cid))
    since = int(G.t.min())
    cids = [c for c in G.cid.unique() if c in ids]
    with ThreadPoolExecutor(6) as ex:
        TR = dict(zip(cids, ex.map(lambda c: [t for t in trades(ids[c], since)], cids)))
    rows = []
    for c in cids:
        g = G[G.cid == c].reset_index(drop=True)
        tr = np.array([(t[0], t[1], t[2]) for t in TR[c]], dtype=float) if TR[c] else np.zeros((0, 3))
        ts, mids = g.t.values, g.mid.values
        for i in range(len(g) - 1):
            r = g.iloc[i]
            if r.spread_ticks < 2:
                continue
            our_bid, our_ask = round(r.bid + r.tick, 4), round(r.ask - r.tick, 4)
            win = tr[(tr[:, 0] >= ts[i]) & (tr[:, 0] < ts[i + 1])] if len(tr) else tr
            for t0, px, bought_yes in win:
                for side, price, hit in (("buy", our_bid, (not bought_yes) and px <= our_bid + 1e-9),
                                         ("sell", our_ask, bought_yes and px >= our_ask - 1e-9)):
                    if not hit:
                        continue
                    mk = {}
                    for m in (1, 5, 30):
                        j = np.searchsorted(ts, t0 + 60 * m)
                        if j < len(ts):
                            mk[f"mk{m}_c"] = 100 * ((mids[j] - price) if side == "buy" else (price - mids[j]))
                    rows.append({"cid": c, "t": t0, "side": side, "price": price, "spread_ticks": r.spread_ticks, **mk})
    F = pd.DataFrame(rows).drop_duplicates(["cid", "t", "side"])
    hours = (G.t.max() - G.t.min()) / 3600
    gaps = (G.spread_ticks >= 2).mean()
    L = [f"# Fresh-price-level study ({len(cids)} markets, {hours:.1f} h of 3-s books incl. curfew gaps)", "",
         f"Snapshots with spread >= 2 ticks: {100 * gaps:.1f}%; fills on our improving orders: {len(F)}", ""]
    if len(F):
        L += ["Mark-out per share (cents; positive = good fill):", "",
              F[[c for c in ("mk1_c", "mk5_c", "mk30_c") if c in F]].describe().round(2).to_markdown(), "",
              f"$ at {SIZE} shares per fill, 5-min mark-out: {(F.get('mk5_c', pd.Series(dtype=float)).sum() * SIZE / 100):.2f}", "",
              "by spread width:", "", F.groupby(pd.cut(F.spread_ticks, [1, 2, 4, 10, 1000])).agg(
                  n=("side", "size"), mk5=("mk5_c", "mean")).round(2).to_markdown(), ""]
    open("../results/GAP_STUDY.md", "w").write("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    main()
