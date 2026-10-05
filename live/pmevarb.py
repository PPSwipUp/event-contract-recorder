"""Read-only scan of every active Polymarket event for locked-in packages.  Never places orders.

  ALL_NO    neg-risk event (exactly one outcome can win): buy NO in all n markets, pays >= n-1.  Safe.
  ALL_YES   neg-risk event: buy YES in all n markets, pays 1 only if the listed outcomes are exhaustive -> logged
            with safe=False (needs a manual check of the rules, e.g. an 'Other' market).
  LADDER    two markets of one event where one implies the other:
              dates   "... by <date>": YES later + NO earlier pays >= 1 (if it happens by the earlier date it also
                      happened by the later one).  Ordered by each market's end date.
              prices  "above / reach / hit $K": YES at the lower K + NO at the higher K pays >= 1;
                      "dip / below / drop" reversed.
Each leg at its best ask (NO ask = 1 - best YES bid; the YES and NO books are one mirrored book), size = smaller
best-ask size, Polymarket taker fee rate*p*(1-p) per share from the market's own fee schedule (0 if fees are off).
Logs every package with locked profit > 0 to pmevarb<tag>.jsonl.
--confirm: each positive package's legs are re-read in ONE /books request immediately ("confirmed" = still positive
at a single instant) and again 1 s later ("catchable"); both results are logged with the hit.  (Without it, a
scan reads ~235k books over ~200 s in token-id order, so the legs of one event can be read minutes apart.)
  python live/pmevarb.py --hours 48 --pause 300
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone

import requests

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backfill"))
import dohfix  # noqa: F401,E402

HERE = os.path.dirname(os.path.abspath(__file__))
S = requests.Session()


def jget(url, **p):
    for attempt in range(5):
        try:
            r = S.get(url, params=p, timeout=60)
            if r.status_code == 200:
                return r.json()
        except requests.RequestException:
            pass
        time.sleep(1 + 2 * attempt)
    return None


def events():
    out, cur = [], None
    while True:
        d = jget("https://gamma-api.polymarket.com/events/keyset", active="true", closed="false", limit=500,
                 **({"after_cursor": cur} if cur else {}))
        if not d:
            return out
        for e in d.get("events", []):
            ms = [m for m in e.get("markets") or [] if m.get("acceptingOrders") and m.get("clobTokenIds") and not m.get("closed")]
            if len(ms) >= 2:
                out.append((e, ms))
        cur = d.get("next_cursor")
        if not cur or not d.get("events"):
            return out


def tops(tokens):
    """{yes token: (best bid, bid size, best ask, ask size)}"""
    out = {}
    for i in range(0, len(tokens), 100):
        try:
            r = S.post("https://clob.polymarket.com/books", json=[{"token_id": t} for t in tokens[i:i + 100]], timeout=30).json()
        except (requests.RequestException, ValueError):
            continue
        for b in r if isinstance(r, list) else []:
            bids = [(float(x["price"]), float(x["size"])) for x in b.get("bids", [])]
            asks = [(float(x["price"]), float(x["size"])) for x in b.get("asks", [])]
            bb, ba = max(bids, default=(None, 0)), min(asks, default=(None, 0))
            out[b["asset_id"]] = (bb[0], bb[1], ba[0], ba[1])
    return out


def recheck(legs_fn, ms, pay):
    """re-read all legs in one request: (edge, size) or None"""
    Q = tops([json.loads(m["clobTokenIds"])[0] for m in ms])
    return package([f(m, Q) for f, m in zip(legs_fn, ms)], pay)


def rate(m):
    fs = m.get("feeSchedule") or {}
    return float(fs.get("rate") or 0) if m.get("feesEnabled") else 0.0


def legs_yes(m, Q):
    q = Q.get(json.loads(m["clobTokenIds"])[0])
    return None if not q or q[2] is None else (q[2], q[3], rate(m))


def legs_no(m, Q):
    q = Q.get(json.loads(m["clobTokenIds"])[0])
    return None if not q or q[0] is None else (round(1 - q[0], 4), q[1], rate(m))


def package(legs, pay):
    if any(x is None or x[1] <= 0 for x in legs):
        return None
    size = min(x[1] for x in legs)
    if size < 5:                                                        # Polymarket minimum order 5 shares
        return None
    edge = 100 * pay - sum(100 * p + 100 * r * p * (1 - p) for p, _, r in legs)
    return (round(edge, 3), round(size, 1)) if edge > 0 else None


def strike(q):
    x = re.search(r"\$([\d,\.]+)\s*(bn|[kKmMbB])?\b", q)
    if not x:
        return None
    v = float(x.group(1).replace(",", "").rstrip("."))
    unit = (x.group(2) or "").lower()
    return v * {"k": 1e3, "m": 1e6, "b": 1e9, "bn": 1e9}.get(unit, 1)


def direction(q):
    """+1: YES needs the value to get HIGH (above/reach/(HIGH)), -1: LOW (below/dip/(LOW)), 0: unclear"""
    q = q.lower()
    down = any(w in q for w in ("(low)", "dip", "below", "drop to", "fall to", "less than"))
    up = any(w in q for w in ("(high)", " above ", "reach", "greater than", "exceed")) or (" hit " in q and not down)
    return 0 if up == down else (1 if up else -1)


def ladders(ms):
    """pairs (implied, implier): YES(implied) >= YES(implier) must hold"""
    out = []
    qs = [m["question"].lower() for m in ms]
    if all(" by " in q for q in qs) and all(strike(m["question"]) is None for m in ms):
        o = sorted(ms, key=lambda m: m.get("endDate") or "")
        out += [(o[i + 1], o[i]) for i in range(len(o) - 1) if o[i].get("endDate") != o[i + 1].get("endDate")]
    for sign in (1, -1):                                           # price ladders, one direction at a time
        g = [(strike(m["question"]), m) for m in ms if direction(m["question"]) == sign and strike(m["question"]) is not None]
        if len(g) < 2 or len({k for k, _ in g}) < len(g) or len({m.get("endDate") for _, m in g}) > 1:
            continue
        o = [m for _, m in sorted(g, key=lambda x: x[0])]
        if sign == 1:
            out += [(o[i], o[i + 1]) for i in range(len(o) - 1)]        # reaching the higher K implies the lower
        else:
            out += [(o[i + 1], o[i]) for i in range(len(o) - 1)]        # dipping to the lower K implies the higher


    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=float, default=48)
    ap.add_argument("--pause", type=float, default=300)
    ap.add_argument("--tag", default="")
    ap.add_argument("--confirm", action="store_true")
    a = ap.parse_args()
    out = os.path.join(HERE, f"pmevarb{a.tag}.jsonl")
    stop, scans = time.time() + 3600 * a.hours, 0
    while time.time() < stop:
        t0 = time.time()
        E = events()
        Q = tops(sorted({json.loads(m["clobTokenIds"])[0] for _, ms in E for m in ms}))
        hits = []
        for e, ms in E:
            if e.get("negRisk"):
                for kind, legs, pay, safe in (("ALL_NO", [legs_no(m, Q) for m in ms], len(ms) - 1, True),
                                              ("ALL_YES", [legs_yes(m, Q) for m in ms], 1, False)):
                    r = package(legs, pay)
                    if r:
                        h = {"event": e.get("slug"), "kind": kind, "n": len(ms), "safe": safe, "edge_c": r[0], "size": r[1]}
                        if a.confirm and safe:
                            fn = [legs_no] * len(ms)
                            h["confirmed"] = recheck(fn, ms, pay)
                            time.sleep(1)
                            h["catchable"] = recheck(fn, ms, pay)
                        hits.append(h)
            for implied, implier in ladders(ms):
                r = package([legs_yes(implied, Q), legs_no(implier, Q)], 1)
                if r:
                    h = {"event": e.get("slug"), "kind": "LADDER", "n": 2, "safe": True, "edge_c": r[0], "size": r[1],
                         "legs": [implied["question"][:70], implier["question"][:70]]}
                    if a.confirm:
                        h["confirmed"] = recheck([legs_yes, legs_no], [implied, implier], 1)
                        time.sleep(1)
                        h["catchable"] = recheck([legs_yes, legs_no], [implied, implier], 1)
                    hits.append(h)
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with open(out, "a") as f:
            for h in hits:
                h["profit_$"] = round(h["edge_c"] * h["size"] / 100, 2)
                f.write(json.dumps({"t": now, **h}) + "\n")
        scans += 1
        print(now[11:16], f"scan {scans}: {len(E)} events, {len(Q)} books, {len(hits)} positive "
              f"({sum(h['safe'] for h in hits)} safe), {time.time() - t0:.0f}s", flush=True)
        time.sleep(max(0, a.pause - (time.time() - t0)))


if __name__ == "__main__":
    main()
