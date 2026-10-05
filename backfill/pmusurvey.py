"""Polymarket US liquidity incentives: what would X contracts per side at the best bid and best offer earn now?

Rules (docs.polymarket.us/incentives/liquidity): each second, per side, walk from the best price outward until
Target Size; orders inside score Discount^(ticks from best) x size; each side's score is normalised to 1.0 (so each
side gets half of that second's pool) and pays only if the side reaches Target Size; with a Max Spread, both sides
must reach Target Size with their size-adjusted prices within Max Spread of their midpoint, else nobody is paid.
Our order joins the BACK of the queue at the best price (others at that price are walked first: conservative).
One snapshot treated as typical for the period.  Rewards only, no fills.  Public endpoints, no account needed.
  python backfill/pmusurvey.py --size 500
"""
from __future__ import annotations

import argparse
import time

import pandas as pd
import requests

import dohfix  # noqa: F401

S = requests.Session()
S.headers["User-Agent"] = "Mozilla/5.0"
HOURS = {"daily_event": 24.0}


def jget(url, **p):
    for attempt in range(6):
        try:
            r = S.get(url, params=p, timeout=30)
            if r.status_code == 200:
                return r.json()
            if r.status_code == 404:
                return None
        except requests.RequestException:
            pass
        time.sleep(min(20, 2 ** attempt))
    raise RuntimeError(url)


def programs():
    out, tok = [], None
    while True:
        q = {"pageSize": 200, "statuses": "active", "programType": "liquidityProgram"}
        if tok:
            q["pageToken"] = tok
        d = jget("https://api.prod.polymarketexchange.com/v1/incentives", **q)
        out += d.get("programs", [])
        tok = d.get("nextPageToken")
        if len(out) % 2000 == 0:
            print(time.strftime("%H:%M:%S"), "programs", len(out), flush=True)
        if not tok or not d.get("programs"):
            return out


def book(slug):
    d = (jget(f"https://gateway.polymarket.us/v1/markets/{slug}/book") or {}).get("marketData", {})
    side = lambda k: [(float(x["px"]["value"]), float(x["qty"])) for x in d.get(k) or []]
    return sorted(side("bids"), reverse=True), sorted(side("offers"))


def walk(levels, target, disc, ours, tick, sign):
    """levels best first; returns (others' score, our score, size-adjusted price or None if target not reached)"""
    if not levels:
        lv = [(None, ours, True)]
    else:
        lv = [(levels[0][0], levels[0][1], False), (levels[0][0], ours, True)] + [(p, q, False) for p, q in levels[1:]]
    best = lv[0][0]
    comp = mine = cum = 0.0
    adj = None
    for p, q, is_ours in lv:
        take = min(q, target - cum)
        if take <= 0:
            break
        n = 0 if p is None or best is None else round(sign * (best - p) / tick)
        w = disc ** n * take
        mine, comp = (mine + w, comp) if is_ours else (mine, comp + w)
        cum += take
        if cum >= target - 1e-9:
            adj = p
            break
    return comp, mine, adj


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", type=float, default=500)
    ap.add_argument("--tick", type=float, default=0.01)
    ap.add_argument("--top", type=int, default=500, help="books fetched for the N largest pools only")
    a = ap.parse_args()
    rows = []
    P = programs()
    act = []
    for pr in P:
        tp = next((t for t in pr.get("timePeriods", []) if t.get("status") == "active" and t.get("programType") == "liquidityProgram"), None)
        if tp:
            act.append((float(tp["rewardPool"]), pr, tp))
    act.sort(key=lambda x: -x[0])
    T = pd.DataFrame([{"pool": x[0], "period": x[2].get("period"), "cat": f'{x[1].get("category")}/{x[1].get("subcategory")}'} for x in act])
    print("active liquidity programs:", len(act), "periods:", T.period.value_counts().to_dict(), flush=True)
    for i, (_, pr, tp) in enumerate(act[:a.top]):
        if i % 100 == 0:
            print(time.strftime("%H:%M:%S"), "books", i, flush=True)
        bids, offers = book(pr["marketSlug"])
        tgt, disc = float(tp["targetSize"]), float(tp["discountFactor"])
        cb, mb, ab = walk(bids, tgt, disc, a.size, a.tick, +1)
        co, mo, ao = walk(offers, tgt, disc, a.size, a.tick, -1)
        sb = mb / (mb + cb) if ab is not None and mb + cb > 0 else 0.0
        so = mo / (mo + co) if ao is not None and mo + co > 0 else 0.0
        ms = tp.get("maxSpread")
        if ms is not None and (ab is None or ao is None or (ao - ab) / 2 > float(ms) + 1e-9):
            sb = so = 0.0
        hours = HOURS.get(tp.get("period"))
        rows.append({"market": pr["marketSlug"], "cat": f'{pr.get("category")}/{pr.get("subcategory")}', "period": tp.get("period"),
                     "pool": float(tp["rewardPool"]), "target": tgt, "disc": disc, "max_spread": ms,
                     "best_bid": bids[0][0] if bids else None, "best_offer": offers[0][0] if offers else None,
                     "share_bid": round(sb, 3), "share_offer": round(so, 3),
                     "usd_per_h": round(float(tp["rewardPool"]) * (sb + so) / 2 / hours, 3) if hours else None})
    R = pd.DataFrame(rows)
    R.to_parquet("data_local/pmusurvey.parquet")
    known = R.dropna(subset=["usd_per_h"]).sort_values("usd_per_h", ascending=False)
    g = known.groupby("cat").agg(markets=("market", "size"), pool_per_day=("pool", "sum"), our_usd_per_h=("usd_per_h", "sum")).sort_values("our_usd_per_h", ascending=False)
    L = [f"# Polymarket US liquidity incentives: reward share for {a.size:.0f} contracts at best bid + best offer (snapshot)", "",
         f"Active liquidity programs: {len(T)}; period types: {T.period.value_counts().to_dict()}",
         f"All pools by period type ($): {T.groupby('period').pool.sum().round(0).to_dict()}",
         f"Pools by category ($, top 10): {T.groupby('cat').pool.sum().sort_values(ascending=False).head(10).round(0).to_dict()}", "",
         f"Books priced for the {len(R)} largest pools. Our share if quoting all of those with a known period length: "
         f"${known.usd_per_h.sum():.2f}/h (rewards only, before fills; capital ~ {a.size:.0f} x 2 x markets)", "",
         "## By category", "", g.head(15).round(2).to_markdown(), "", "## Top markets", "",
         known.head(20).to_markdown(index=False), ""]
    open("../results/PMUS_LIP.md", "w").write("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    main()
