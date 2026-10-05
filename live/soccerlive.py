"""Live soccer 1X2 gap scanner, Polymarket international and Polymarket US.  Read-only: never places orders.

A full-time 1X2 set (home win / draw / away win) is exclusive AND exhaustive, so at any instant:
  SELL_ALL  sell YES in all three at the best bids (= buy NO at 1 - bid): pays out exactly 1 per set, so profit =
            sum(bids) - 1 - fees.   BUY_ALL  buy YES in all three at the best asks: pays 1, profit = 1 - sum(asks) - fees.
Every --every seconds, for matches from 15 min before kick-off to 2.5 h after: read all three books of a match
together (intl: ONE /books request for every live match; US: the three books in parallel), and log any positive
package with its size (smallest of the three best-level sizes), then re-read that match 1 s later ("catchable").
Fees: intl = the market's feeSchedule rate x p(1-p) per share; US = 0.0695 x p(1-p) per contract.
  python live/soccerlive.py --venue intl     |     python live/soccerlive.py --venue us
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import requests

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backfill"))
import dohfix  # noqa: F401,E402

HERE = os.path.dirname(os.path.abspath(__file__))
S = requests.Session()
S.headers["User-Agent"] = "Mozilla/5.0"
US_LEAGUES = ["epl", "lal", "bun", "sea", "mls", "uefa", "ucl", "cham", "fwc", "flc", "nb1"]


def jget(url, **p):
    for attempt in range(3):
        try:
            r = S.get(url, params=p, timeout=20)
            if r.status_code == 200:
                return r.json()
        except requests.RequestException:
            pass
        time.sleep(1 + attempt)
    return None


def ts(x):
    return datetime.fromisoformat(x.replace("Z", "+00:00")) if x else None


# ---------- match lists: [(match id, start, [(leg name, key, fee rate), x3])] ----------
def intl_matches():
    out, cur = [], None
    while True:
        d = jget("https://gamma-api.polymarket.com/events/keyset", active="true", closed="false", limit=500, tag_slug="soccer",
                 **({"after_cursor": cur} if cur else {})) or {}
        for e in d.get("events", []):
            ms = [m for m in e.get("markets") or [] if m.get("clobTokenIds") and not m.get("closed")]
            if not e.get("negRisk") or len(ms) != 3 or not any("draw" in m["question"].lower() for m in ms):
                continue
            st = ts(e.get("startTime") or (ms[0].get("gameStartTime") or "").replace(" ", "T") or None)
            legs = [(m["question"][:40], json.loads(m["clobTokenIds"])[0],
                     float((m.get("feeSchedule") or {}).get("rate") or 0) if m.get("feesEnabled") else 0.0) for m in ms]
            out.append((e["slug"], st, legs))
        cur = d.get("next_cursor")
        if not cur or not d.get("events"):
            return out


def us_matches():
    out = []
    for lg in US_LEAGUES:
        d = jget(f"https://gateway.polymarket.us/v2/leagues/{lg}/events", limit=100) or {}
        for e in d.get("events", []):
            ms = [m for m in e.get("markets") or [] if m.get("sportsMarketType") == "soccer_team_full_time_winner"]
            if e.get("closed") or len(ms) != 3:
                continue
            out.append((e["slug"], ts(e.get("startTime")), [(m["slug"][-12:], m["slug"], 0.0695) for m in ms]))
    return out


# ---------- books: {key: (bid, bid size, ask, ask size)} ----------
def intl_books(keys):
    out = {}
    for i in range(0, len(keys), 300):
        try:
            r = S.post("https://clob.polymarket.com/books", json=[{"token_id": k} for k in keys[i:i + 300]], timeout=20).json()
        except (requests.RequestException, ValueError):
            continue
        for b in r if isinstance(r, list) else []:
            bids = [(float(x["price"]), float(x["size"])) for x in b.get("bids", [])]
            asks = [(float(x["price"]), float(x["size"])) for x in b.get("asks", [])]
            bb, ba = max(bids, default=(None, 0)), min(asks, default=(None, 0))
            out[b["asset_id"]] = (bb[0], bb[1], ba[0], ba[1])
    return out


def us_book(slug):
    d = (jget(f"https://gateway.polymarket.us/v1/markets/{slug}/book") or {}).get("marketData") or {}
    b = [(float(x["px"]["value"]), float(x["qty"])) for x in d.get("bids") or []]
    a = [(float(x["px"]["value"]), float(x["qty"])) for x in d.get("offers") or []]
    bb, ba = max(b, default=(None, 0)), min(a, default=(None, 0))
    return slug, (bb[0], bb[1], ba[0], ba[1])


def us_books(keys):
    with ThreadPoolExecutor(12) as ex:
        return dict(ex.map(us_book, keys))


def packages(legs, Q):
    """-> list of (kind, edge in cents per set after fees, size)"""
    q = [Q.get(k) for _, k, _ in legs]
    if any(x is None for x in q):
        return []
    out = []
    if all(x[0] is not None for x in q):
        edge = 100 * (sum(x[0] for x in q) - 1 - sum(r * x[0] * (1 - x[0]) for (_, _, r), x in zip(legs, q)))
        if edge > 0:
            out.append(("SELL_ALL", round(edge, 3), min(x[1] for x in q)))
    if all(x[2] is not None for x in q):
        edge = 100 * (1 - sum(x[2] for x in q) - sum(r * x[2] * (1 - x[2]) for (_, _, r), x in zip(legs, q)))
        if edge > 0:
            out.append(("BUY_ALL", round(edge, 3), min(x[3] for x in q)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--venue", choices=["intl", "us"], required=True)
    ap.add_argument("--every", type=float, default=2)
    ap.add_argument("--hours", type=float, default=96)
    a = ap.parse_args()
    find, books = (intl_matches, intl_books) if a.venue == "intl" else (us_matches, us_books)
    log = os.path.join(HERE, f"soccerlive_{a.venue}.jsonl")
    stop, M, refreshed, polls = time.time() + 3600 * a.hours, [], 0, 0
    while time.time() < stop:
        now = datetime.now(timezone.utc)
        if time.time() - refreshed > 900:
            try:
                M, refreshed = find(), time.time()
            except Exception as err:                                        # network outage (curfew): retry later
                print(now.strftime("%H:%M"), "match list error", repr(err)[:100], flush=True)
        live = [m for m in M if m[1] and m[1] - timedelta(minutes=15) <= now <= m[1] + timedelta(hours=2.5)]
        if not live:
            time.sleep(60)
            continue
        t0 = time.time()
        Q = books([k for _, _, legs in live for _, k, _ in legs])
        polls += 1
        for mid, st, legs in live:
            for kind, edge, size in packages(legs, Q):
                time.sleep(1)
                again = [p for p in packages(legs, books([k for _, k, _ in legs])) if p[0] == kind]
                rec = {"t": now.isoformat(timespec="seconds"), "match": mid, "minute": round((now - st).total_seconds() / 60, 1),
                       "kind": kind, "edge_c": edge, "size": size, "profit_$": round(edge * size / 100, 2),
                       "catchable_1s": list(again[0][1:]) if again else None,
                       "legs": {n: Q.get(k) for n, k, _ in legs}}
                with open(log, "a") as f:
                    f.write(json.dumps(rec) + "\n")
                print(now.strftime("%H:%M:%S"), mid, kind, edge, "c x", size, "-> 1 s later:", rec["catchable_1s"], flush=True)
        if polls % 300 == 1:
            print(now.strftime("%H:%M:%S"), f"poll {polls}: {len(live)} live matches, {len(Q)} books, {time.time() - t0:.1f}s", flush=True)
        time.sleep(max(0.2, a.every - (time.time() - t0)))


if __name__ == "__main__":
    main()
