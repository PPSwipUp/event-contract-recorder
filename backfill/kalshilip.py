"""Kalshi Liquidity Incentive Program: what would resting X contracts per side earn, given the competing book now?

Rules (help.kalshi.com 'Liquidity Incentive Program'): a snapshot each second; per side (yes bids, no bids) walk
down from the best bid until cumulative size reaches Target/5 -> Reference Price; orders count until cumulative size
reaches the Target; each counted order scores Discount^N x size, N = ticks below the Reference Price (0 at or
better).  The period reward is split by score.  Our quote: X contracts at each side's best bid (joining the queue).
One snapshot treated as typical for the period (an assumption).  Rewards only; fills / adverse selection NOT
included - this ranks where the money is, it is not a profit estimate.
  python backfill/kalshilip.py --size 100
"""
from __future__ import annotations

import argparse
import sys
import os

import numpy as np
import pandas as pd
import requests

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "live"))
import dohfix  # noqa: F401,E402
from arbscan import kget  # noqa: E402


def programs():
    rows, cur = [], None
    while True:
        p = {"status": "active", "limit": 1000}
        if cur:
            p["cursor"] = cur
        d = kget("/incentive_programs", **p)
        rows += d.get("incentive_programs", [])
        cur = d.get("next_cursor") or d.get("cursor")
        if not cur or not d.get("incentive_programs"):
            return pd.DataFrame(rows)


def side_score(levels, target, disc, ours, back=True):
    """levels: [(price, size)] bids best first; returns (competitors' score, our score) with our order joined at the
    best bid.  back=True: time priority, our order counts only after everyone already at that price (realistic);
    back=False: our order counted first (optimistic upper bound)."""
    if not levels:
        return 0.0, float(ours)                                       # empty side: our order is the whole book
    if back:
        lv = [(levels[0][0], levels[0][1], False), (levels[0][0], ours, True)] + [(p, q, False) for p, q in levels[1:]]
    else:
        lv = [(levels[0][0], levels[0][1] + ours, True)] + [(p, q, False) for p, q in levels[1:]]
    cum, ref = 0.0, lv[-1][0]
    for p, q, _ in lv:
        cum += q
        if cum >= target / 5:
            ref = p
            break
    comp = mine = 0.0
    cum = 0.0
    for p, q, has_ours in lv:
        if cum >= target:
            break
        take = min(q, target - cum)
        cum += take
        n = max(0, round((ref - p) * 100))
        w = disc ** n
        if has_ours and back:
            mine += w * take
        elif has_ours:
            mine += w * min(ours, take)
            comp += w * max(0.0, take - ours)
        else:
            comp += w * take
    return comp, mine


def market_share(book, target, disc, ours):
    """our share of one snapshot, or None if Kalshi would exclude it (either side's depth incl. ours < target)"""
    if any(sum(q for _, q in lv) + ours < target for lv in book):
        return None
    comp = mine = 0.0
    for lv in book:
        c, m = side_score(lv, target, disc, ours)
        comp += c
        mine += m
    return mine / (mine + comp) if mine + comp > 0 else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", type=float, default=100)
    a = ap.parse_args()
    P = programs()
    P["hours"] = (pd.to_datetime(P.end_date, format="ISO8601") - pd.to_datetime(P.start_date, format="ISO8601")).dt.total_seconds() / 3600
    P["reward_usd"] = P.period_reward / 10000
    P["target"] = pd.to_numeric(P.target_size_fp)
    P["disc"] = P.discount_factor_bps.fillna(10000) / 10000
    books = {}
    tick = P.market_ticker.unique().tolist()
    for j in range(0, len(tick), 100):
        d = kget("/markets/orderbooks", tickers=tick[j:j + 100])
        for ob in d.get("orderbooks", []):
            b = ob["orderbook_fp"]
            books[ob["ticker"]] = [sorted(((float(p), float(q)) for p, q in b.get(s) or []), reverse=True) for s in ("yes_dollars", "no_dollars")]
    rows = []
    for r in P.to_dict("records"):
        bk = books.get(r["market_ticker"])
        if not bk:
            continue
        comp = mine = 0.0
        for levels in bk:
            c, m = side_score(levels, r["target"], r["disc"], a.size)
            comp += c
            mine += m
        share = mine / (mine + comp) if mine + comp > 0 else 0
        rows.append({"market": r["market_ticker"], "series": r["market_ticker"].split("-")[0], "reward_usd": r["reward_usd"],
                     "hours": round(r["hours"], 2), "target": r["target"], "disc": r["disc"], "share": round(share, 3),
                     "our_usd_per_hour": round(share * r["reward_usd"] / max(r["hours"], 0.01), 2)})
    R = pd.DataFrame(rows).sort_values("our_usd_per_hour", ascending=False)
    g = R.groupby("series").agg(markets=("market", "size"), reward_per_h=("our_usd_per_hour", "sum"), med_share=("share", "median")).sort_values("reward_per_h", ascending=False)
    L = [f"# Kalshi liquidity incentives: reward share for {a.size:.0f} contracts per side at the best bid (snapshot)", "",
         f"Active programs priced: {len(R)}; sum of our $/hour if quoting ALL of them: {R.our_usd_per_hour.sum():.0f} "
         "(rewards only, before any fill losses; capital ~ size x markets)", "",
         "## Top series", "", g.head(15).round(2).to_markdown(), "", "## Top markets", "", R.head(15).to_markdown(index=False), ""]
    open("../results/KALSHI_LIP.md", "w").write("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    main()
