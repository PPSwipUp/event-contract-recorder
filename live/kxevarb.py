"""Read-only scan of EVERY open mutually exclusive Kalshi event for locked-in packages (any category).

For an event whose markets are mutually exclusive (at most one resolves YES), with n markets:
  ALL_NO   buy NO in every market: pays at least n-1.        Safe from exclusivity alone.
  ALL_YES  buy YES in every market: pays 1 only if one of them MUST win (the set is exhaustive).  Flagged
           'exhaustive' only when the strikes provably cover the whole line (a 'less' tail, contiguous
           'between' brackets, a 'greater' tail); otherwise logged as 'check' and not counted.
Priced at each leg's best ask, size = smallest best-ask size, Kalshi taker fee per leg for that size with the
series' fee multiplier.  Logs every package with locked profit > 0 to kxevarb.jsonl.  Never places orders.
  python live/kxevarb.py --hours 24 --pause 120
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backfill"))
import dohfix  # noqa: F401,E402
from arbscan import books, kget  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
FEE_MULT = {}


def fee_c(p, n, mult):
    return math.ceil(7 * mult * n * p * (1 - p)) / n


def mult(series):
    if series not in FEE_MULT:
        try:
            s = kget(f"/series/{series}")["series"]
            FEE_MULT[series] = float(s.get("fee_multiplier") or 1) if s.get("fee_type") != "flat" else 1.0
        except Exception:
            FEE_MULT[series] = 1.0
    return FEE_MULT[series]


def events():
    out, cur = [], None
    while True:
        p = {"status": "open", "with_nested_markets": "true", "limit": 200}
        if cur:
            p["cursor"] = cur
        d = kget("/events", **p)
        for e in d.get("events", []):
            ms = [m for m in e.get("markets") or [] if m.get("status") in ("active", "open")]
            if e.get("mutually_exclusive") and len(ms) >= 2:
                out.append((e, ms))
        cur = d.get("cursor")
        if not cur or not d.get("events"):
            return out


def exhaustive(ms):
    """strikes cover (-inf, inf): one 'less' tail, contiguous 'between' brackets, one 'greater' tail"""
    try:
        lo = [m for m in ms if m.get("strike_type") == "less"]
        hi = [m for m in ms if m.get("strike_type") == "greater"]
        mid = sorted((float(m["floor_strike"]), float(m["cap_strike"])) for m in ms if m.get("strike_type") == "between")
        if len(lo) != 1 or len(hi) != 1 or len(mid) + 2 != len(ms):
            return False
        edges = [float(lo[0]["cap_strike"])] + [x for b in mid for x in b] + [float(hi[0]["floor_strike"])]
        return all(abs(edges[i + 1] - edges[i]) <= 1.0001 for i in range(0, len(edges) - 1, 2))
    except (TypeError, ValueError, KeyError):
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=float, default=24)
    ap.add_argument("--pause", type=float, default=120)
    a = ap.parse_args()
    out = os.path.join(HERE, "kxevarb.jsonl")
    stop, scans = time.time() + 3600 * a.hours, 0
    while time.time() < stop:
        t0 = time.time()
        try:
            E = events()
            Q = books(sorted({m["ticker"] for _, ms in E for m in ms}))
        except Exception as err:
            print(datetime.now(timezone.utc).strftime("%H:%M"), "scan error", repr(err)[:150], flush=True)
            time.sleep(60)
            continue
        hits = 0
        for e, ms in E:
            q = [Q.get(m["ticker"]) for m in ms]
            if any(x is None for x in q):
                continue
            fm = mult(e["series_ticker"])
            n_mk = len(ms)
            for kind, legs, pay in (("ALL_NO", [(x[2], x[3]) for x in q], n_mk - 1), ("ALL_YES", [(x[0], x[1]) for x in q], 1)):
                if any(p is None or s <= 0 for p, s in legs):
                    continue
                size = int(min(s for _, s in legs))
                if size < 1:
                    continue
                edge = 100 * pay - sum(100 * p + fee_c(p, size, fm) for p, _ in legs)
                if edge > 0:
                    hits += 1
                    with open(out, "a") as f:
                        f.write(json.dumps({"t": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                            "event": e["event_ticker"], "category": e.get("category"), "kind": kind,
                                            "n": n_mk, "edge_c": round(edge, 2), "size": size,
                                            "profit_$": round(edge * size / 100, 2), "fee_mult": fm,
                                            "safe": kind == "ALL_NO" or exhaustive(ms)}) + "\n")
        scans += 1
        print(datetime.now(timezone.utc).strftime("%H:%M"), f"scan {scans}: {len(E)} exclusive events, "
              f"{sum(len(ms) for _, ms in E)} markets, {hits} positive packages, {time.time() - t0:.0f}s", flush=True)
        time.sleep(max(0, a.pause - (time.time() - t0)))


if __name__ == "__main__":
    main()
