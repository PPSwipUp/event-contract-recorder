"""Ground-truth check of the liquidity-provider idea from REAL Polymarket makers (public data-api).

1. Maker wallets: wallets on the maker side of recent trades in the paper-LP's 20 markets (trades listed with
   takerOnly=false minus those with takerOnly=true).
2. For each of the top makers: last-30-day REWARD (liquidity rewards) and MAKER_REBATE payouts (activity API), and
   Polymarket's public leaderboard profit and volume for the last month (data-api /v1/leaderboard).
3. Do real makers' rewards + rebates exceed their trading losses?  How big are the winners, and how many are there?
Caveat: payouts and P&L are per wallet across ALL markets, not only these 20.
  python backfill/lpwallets.py
"""
from __future__ import annotations

import collections
import json
import time

import numpy as np
import pandas as pd

from pmtouchdata import jget

DAYS = 30


def makers(cids, top=40):
    c = collections.Counter()
    for cid in cids:
        a = jget("https://data-api.polymarket.com/trades", market=cid, limit=1000, takerOnly="false") or []
        b = jget("https://data-api.polymarket.com/trades", market=cid, limit=1000, takerOnly="true") or []
        taker = {t["transactionHash"] + t["proxyWallet"] for t in b}
        c.update(t["proxyWallet"] for t in a if t["transactionHash"] + t["proxyWallet"] not in taker)
    return [w for w, _ in c.most_common(top)]


def payouts(w, typ, since):
    out, off = 0.0, 0
    while off < 3000:
        j = jget("https://data-api.polymarket.com/activity", user=w, type=typ, limit=500, offset=off) or []
        rec = [x for x in j if x.get("timestamp", 0) >= since]
        out += sum(float(x.get("usdcSize") or 0) for x in rec)
        if len(j) < 500 or len(rec) < len(j):
            return out
        off += 500
    return out


def leaderboard(w):
    """Polymarket leaderboard: last-month profit and volume for one wallet"""
    try:
        j = jget("https://data-api.polymarket.com/v1/leaderboard", user=w, timePeriod="month")
    except RuntimeError:
        return np.nan, np.nan
    return (float(j[0]["pnl"]), float(j[0]["vol"])) if isinstance(j, list) and j else (np.nan, np.nan)


def main():
    st = json.load(open("../live/pmlp_state.json"))
    W = makers([m["cid"] for m in st["markets"]])
    since = int(time.time()) - DAYS * 86400
    rows = []
    for w in W:
        rw, rb = payouts(w, "REWARD", since), payouts(w, "MAKER_REBATE", since)
        lb, vol = leaderboard(w)
        rows.append({"wallet": w[:10], "rewards_30d": round(rw, 2), "rebates_30d": round(rb, 2),
                     "lb_profit_1m": round(lb, 2), "volume_1m": round(vol)})
        print(rows[-1], flush=True)
    R = pd.DataFrame(rows)
    R["income_30d"] = R.rewards_30d + R.rebates_30d
    L = [f"# Real Polymarket makers in the paper-LP markets: rewards vs trading P&L (top {len(R)} maker wallets)", "",
         "Per wallet across ALL its markets. lb_profit_1m = Polymarket leaderboard profit, last month (includes rewards? "
         "unknown - shown for comparison).", "", R.sort_values("income_30d", ascending=False).to_markdown(index=False), "",
         f"Wallets with rewards+rebates > $100/30d: {(R.income_30d > 100).sum()}; of those, leaderboard profit > 0: "
         f"{((R.income_30d > 100) & (R.lb_profit_1m > 0)).sum()}", ""]
    open("../results/LP_WALLETS.md", "w").write("\n".join(L))
    print("\n".join(L[-2:]))


if __name__ == "__main__":
    main()
