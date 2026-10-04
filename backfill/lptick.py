"""Loss-versus-speed curve for the Polymarket liquidity provider, on the tick recording (live/pmtick/*.jsonl).

From the stream: best bid/ask after every book change (price_change carries best_bid/best_ask; book snapshots give
the full ladder) and every trade with millisecond timestamps (last_trade_price; NO-token trades are converted to
the YES side).  For reaction delay D (100 ms .. 60 s): our quotes sit at the best bid and best ask as they were D ms
ago (500 shares each), i.e. a bot that sees every change but needs D to re-quote.  Fills: back of the queue, so
only trades strictly THROUGH our price fill us, fully, at our price; a filled side is off for D ms.  Inventory capped
at 2x size, marked to the final mid.  Rewards are not included (identical across D); compare the fill loss with the
paper LP's reward estimate to find the break-even reaction time.  Online time excludes gaps > 5 min (curfew).
  python backfill/lptick.py
"""
from __future__ import annotations

import glob
import json
import os

import numpy as np
import pandas as pd

TICK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "live", "pmtick")
STATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "live", "pmlp_state.json")
SIZE = 500
DELAYS_MS = (100, 500, 1000, 3000, 15000, 60000)


def load():
    yes = {m["token"]: m["cid"] for m in json.load(open(STATE))["markets"]}
    quotes, trades = [], []
    for path in sorted(glob.glob(os.path.join(TICK, "*.jsonl"))):
        with open(path) as f:
            for line in f:
                j = json.loads(line)
                e = j.get("event_type")
                ts = int(j.get("timestamp") or j["rx"])
                if e == "price_change":
                    for c in j.get("price_changes", []):
                        if c.get("asset_id") in yes and c.get("best_bid") and c.get("best_ask"):
                            quotes.append((yes[c["asset_id"]], ts, float(c["best_bid"]), float(c["best_ask"])))
                elif e == "book" and j.get("asset_id") in yes:
                    b = [float(x["price"]) for x in j.get("bids", [])]
                    a = [float(x["price"]) for x in j.get("asks", [])]
                    if b and a:
                        quotes.append((yes[j["asset_id"]], ts, max(b), min(a)))
                elif e == "last_trade_price":
                    aid, px, side = j.get("asset_id"), float(j["price"]), j.get("side")
                    is_yes = aid in yes
                    cid = yes.get(aid) or j.get("market")
                    trades.append((cid, ts, px if is_yes else 1 - px, (side == "BUY") == is_yes))
    Q = pd.DataFrame(quotes, columns=["cid", "ts", "bid", "ask"]).sort_values(["cid", "ts"])
    T = pd.DataFrame(trades, columns=["cid", "ts", "yes_px", "bought_yes"]).sort_values(["cid", "ts"])
    return Q, T


def online_hours(Q):
    t = np.sort(Q.ts.unique())
    d = np.diff(t)
    return d[d <= 300_000].sum() / 3.6e6


def simulate(q, t, delay):
    """q: one market's (ts, bid, ask); t: its trades.  Our quote at time x = touch at x - delay."""
    qts = q.ts.values
    inv = cash = 0.0
    fills = 0
    off_bid = off_ask = -1
    for ts, px, bought in zip(t.ts.values, t.yes_px.values, t.bought_yes.values):
        i = np.searchsorted(qts, ts - delay, side="right") - 1
        if i < 0:
            continue
        bid, ask = q.bid.values[i], q.ask.values[i]
        if not bought and ts >= off_bid and inv < 2 * SIZE and px < bid - 1e-9:
            inv += SIZE; cash -= SIZE * bid; fills += 1; off_bid = ts + delay
        if bought and ts >= off_ask and inv > -2 * SIZE and px > ask + 1e-9:
            inv -= SIZE; cash += SIZE * ask; fills += 1; off_ask = ts + delay
    mid = (q.bid.values[-1] + q.ask.values[-1]) / 2
    return fills, cash + inv * mid


def main():
    Q, T = load()
    hrs = online_hours(Q)
    rows = []
    for d in DELAYS_MS:
        f = pnl = 0
        for cid, q in Q.groupby("cid"):
            fi, p = simulate(q, T[T.cid == cid], d)
            f += fi
            pnl += p
        rows.append({"reaction_ms": d, "fills": f, "fill_pnl_$": round(pnl, 2), "per_online_hour_$": round(pnl / max(hrs, 1e-9), 2)})
    R = pd.DataFrame(rows)
    L = [f"# Liquidity provider: fill loss vs reaction time (tick data, {Q.cid.nunique()} markets, {hrs:.1f} online hours, "
         f"{len(T)} trades)", "", "Join best bid/ask, 500 shares, back-of-queue fills, rewards excluded.", "",
         R.to_markdown(index=False), "",
         "Break-even: the reaction time at which |fill loss per hour| falls below the reward income per hour "
         "(paper estimate from live/pmlp_tight.jsonl, an upper bound).", ""]
    open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results", "LP_TICK.md"), "w").write("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    main()
