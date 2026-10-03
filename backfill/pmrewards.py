"""Polymarket liquidity-rewards scan: for every active market with a daily reward pool, how much of the pool would a
quote of X shares per side earn, given the competing orders in the book right now?

Scoring (docs.polymarket.com/programs/liquidity-rewards): an order at distance s (cents) from the midpoint, within
the market's max spread v and at least the min size, scores ((v - s) / v)^2 x size; per sample a maker's score is
min(bid-side, ask-side) (single-sided counts /3 when 0.10 <= mid <= 0.90); the daily pool is split by score share.
Approximation used here: competitors' total score = mean of the two sides' scores of every qualifying order in the
book (one snapshot, treated as typical for the day).  Our quote: X shares bid and X shares ask, `d` cents from mid.
Capital tied up ~ X dollars (bid X at mid-d plus the opposite side X at 1-mid-d).
  python backfill/pmrewards.py --size 500 --dist 1
"""
from __future__ import annotations

import argparse
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import requests

import dohfix  # noqa: F401

S = requests.Session()
OUT = "data_local/pmrewards"


def markets():
    out, off = [], 0
    while True:
        r = S.get("https://gamma-api.polymarket.com/markets", timeout=60,
                  params={"active": "true", "closed": "false", "limit": 500, "offset": off}).json()
        if not isinstance(r, list) or not r:            # gamma returns an error object past its offset cap
            if not isinstance(r, list):
                print("gamma stopped at offset", off, str(r)[:120], flush=True)
            return out
        off += 500
        for m in r:
            rate = sum(float(c.get("rewardsDailyRate") or 0) for c in (m.get("clobRewards") or []))
            if rate > 0 and m.get("clobTokenIds") and m.get("enableOrderBook"):
                out.append({"cid": m["conditionId"], "question": m["question"], "slug": m.get("slug"),
                            "token": json.loads(m["clobTokenIds"])[0], "rate": rate,
                            "min_size": float(m.get("rewardsMinSize") or 0), "max_spread": float(m.get("rewardsMaxSpread") or 0),
                            "end": m.get("endDate"), "vol24": float(m.get("volume24hr") or 0),
                            "holding": bool(m.get("holdingRewardsEnabled")), "category": m.get("category")})


def book(token):
    for attempt in range(5):
        try:
            r = S.get("https://clob.polymarket.com/book", params={"token_id": token}, timeout=20)
            if r.status_code == 200:
                return r.json()
        except requests.RequestException:
            pass
        time.sleep(1 + attempt)
    return None


def score(m, b, size, dist):
    bids = [(float(x["price"]), float(x["size"])) for x in b.get("bids", [])]
    asks = [(float(x["price"]), float(x["size"])) for x in b.get("asks", [])]
    if not bids or not asks:
        return None
    bb, ba = max(p for p, _ in bids), min(p for p, _ in asks)
    mid, v = (bb + ba) / 2, m["max_spread"]

    def side(levels):
        return sum(((v - abs(p - mid) * 100) / v) ** 2 * q for p, q in levels
                   if abs(p - mid) * 100 < v and q >= m["min_size"])
    q_bid, q_ask = side(bids), side(asks)
    comp = (q_bid + q_ask) / 2
    ours = ((v - dist) / v) ** 2 * size if dist < v and size >= m["min_size"] else 0.0
    if not 0.10 <= mid <= 0.90:
        pass                                   # two-sided required; we are two-sided, nothing changes
    share = ours / (ours + comp) if ours + comp > 0 else 0.0
    return {"mid": round(mid, 4), "spread_c": round((ba - bb) * 100, 2), "comp_score": round(comp), "share": round(share, 4),
            "reward_day_$": round(share * m["rate"], 2), "yield_day_%": round(100 * share * m["rate"] / size, 3)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", type=float, default=500)
    ap.add_argument("--dist", type=float, default=1.0, help="cents from the midpoint for our bid and ask")
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    M = markets()
    print(len(M), "markets with reward pools, total $", round(sum(m["rate"] for m in M)), "per day", flush=True)
    with ThreadPoolExecutor(8) as ex:
        books = list(ex.map(lambda m: book(m["token"]), M))
    rows = []
    for m, b in zip(M, books):
        s = score(m, b, a.size, a.dist) if b else None
        if s:
            rows.append({**m, **s})
    R = pd.DataFrame(rows).sort_values("reward_day_$", ascending=False)
    stamp = time.strftime("%Y%m%d_%H%M")
    R.to_parquet(f"{OUT}/scan_{stamp}.parquet")
    cols = ["question", "rate", "max_spread", "min_size", "mid", "spread_c", "comp_score", "share", "reward_day_$", "vol24", "end"]
    print(R[cols].head(30).to_string(index=False))
    print("\nsum of top-20 rewards/day at", a.size, "shares each:", R["reward_day_$"].head(20).sum())


if __name__ == "__main__":
    main()
