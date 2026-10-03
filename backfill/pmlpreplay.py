"""Historical replay of the paper liquidity provider (live/pmlp.py) on its 20 markets, last 60 days: what do FILLS
cost?  (Rewards are the published formula; fills are the unknown.)

Each minute, quotes from the previous minute's midpoint (CLOB prices-history, 1-min), ON THE TICK GRID:
  wide   bid = floor(mid - v/3), ask = ceil(mid + v/3)   200 shares/side
  touch  bid = floor(mid - tick/2), ask = ceil(mid + tick/2)  (joins the best bid/ask)   500 shares/side
Fills from every real taker trade (data-api), two queue bounds:
  front  any trade AT or THROUGH our price fills our whole size at our price (we are first in line)
  back   only trades strictly THROUGH our price fill us (everyone else at our price goes first)
A filled side is re-quoted next minute; inventory capped at 2x size.  P&L marked to the midpoint (no resolutions in
the window).  Reward income per day for comparison = today's reward share against the live book (tick-correct
distance), assumed constant - an assumption, flagged.
  python backfill/pmlpreplay.py
"""
from __future__ import annotations

import json
import math
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "live"))
from pmlp import book  # noqa: E402
from pmtouchdata import jget  # noqa: E402

D = "data_local/pmlpreplay"
DAYS = 60
CFG = {"wide": 200, "touch": 500}


