"""Live, read-only cross-venue arbitrage check: Polymarket "Bitcoin/Ethereum above $K on <date>" (noon ET) vs Kalshi
KXBTCD/KXETHD hourly "above K-0.01" for the same noon close.  Kalshi's noon event exists only from 11:00 ET, so
each day it polls both order books every few seconds from 11:00 to 12:00 ET and prices the two locked packages
per matched strike:
  A  PM YES + Kalshi NO      B  PM NO + Kalshi YES        (each pays $1 if both venues settle the same way)
at the best ask of each leg, size = smaller of the two best-ask sizes, Kalshi taker fee for that size and the
Polymarket taker fee (0.07 * p * (1-p) per share, the crypto fee schedule).  Logs every poll's best package per
strike to xvlive.jsonl (positive or not) so the gap distribution is visible.  Never places orders.
  python live/xvlive.py --days 7
"""
from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timedelta

import sys

import requests

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backfill"))
import dohfix  # noqa: F401,E402  (EE hotspot DNS block)
from arbscan import ET, books, event, fee_c, kget

HERE = os.path.dirname(os.path.abspath(__file__))
PM = requests.Session()
ASSETS = {"bitcoin": "KXBTCD", "ethereum": "KXETHD"}


def pm_markets(asset, day):
    slug = f"{asset}-above-on-{day:%B}-{day.day}-{day.year}".lower()
    r = PM.get("https://gamma-api.polymarket.com/events", params={"slug": slug}, timeout=30).json()
    out = {}
    for m in (r[0]["markets"] if r else []):
        K = float(m["question"].split("$")[1].split(" ")[0].replace(",", ""))
        out[K] = json.loads(m["clobTokenIds"])                       # [yes, no]
    return out


def pm_asks(tokens):
    """{token: (best ask, size)}"""
    r = PM.post("https://clob.polymarket.com/books", json=[{"token_id": t} for t in tokens], timeout=20).json()
    out = {}
    for b in r:
        asks = [(float(a["price"]), float(a["size"])) for a in b.get("asks", [])]
        out[b["asset_id"]] = min(asks) if asks else (None, 0)
    return out


def pm_fee(p):
    return 100 * 0.07 * p * (1 - p)


def run_window(day, out):
    noon = datetime(day.year, day.month, day.day, 12, tzinfo=ET)
    pairs = []
    for asset, series in ASSETS.items():
        pm = pm_markets(asset, day)
        km = kget("/markets", event_ticker=event(series, noon), limit=1000).get("markets", [])
        kt = {round(float(m["floor_strike"]) + 0.01): m["ticker"] for m in km if m.get("floor_strike") is not None}
        pairs += [(asset, K, toks, kt[round(K)]) for K, toks in pm.items() if round(K) in kt]
    print(day, "matched strikes", len(pairs), flush=True)
    n = 0
    while datetime.now(ET) < noon and pairs:
        now = datetime.now(ET)
        try:
            P = pm_asks([t for _, _, toks, _ in pairs for t in toks])
            Q = books([k for *_, k in pairs])
        except Exception as e:
            print(now.strftime("%H:%M:%S"), "error", repr(e)[:120], flush=True)
            time.sleep(5)
            continue
        with open(out, "a") as f:
            for asset, K, (ty, tn), k in pairs:
                if k not in Q:
                    continue
                ky, kys, kn, kns = Q[k]
                for kind, (pp, ps), (kp, ks) in (("A", P.get(ty, (None, 0)), (kn, kns)), ("B", P.get(tn, (None, 0)), (ky, kys))):
                    if pp is None or kp is None or ps <= 0 or ks <= 0:
                        continue
                    size = int(min(ps, ks))
                    if size < 1:
                        continue
                    edge = 100 - 100 * pp - 100 * kp - fee_c(kp, size) - pm_fee(pp)
                    f.write(json.dumps({"t": now.isoformat(), "asset": asset, "strike": K, "kind": kind,
                                        "pm_ask": pp, "pm_size": ps, "k_ask": kp, "k_size": ks,
                                        "size": size, "edge_c": round(edge, 2)}) + "\n")
        n += 1
        if n % 60 == 0:
            print(now.strftime("%H:%M:%S"), "polls", n, flush=True)
        time.sleep(max(0, 5 - (datetime.now(ET) - now).total_seconds()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--out", default=os.path.join(HERE, "xvlive.jsonl"))
    a = ap.parse_args()
    for _ in range(a.days):
        now = datetime.now(ET)
        day = now.date() if now.hour < 12 else now.date() + timedelta(days=1)
        start = datetime(day.year, day.month, day.day, 11, 0, 20, tzinfo=ET)
        if now < start:
            time.sleep((start - now).total_seconds())
        try:
            run_window(day, a.out)
        except Exception as e:
            print(day, "window failed", repr(e)[:150], flush=True)
        time.sleep(120)


if __name__ == "__main__":
    main()
