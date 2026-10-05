"""Live, read-only check of the Kalshi range-vs-above/below arbitrage with real order-book depth.

Every few seconds, for the current BTC and ETH hourly events, read every order book (batched) and price the two
locked-in packages per range bracket [L, U]:
  A  YES range + YES above(U) + NO above(L-)   pays $1
  B  NO range  + NO above(U)  + YES above(L-)  pays $2
at the best ask of each leg, with the size available at that price (smallest of the three legs) and Kalshi taker fees
for that size.  Logs every package with a positive locked-in profit to arbscan.jsonl.  Never places orders.
  python live/arbscan.py --every 5 --hours 8
"""
from __future__ import annotations

import argparse
import json
import math
import os
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests

K = "https://api.elections.kalshi.com/trade-api/v2"
ET = ZoneInfo("America/New_York")
MON = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
PAIRS = {"KXBTC": "KXBTCD", "KXETH": "KXETHD"}
HERE = os.path.dirname(os.path.abspath(__file__))
S = requests.Session()


def kget(path, **params):
    for attempt in range(8):
        r = S.get(f"{K}{path}", params=params, timeout=20)
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(min(20, 2 ** attempt))
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError(path)


def event(series, close):
    t = close.astimezone(ET)
    return f"{series}-{t:%y}{MON[t.month - 1]}{t:%d%H}"


def fee_c(p, n):                                   # Kalshi taker fee per contract, cents, order of n at price p
    return math.ceil(7 * n * p * (1 - p)) / n


def books(tickers):
    """{ticker: (yes_ask, size, no_ask, size)} from batched order books; ask = 1 - best opposite bid"""
    out = {}
    for j in range(0, len(tickers), 100):
        d = kget("/markets/orderbooks", tickers=tickers[j:j + 100])
        for ob in d.get("orderbooks", []):
            b = ob["orderbook_fp"]
            yb = max(((float(p), float(q)) for p, q in b.get("yes_dollars") or []), default=None)
            nb = max(((float(p), float(q)) for p, q in b.get("no_dollars") or []), default=None)
            out[ob["ticker"]] = (round(1 - nb[0], 2) if nb else None, nb[1] if nb else 0,
                                 round(1 - yb[0], 2) if yb else None, yb[1] if yb else 0)
    return out


def strikes(rng, ab, close):
    mr = kget("/markets", event_ticker=event(rng, close), limit=1000).get("markets", [])
    ma = kget("/markets", event_ticker=event(ab, close), limit=1000).get("markets", [])
    above = {round(float(m["floor_strike"]), 2): m["ticker"] for m in ma if m.get("floor_strike") is not None}
    trip = []
    for m in mr:
        lo, hi = m.get("floor_strike"), m.get("cap_strike")
        if lo is None or hi is None:
            continue
        tl, th = above.get(round(float(lo) - 0.01, 2)), above.get(round(float(hi), 2))
        if tl and th:
            trip.append((m["ticker"], th, tl))
    return trip


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--every", type=float, default=5)
    ap.add_argument("--hours", type=float, default=8)
    ap.add_argument("--out", default=os.path.join(HERE, "arbscan.jsonl"))
    a = ap.parse_args()
    stop = time.time() + 3600 * a.hours
    cache, polls, hits = {}, 0, 0
    while time.time() < stop:
        now = datetime.now(timezone.utc)
        close = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
        for rng, ab in PAIRS.items():
            try:
                if cache.get(rng, (None,))[0] != close:
                    cache[rng] = (close, strikes(rng, ab, close))
                trip = cache[rng][1]
                if not trip:
                    continue
                Q = books(sorted({t for x in trip for t in x}))
                for r, h, l in trip:
                    if r not in Q or h not in Q or l not in Q:
                        continue
                    # (price, size) per leg for each package
                    for kind, legs, pay in (("A", [Q[r][0:2], Q[h][0:2], Q[l][2:4]], 1.0),
                                            ("B", [Q[r][2:4], Q[h][2:4], Q[l][0:2]], 2.0)):
                        if any(p is None or q <= 0 for p, q in legs):
                            continue
                        n = int(min(q for _, q in legs))
                        if n < 1:
                            continue
                        edge = 100 * pay - sum(100 * p + fee_c(p, n) for p, _ in legs)
                        if edge > 0:
                            hits += 1
                            with open(a.out, "a") as f:
                                f.write(json.dumps({"t": now.isoformat(), "close": close.isoformat(), "kind": kind,
                                                    "bracket": r, "edge_c": round(edge, 2), "size": n,
                                                    "profit_$": round(edge * n / 100, 2),
                                                    "legs": [p for p, _ in legs], "sizes": [q for _, q in legs]}) + "\n")
            except Exception as e:
                print(now.strftime("%H:%M:%S"), rng, "error", repr(e)[:150], flush=True)
        polls += 1
        if polls % 60 == 0:
            print(now.strftime("%H:%M:%S"), "polls", polls, "positive packages", hits, flush=True)
        time.sleep(max(0, a.every - (datetime.now(timezone.utc) - now).total_seconds()))


if __name__ == "__main__":
    main()
