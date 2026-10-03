"""Deep, read-only scan of Kalshi's hourly crypto range vs above/below markets for locked-in packages.  Never trades.

For the event closing at the next hour, per coin (BTC, ETH, SOL, XRP, BNB, HYPE), every package that pays a fixed
amount whatever the price does:
  SPAN_A k   YES on k adjacent range brackets [L..U] + YES above(U) + NO above(just below L)     pays 1
  SPAN_B k   NO on the same k brackets + NO above(U) + YES above(just below L)                   pays k + 1
  LADDER     YES above(K1) + NO above(K2), K1 < K2 (up to 3 strikes apart)                       pays >= 1
  ALL_YES    YES on every bracket incl. both tails (only if they cover every price)              pays 1
  ALL_NO     NO on every bracket                                                                 pays n - 1
Depth: each leg's full ask ladder (YES ask = 1 - NO bid, level by level); the package is filled level by level while
the marginal package still makes money after Kalshi's taker fee (ceil(7 n p (1-p)) cents per leg per level).
Persistence: polled every few seconds; each opportunity is tracked from first to last sighting and written once it
disappears (duration, polls seen, best profit, size) to kxcryptoarb.jsonl.
Validation on every sighting: the package's legs are re-read together in ONE request right away ('confirmed': the
gap was not an artefact of legs read seconds apart in different batches) and again 1 s later ('catchable': still
there after a laptop's reaction time).  Only confirmed / catchable profit should be believed.
  python live/kxcryptoarb.py --every 4 --hours 48
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backfill"))
import dohfix  # noqa: F401,E402
from arbscan import event, kget  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
COINS = {"BTC": ("KXBTC", "KXBTCD"), "ETH": ("KXETH", "KXETHD"), "SOL": ("KXSOLE", "KXSOLD"),
         "XRP": ("KXXRP", "KXXRPD"), "BNB": ("KXBNB", "KXBNBD"), "HYPE": ("KXHYPE", "KXHYPED")}


def ladders(tickers):
    """{ticker: {'yes': [(ask, qty) ascending], 'no': [...]}} from batched order books (bids -> opposite asks)"""
    out = {}
    for j in range(0, len(tickers), 100):
        d = kget("/markets/orderbooks", tickers=tickers[j:j + 100])
        for ob in d.get("orderbooks", []):
            b = ob["orderbook_fp"]
            yb = [(float(p), float(q)) for p, q in b.get("yes_dollars") or []]
            nb = [(float(p), float(q)) for p, q in b.get("no_dollars") or []]
            out[ob["ticker"]] = {"yes": sorted((round(1 - p, 4), q) for p, q in nb),     # buy YES = hit NO bids
                                 "no": sorted((round(1 - p, 4), q) for p, q in yb)}
    return out


def fill(legs, pay, max_levels=5):
    """walk the legs' ask ladders together; returns (profit $, contracts, avg edge c) or None"""
    pos = [0] * len(legs)
    left = [lv[0][1] if lv else 0 for lv in legs]
    size = profit = 0.0
    for _ in range(max_levels * len(legs)):
        if any(i >= len(lv) for i, lv in zip(pos, legs)):
            break
        px = [lv[i][0] for i, lv in zip(pos, legs)]
        q = int(min(left))
        if q < 1:
            break
        cost = sum(100 * p * q + math.ceil(7 * q * p * (1 - p)) for p in px)      # cents incl. fees for this chunk
        gain = 100 * pay * q - cost
        if gain <= 0:
            break
        size += q
        profit += gain
        for k in range(len(legs)):
            left[k] -= q
            if left[k] <= 0:
                pos[k] += 1
                left[k] = legs[k][pos[k]][1] if pos[k] < len(legs[k]) else 0
    return (round(profit / 100, 2), int(size), round(profit / size, 2)) if size else None


