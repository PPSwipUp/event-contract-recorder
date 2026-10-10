"""Kalshi ETH hourly range order-book depth at +15 min (results/AUDIT_RANGE_FORWARD.md: the forward ledger buys 100
contracts at the best ask with no depth check).  One pass: every bracket of the KXETH event that closes at the next
top of the hour; raw public orderbook -> live/kxdepth/<UTC date>.jsonl.  Read-only, no keys, never orders.
  python live/kxdepth.py
"""
import json
import os
import time
from datetime import datetime, timezone

import requests

B = "https://api.elections.kalshi.com/trade-api/v2"
HERE = os.path.dirname(os.path.abspath(__file__))


def get(url, **p):
    for attempt in range(5):
        try:
            r = requests.get(url, params=p, timeout=20)
            if r.status_code == 200:
                return r.json()
        except requests.RequestException:
            pass
        time.sleep(2 ** attempt)                     # Kalshi 429s GitHub IPs: back off
    return None


def main():
    now = datetime.now(timezone.utc)
    nxt = (int(now.timestamp()) // 3600 + 1) * 3600
    ms = (get(f"{B}/markets", series_ticker="KXETH", status="open", limit=1000) or {}).get("markets", [])
    ms = [m for m in ms if int(datetime.fromisoformat(m["close_time"].replace("Z", "+00:00")).timestamp()) == nxt
          and 0.01 < float(m.get("yes_ask_dollars") or 0) < 0.99]     # quoted brackets only (a bet needs an ask)
    os.makedirs(os.path.join(HERE, "kxdepth"), exist_ok=True)
    out = os.path.join(HERE, "kxdepth", f"{now:%Y-%m-%d}.jsonl")
    n = 0
    with open(out, "a") as f:
        for m in ms:
            ob = get(f"{B}/markets/{m['ticker']}/orderbook")
            if ob is None:
                continue
            f.write(json.dumps({"ts": int(time.time()), "ticker": m["ticker"], "event": m["event_ticker"],
                                "yes_ask": m.get("yes_ask_dollars"), "yes_bid": m.get("yes_bid_dollars"),
                                "book": ob.get("orderbook_fp") or ob.get("orderbook")}) + "\n")
            n += 1
            time.sleep(0.3)
    print(now.isoformat(timespec="seconds"), "kxdepth", len(ms), "brackets,", n, "books")


if __name__ == "__main__":
    main()
