"""Read-only Polymarket top-of-book recorder for the "be first at a fresh price level" idea.

Every few seconds, for the paper-LP markets plus the most liquid rewarded long-dated markets, logs best bid/ask
(price + size), the second levels, spread in ticks and the latest trade timestamp to pmgap.jsonl.  Later analysis:
how often the spread opens to 2+ ticks and for how long, and what the price does 1/5/30 min after an order that was
first inside the gap would have been filled.  Never places orders.
  python live/pmgap.py --every 3 --extra 20 --hours 96
"""
from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone

from pmlp import CLOB, S, choose

HERE = os.path.dirname(os.path.abspath(__file__))


def books(tokens):
    r = S.post(f"{CLOB}/books", json=[{"token_id": t} for t in tokens], timeout=20)
    r.raise_for_status()
    return r.json()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--every", type=float, default=3)
    ap.add_argument("--extra", type=int, default=20)
    ap.add_argument("--hours", type=float, default=96)
    a = ap.parse_args()
    lp = json.load(open(os.path.join(HERE, "pmlp_state.json")))["markets"]
    extra = [m for m in choose(60, 20) if m["cid"] not in {x["cid"] for x in lp}][:a.extra]
    M = {m["token"]: m for m in lp + extra}
    print(len(M), "markets", flush=True)
    out = os.path.join(HERE, "pmgap.jsonl")
    stop, n = time.time() + 3600 * a.hours, 0
    while time.time() < stop:
        t0 = time.time()
        try:
            for b in books(list(M)):
                bids = sorted(((float(x["price"]), float(x["size"])) for x in b.get("bids", [])), reverse=True)
                asks = sorted((float(x["price"]), float(x["size"])) for x in b.get("asks", []))
                if not bids or not asks:
                    continue
                m = M[b["asset_id"]]
                rec = {"t": round(t0, 2), "cid": m["cid"][:12], "tick": m["tick"],
                       "b1": bids[0], "a1": asks[0], "b2": bids[1] if len(bids) > 1 else None,
                       "a2": asks[1] if len(asks) > 1 else None,
                       "spread_ticks": round((asks[0][0] - bids[0][0]) / m["tick"]), "last": b.get("last_trade_price")}
                with open(out, "a") as f:
                    f.write(json.dumps(rec) + "\n")
        except Exception as err:
            print(datetime.now(timezone.utc).strftime("%H:%M:%S"), "error", repr(err)[:120], flush=True)
        n += 1
        if n % 1200 == 0:
            print(datetime.now(timezone.utc).strftime("%H:%M"), "polls", n, flush=True)
        time.sleep(max(0, a.every - (time.time() - t0)))


if __name__ == "__main__":
    main()
