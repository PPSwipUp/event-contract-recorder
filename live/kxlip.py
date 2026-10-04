"""Paper liquidity provider for Kalshi's Liquidity Incentive Program.  Read-only: never places orders.

Every minute: take the active incentive programs, keep the series in --series, and for each market quote X
contracts at the best YES bid and the best NO bid (joining both queues).
  reward : Kalshi's published scoring (backfill/kalshilip.market_share: back of the queue, reference price at
           Target/5, Discount^ticks; snapshots with either side below Target pay nothing),
           our share of the current snapshot x period reward x (60 s / period length)
  fills  : every public trade since the last minute that went strictly THROUGH our price fills our whole size at
           our price (back of the queue): a taker buying NO below 1 - our YES bid hits our YES bid, etc.
  settle : when a market closes, open inventory is valued at its official result (YES = $1 / $0)
P&L = rewards + realised fill P&L at settlement + mark-to-mid of anything still open.  Kalshi taker fees are paid by
the taker; maker fees (some series) are charged here at ceil(1.75 n p (1-p)) cents as a conservative assumption.
  python live/kxlip.py --series KXCRYPTOLEAD15M,KXTEMPMIAH,KXRT --size 100 --hours 168
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from datetime import datetime, timezone

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backfill"))
import dohfix  # noqa: F401,E402
from arbscan import kget  # noqa: E402
from kalshilip import market_share  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


def maker_fee(p, n):
    return math.ceil(1.75 * n * p * (1 - p)) / 100


def active(series):
    rows, cur = [], None
    while True:
        p = {"status": "active", "limit": 1000}
        if cur:
            p["cursor"] = cur
        d = kget("/incentive_programs", **p)
        rows += [x for x in d.get("incentive_programs", []) if x["market_ticker"].split("-")[0] in series]
        cur = d.get("next_cursor") or d.get("cursor")
        if not cur or not d.get("incentive_programs"):
            return rows


def books(tickers):
    out = {}
    for j in range(0, len(tickers), 100):
        d = kget("/markets/orderbooks", tickers=tickers[j:j + 100])
        for ob in d.get("orderbooks", []):
            b = ob["orderbook_fp"]
            out[ob["ticker"]] = [sorted(((float(p), float(q)) for p, q in b.get(s) or []), reverse=True)
                                 for s in ("yes_dollars", "no_dollars")]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", default="KXCRYPTOLEAD15M,KXTEMPMIAH,KXRT")
    ap.add_argument("--size", type=float, default=100)
    ap.add_argument("--hours", type=float, default=168)
    a = ap.parse_args()
    series = set(a.series.split(","))
    state_path, log_path = os.path.join(HERE, "kxlip_state.json"), os.path.join(HERE, "kxlip.jsonl")
    try:
        st = json.load(open(state_path))
    except (OSError, ValueError):
        st = {"pos": {}, "reward": 0.0, "realised": 0.0, "fees": 0.0, "fills": 0}
    stop, last_loop = time.time() + 3600 * a.hours, time.time()
    while time.time() < stop:
        t0 = time.time()
        try:
            gap = t0 - last_loop > 300                                    # outage (curfew): drop stale quotes
            last_loop = t0
            progs = {p["market_ticker"]: p for p in active(series)}
            B = books(list(progs))
            for tk, pr in progs.items():
                pos = st["pos"].setdefault(tk, {"inv": 0.0, "cash": 0.0, "yes_bid": None, "no_bid": None, "last": int(t0)})
                # 1) fills against last minute's quotes
                if not gap and (pos["yes_bid"] or pos["no_bid"]):
                    tr = kget("/markets/trades", ticker=tk, min_ts=pos["last"], limit=1000).get("trades", [])
                    for t in tr:
                        yp = float(t.get("yes_price_dollars") or 0)
                        taker_no = t.get("taker_side") == "no"
                        if pos["yes_bid"] and taker_no and yp < pos["yes_bid"] - 1e-9:      # sold YES below our bid
                            pos["inv"] += a.size; pos["cash"] -= a.size * pos["yes_bid"]
                            st["fees"] += maker_fee(pos["yes_bid"], a.size); st["fills"] += 1; pos["yes_bid"] = None
                        if pos["no_bid"] and not taker_no and (1 - yp) < pos["no_bid"] - 1e-9:  # sold NO below our bid
                            pos["inv"] -= a.size; pos["cash"] -= a.size * pos["no_bid"]
                            st["fees"] += maker_fee(pos["no_bid"], a.size); st["fills"] += 1; pos["no_bid"] = None
                pos["last"] = int(t0)
                # 2) reward for this minute and fresh quotes
                bk = B.get(tk)
                if not bk:
                    continue
                hours = (pd.Timestamp(pr["end_date"]) - pd.Timestamp(pr["start_date"])).total_seconds() / 3600
                sh = market_share(bk, float(pr["target_size_fp"]), (pr.get("discount_factor_bps") or 10000) / 10000, a.size)
                if sh:                                   # None = snapshot excluded (a side below target): no reward
                    st["reward"] += sh * pr["period_reward"] / 10000 * (60 / 3600) / max(hours, 1 / 60)
                pos["yes_bid"] = bk[0][0][0] if bk[0] and abs(pos["inv"]) < 2 * a.size else None
                pos["no_bid"] = bk[1][0][0] if bk[1] and abs(pos["inv"]) < 2 * a.size else None
                pos["mid"] = (bk[0][0][0] + 1 - bk[1][0][0]) / 2 if bk[0] and bk[1] else pos.get("mid")
            # 3) settle positions in markets that are no longer incentivised and have closed
            for tk in [k for k in st["pos"] if k not in progs]:
                pos = st["pos"][tk]
                m = kget(f"/markets/{tk}").get("market", {})
                if m.get("result") in ("yes", "no"):
                    yes_val = 1.0 if m["result"] == "yes" else 0.0
                    # inv > 0 = long YES; inv < 0 = long NO (bought NO contracts)
                    st["realised"] += pos["cash"] + (pos["inv"] * yes_val if pos["inv"] > 0 else -pos["inv"] * (1 - yes_val))
                    del st["pos"][tk]
            mtm = sum(p["cash"] + (p["inv"] * (p.get("mid") or 0.5) if p["inv"] > 0 else -p["inv"] * (1 - (p.get("mid") or 0.5)))
                      for p in st["pos"].values())
            json.dump(st, open(state_path, "w"))
            with open(log_path, "a") as f:
                f.write(json.dumps({"t": datetime.now(timezone.utc).isoformat(timespec="seconds"), "markets": len(progs),
                                    "reward": round(st["reward"], 2), "realised": round(st["realised"], 2), "open_mtm": round(mtm, 2),
                                    "maker_fees": round(st["fees"], 2), "fills": st["fills"],
                                    "net": round(st["reward"] + st["realised"] + mtm - st["fees"], 2)}) + "\n")
        except Exception as err:
            print(datetime.now(timezone.utc).strftime("%H:%M:%S"), "error", repr(err)[:150], flush=True)
        time.sleep(max(1, 60 - (time.time() - t0)))


if __name__ == "__main__":
    main()
