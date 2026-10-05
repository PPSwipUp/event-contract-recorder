"""Record Polymarket US order books for markets in an active liquidity-incentive period (read-only, public API).

For each game in --games, take every market with an incentive program; every --every seconds, while that market's
"day_of" period is running (6 h before eventStartTime until the start) or, with --live, its "live" period (start until
--live-hours after), fetch its book (top 10 levels each side + last trade stats) and append it to
live/pmusrec/YYYY-MM-DD.jsonl.  Programs (pool, target, discount, max spread) saved alongside.
  python live/pmusrec.py --games mlb-cws-cle-2026-10-05,mlb-nyy-tb-2026-10-05
"""
from __future__ import annotations

import argparse
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import pandas as pd
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
S = requests.Session()
S.headers["User-Agent"] = "Mozilla/5.0"


def jget(url, **p):
    for attempt in range(4):
        try:
            r = S.get(url, params=p, timeout=20)
            if r.status_code == 200:
                return r.json()
            if r.status_code == 404:
                return None
        except requests.RequestException:
            pass
        time.sleep(1 + 2 * attempt)
    return None


def programs(game):
    rows, tok = [], None
    while True:
        q = {"pageSize": 200, "statuses": "active", "programType": "liquidityProgram", "query": game}
        if tok:
            q["pageToken"] = tok
        d = jget("https://api.prod.polymarketexchange.com/v1/incentives", **q) or {}
        for p in d.get("programs", []):
            for t in p["timePeriods"]:
                rows.append({"slug": p["marketSlug"], "start": pd.Timestamp(p["eventStartTime"]).timestamp(), "program": t["programId"],
                             "period": t["period"], "pool": t["rewardPool"], "target": t["targetSize"], "disc": t["discountFactor"],
                             "max_spread": t.get("maxSpread")})
        tok = d.get("nextPageToken")
        if not tok or not d.get("programs"):
            return rows


def book(slug):
    d = (jget(f"https://gateway.polymarket.us/v1/markets/{slug}/book") or {}).get("marketData")
    if not d:
        return None
    lv = lambda k: [[float(x["px"]["value"]), float(x["qty"])] for x in (d.get(k) or [])][:10]
    st = d.get("stats") or {}
    return {"slug": slug, "ts": round(time.time(), 1), "bids": lv("bids"), "offers": lv("offers"), "state": d.get("state"),
            "shares_traded": st.get("sharesTraded"), "last_px": (st.get("lastTradePx") or {}).get("value"),
            "last_qty": st.get("lastTradeQty"), "last_t": st.get("lastTradeSetTime")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", required=True)
    ap.add_argument("--every", type=float, default=60)
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--live-hours", type=float, default=4)
    a = ap.parse_args()
    out_dir = os.path.join(HERE, "pmusrec")
    os.makedirs(out_dir, exist_ok=True)
    P = pd.DataFrame([r for g in a.games.split(",") for r in programs(g)])
    P.to_csv(os.path.join(out_dir, f"programs_{datetime.now(timezone.utc):%Y%m%d_%H%M}.csv"), index=False)
    starts = P.groupby("slug").start.first()
    print(len(starts), "markets;", P.groupby("period").program.nunique().to_dict(), flush=True)
    end = starts.max() + (a.live_hours * 3600 if a.live else 0)
    while time.time() < end:
        t0 = time.time()
        on = [s for s, st in starts.items() if st - 6 * 3600 <= t0 < st or (a.live and st <= t0 < st + a.live_hours * 3600)]
        if on:
            with ThreadPoolExecutor(4) as ex:
                res = [r for r in ex.map(book, on) if r]
            with open(os.path.join(out_dir, f"{datetime.now(timezone.utc):%Y-%m-%d}.jsonl"), "a") as f:
                for r in res:
                    f.write(json.dumps(r) + "\n")
            print(datetime.now(timezone.utc).strftime("%H:%M:%S"), "books", len(res), "/", len(on), f"{time.time() - t0:.0f}s", flush=True)
        time.sleep(max(1, a.every - (time.time() - t0)))


if __name__ == "__main__":
    main()