def minutes(token):
    now, pts = int(time.time()), {}
    for k in range(0, DAYS, 7):
        t1 = now - k * 86400
        h = jget("https://clob.polymarket.com/prices-history", market=token, startTs=t1 - 7 * 86400, endTs=t1, fidelity=1)
        for x in (h or {}).get("history", []):
            pts[int(x["t"]) // 60 * 60] = float(x["p"])
    s = pd.Series(pts).sort_index()
    return s[s.index >= now - DAYS * 86400]


def trades(cid, since):
    out, end = {}, None
    while True:
        j = jget("https://data-api.polymarket.com/trades", market=cid, limit=1000, takerOnly="true", **({"end": end} if end else {}))
        new = 0
        for t in j:
            key = (t["transactionHash"], t["asset"], t["side"], t["size"], t["price"])
            if key not in out and t["timestamp"] >= since:
                new += 1
                yes_px = float(t["price"]) if t["outcome"] == "Yes" else 1 - float(t["price"])
                out[key] = (t["timestamp"], yes_px, (t["side"] == "BUY") == (t["outcome"] == "Yes"), float(t["size"]))
        if len(j) < 1000 or not new or min(t["timestamp"] for t in j) < since:
            return sorted(out.values())
        end = min(t["timestamp"] for t in j)


def quotes(mid, v, tick, kind):
    d = v / 3 / 100 if kind == "wide" else tick / 2
    bid = math.floor(round((mid - d) / tick, 6)) * tick
    ask = math.ceil(round((mid + d) / tick, 6)) * tick
    return round(bid, 4), round(ask, 4)


def replay(m, mids, T, kind, queue):
    size = CFG[kind]
    inv = cash = 0.0
    fills, daily = 0, {}
    ti = 0
    bid_on = ask_on = True
    ts_list = mids.index.values
    for i in range(1, len(ts_list)):
        t0, t1 = ts_list[i - 1], ts_list[i]
        mid = mids.iloc[i - 1]
        bid, ask = quotes(mid, m["v"], m["tick"], kind)
        bid_on, ask_on = inv < 2 * size and bid > 0, inv > -2 * size and ask < 1
        while ti < len(T) and T[ti][0] < t0:
            ti += 1
        j = ti
        while j < len(T) and T[j][0] < t1:
            _, px, bought_yes, _ = T[j]
            hit_bid = (not bought_yes) and (px < bid - 1e-9 or (queue == "front" and px <= bid + 1e-9))
            hit_ask = bought_yes and (px > ask + 1e-9 or (queue == "front" and px >= ask - 1e-9))
            if bid_on and hit_bid:
                inv += size; cash -= size * bid; fills += 1; bid_on = False
            if ask_on and hit_ask:
                inv -= size; cash += size * ask; fills += 1; ask_on = False
            j += 1
        day = pd.Timestamp(t1, unit="s").strftime("%Y-%m-%d")
        daily[day] = cash + inv * mids.iloc[i]                       # cumulative mark-to-market at day end
    s = pd.Series(daily)
    return fills, s.diff().fillna(s.iloc[0]) if len(s) else s, inv * mids.iloc[-1] + cash


def reward_now(m, kind):
    cache = f"{D}/reward_{m['cid'][:12]}_{kind}.json"
    if os.path.exists(cache):
        return json.load(open(cache))
    b = book(m["token"])
    if not b or not b["bids"] or not b["asks"]:
        raise RuntimeError(f"no live book for {m['question'][:40]} - cannot estimate reward")
    mid = (b["bids"][0][0] + b["asks"][0][0]) / 2
    bid, ask = quotes(mid, m["v"], m["tick"], kind)
    v, size = m["v"], CFG[kind]

    def side(levels):
        return sum(((v - abs(px - mid) * 100) / v) ** 2 * q for px, q in levels if abs(px - mid) * 100 < v and q >= m["min_size"])
    others = (side(b["bids"]) + side(b["asks"])) / 2
    s = min(((v - (mid - bid) * 100) / v) ** 2, ((v - (ask - mid) * 100) / v) ** 2) if max(mid - bid, ask - mid) * 100 < v else 0
    ours = s * size
    r = m["rate"] * ours / (ours + others) if ours + others > 0 else 0.0
    json.dump(r, open(cache, "w"))
    return r


def main():
    os.makedirs(D, exist_ok=True)
    st = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "live", "pmlp_state.json")))
    M = st["markets"]
    since = int(time.time()) - DAYS * 86400

    def load(m):
        p = f"{D}/{m['cid'][:12]}.json"
        if os.path.exists(p):
            x = json.load(open(p))
            return pd.Series(x["mids"]).rename(index=int), [tuple(t) for t in x["trades"]]
        mids, T = minutes(m["token"]), trades(m["cid"], since)
        json.dump({"mids": {int(k): v for k, v in mids.items()}, "trades": T}, open(p, "w"))
        return mids, T
    with ThreadPoolExecutor(4) as ex:
        data = list(ex.map(load, M))
    rows, daily = [], []
    for m, (mids, T) in zip(M, data):
        if len(mids) < 1000:
            continue
        for kind in CFG:
            rw = reward_now(m, kind)
            for queue in ("front", "back"):
                f, d, total = replay(m, mids, T, kind, queue)
                ndays = max(1, len(d))
                rows.append({"market": m["question"][:40], "kind": kind, "queue": queue, "trades": len(T), "fills": f,
                             "fill_pnl_day_$": round(total / ndays, 2), "reward_day_$": round(rw, 2),
                             "net_day_$": round(total / ndays + rw, 2), "worst_day_$": round(d.min(), 2) if len(d) else 0})
                daily.append((d + rw).rename(f"{m['cid'][:8]}|{kind}|{queue}"))     # net per active day
    R = pd.DataFrame(rows)
    Dd = pd.concat(daily, axis=1)                                   # NaN = market not live that day
    L = ["# Paper liquidity provider: 60-day historical replay of fill costs (20 markets)", "",
         "Rewards = today's share against the live book, assumed constant (unverified assumption).", ""]
    tot = R.groupby(["kind", "queue"]).agg(fills=("fills", "sum"), fill_pnl_day=("fill_pnl_day_$", "sum"),
                                           reward_day=("reward_day_$", "sum"), net_day=("net_day_$", "sum")).round(2)
    L += ["## Totals per day (all 20 markets)", "", tot.to_markdown(), ""]
    for kind in CFG:
        for queue in ("front", "back"):
            cols = [c for c in Dd.columns if c.endswith(f"|{kind}|{queue}")]
            net = Dd[cols].sum(axis=1, min_count=1).dropna()
            eq = net.cumsum()
            L.append(f"- {kind}/{queue}: daily net mean ${net.mean():.2f}, sd ${net.std():.2f}, worst day ${net.min():.2f}, "
                     f"max drawdown ${(eq.cummax() - eq).max():.2f}, positive days {(net > 0).mean():.0%}, "
                     f"t {net.mean() / net.std() * np.sqrt(len(net)):.2f}" if net.std() > 0 else f"- {kind}/{queue}: no data")
    L += ["", "## Per market (touch / back queue = most realistic tight quoting)", "",
          R[(R.kind == "touch") & (R.queue == "back")].sort_values("net_day_$").to_markdown(index=False), "",
          "## Per market (wide / back queue)", "",
          R[(R.kind == "wide") & (R.queue == "back")].sort_values("net_day_$").to_markdown(index=False), ""]
    open("../results/PM_LP_REPLAY.md", "w").write("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    main()