def structure(coin, close):
    rs, ab = COINS[coin]
    mr = kget("/markets", event_ticker=event(rs, close), limit=1000).get("markets", [])
    ma = kget("/markets", event_ticker=event(ab, close), limit=1000).get("markets", [])
    above = sorted((float(m["floor_strike"]), m["ticker"]) for m in ma if m.get("floor_strike") is not None)
    mids = sorted((float(m["floor_strike"]), float(m["cap_strike"]), m["ticker"]) for m in mr
                  if m.get("strike_type") == "between" and m.get("floor_strike") is not None and m.get("cap_strike") is not None)
    lo_tail = [m for m in mr if m.get("strike_type") == "less"]
    hi_tail = [m for m in mr if m.get("strike_type") == "greater"]

    def above_at(x, below=True):
        tol = 2e-4 * x
        c = [(s, t) for s, t in above if (x - tol <= s < x if below else abs(s - x) <= tol)]
        return max(c)[1] if c else None
    pk = []
    for i in range(len(mids)):
        for k in (1, 2, 3):
            span = mids[i:i + k]
            if len(span) < k or any(abs(span[n + 1][0] - span[n][1]) > 2e-4 * span[n][1] + 0.011 for n in range(k - 1)):
                continue
            a_lo, a_hi = above_at(span[0][0]), above_at(span[-1][1], below=False)
            if a_lo and a_hi:
                br = [t for _, _, t in span]
                pk.append((f"SPAN_A{k}", [(t, "yes") for t in br] + [(a_hi, "yes"), (a_lo, "no")], 1))
                pk.append((f"SPAN_B{k}", [(t, "no") for t in br] + [(a_hi, "no"), (a_lo, "yes")], k + 1))
    for i in range(len(above)):
        for g in (1, 2, 3):
            if i + g < len(above):
                pk.append(("LADDER", [(above[i][1], "yes"), (above[i + g][1], "no")], 1))
    if len(lo_tail) == 1 and len(hi_tail) == 1 and mids:
        allb = [lo_tail[0]["ticker"]] + [t for _, _, t in mids] + [hi_tail[0]["ticker"]]
        contiguous = abs(float(lo_tail[0]["cap_strike"]) - mids[0][0]) <= 2e-4 * mids[0][0] + 0.011 and \
            abs(float(hi_tail[0]["floor_strike"]) - mids[-1][1]) <= 2e-4 * mids[-1][1] + 0.011 and \
            all(abs(mids[n + 1][0] - mids[n][1]) <= 2e-4 * mids[n][1] + 0.011 for n in range(len(mids) - 1))
        if contiguous:
            pk.append(("ALL_YES", [(t, "yes") for t in allb], 1))
        pk.append(("ALL_NO", [(t, "no") for t in allb], len(allb) - 1))
    return pk


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--every", type=float, default=4)
    ap.add_argument("--hours", type=float, default=48)
    a = ap.parse_args()
    out = os.path.join(HERE, "kxcryptoarb.jsonl")
    stop, cache, active, polls = time.time() + 3600 * a.hours, {}, {}, 0
    while time.time() < stop:
        t0 = time.time()
        now = datetime.now(timezone.utc)
        close = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
        seen = set()
        try:
            for coin in COINS:
                if cache.get(coin, (None,))[0] != close:
                    cache[coin] = (close, structure(coin, close))
                pk = cache[coin][1]
                if not pk:
                    continue
                Q = ladders(sorted({t for _, legs, _ in pk for t, _ in legs}))
                for kind, legs, pay in pk:
                    lv = [Q.get(t, {}).get(side, []) for t, side in legs]
                    r = fill(lv, pay)
                    if not r or r[0] <= 0:
                        continue
                    tk = sorted({t for t, _ in legs})
                    Q1 = ladders(tk)                                            # same instant, one request
                    r1 = fill([Q1.get(t, {}).get(side, []) for t, side in legs], pay)
                    r2 = None
                    if r1 and r1[0] > 0:
                        time.sleep(1.0)
                        Q2 = ladders(tk)
                        r2 = fill([Q2.get(t, {}).get(side, []) for t, side in legs], pay)
                    key = f"{coin}|{kind}|{'+'.join(t.split('-')[-1] + side[0] for t, side in legs)}|{close:%H}"
                    seen.add(key)
                    s = active.setdefault(key, {"coin": coin, "kind": kind, "close": close.isoformat(), "legs": len(legs),
                                                "first": now.isoformat(timespec="seconds"), "polls": 0, "best_profit_$": 0,
                                                "best_size": 0, "best_edge_c": 0, "min_to_close": round((close - now).total_seconds() / 60, 1),
                                                "confirmed_profit_$": 0, "catchable_profit_$": 0, "catchable_size": 0})
                    s["polls"] += 1
                    s["last"] = now.isoformat(timespec="seconds")
                    if r[0] > s["best_profit_$"]:
                        s["best_profit_$"], s["best_size"], s["best_edge_c"] = r
                    if r1 and r1[0] > s["confirmed_profit_$"]:
                        s["confirmed_profit_$"] = r1[0]
                    if r2 and r2[0] > s["catchable_profit_$"]:
                        s["catchable_profit_$"], s["catchable_size"] = r2[0], r2[1]
        except Exception as err:
            print(now.strftime("%H:%M:%S"), "error", repr(err)[:150], flush=True)
        with open(out, "a") as f:
            for key in [k for k in active if k not in seen]:
                s = active.pop(key)
                s["duration_s"] = (datetime.fromisoformat(s["last"]) - datetime.fromisoformat(s["first"])).total_seconds()
                f.write(json.dumps({"key": key, **s}) + "\n")
        polls += 1
        if polls % 150 == 0:
            print(now.strftime("%H:%M"), "polls", polls, "open opportunities", len(active), flush=True)
        time.sleep(max(0, a.every - (time.time() - t0)))


if __name__ == "__main__":
    main()
