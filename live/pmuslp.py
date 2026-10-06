"""Polymarket US paper liquidity provider on non-sports daily reward programs (results/PLAN_PMUSLP.md).
Read-only, public endpoints only: never places orders.
  python live/pmuslp.py --tag _join            |   python live/pmuslp.py --tag _back --back
"""
from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timedelta, timezone

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
S = requests.Session()
S.headers["User-Agent"] = "Mozilla/5.0"
GW, INC = "https://gateway.polymarket.us", "https://api.prod.polymarketexchange.com/v1/incentives"


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


def programs():
    """{slug: program dict incl. n (markets in its program)} for active non-sports daily liquidity programs"""
    rows, tok = [], None
    while True:
        q = {"pageSize": 200, "statuses": "active", "programType": "liquidityProgram"}
        if tok:
            q["pageToken"] = tok
        d = jget(INC, **q)
        if d is None:
            raise RuntimeError("incentives list unavailable")
        for p in d.get("programs", []):
            if p.get("category") == "SPR":
                continue
            for t in p["timePeriods"]:
                if t.get("status") == "active" and t.get("period") in ("daily", "daily_event"):
                    rows.append({"slug": p["marketSlug"], "program": t["programId"], "pool": float(t["rewardPool"]),
                                 "target": float(t["targetSize"]), "disc": float(t["discountFactor"]),
                                 "max_spread": float(t["maxSpread"]) if t.get("maxSpread") else None,
                                 "start": p.get("eventStartTime"), "sub": p.get("subcategory")})
        tok = d.get("nextPageToken")
        if not tok or not d.get("programs"):
            break
    n = {}
    for r in rows:
        n[r["program"]] = n.get(r["program"], 0) + 1
    return {r["slug"]: {**r, "n": n[r["program"]]} for r in rows}


def book(slug):
    d = (jget(f"{GW}/v1/markets/{slug}/book") or {}).get("marketData")
    if not d:
        return None
    lv = lambda k: [(float(x["px"]["value"]), float(x["qty"])) for x in (d.get(k) or [])]
    return {"bids": sorted(lv("bids"), reverse=True), "offers": sorted(lv("offers")),
            "traded": float((d.get("stats") or {}).get("sharesTraded") or 0)}


def tick_of(slug):
    m = (jget(f"{GW}/v1/market/slug/{slug}") or {}).get("market") or {}
    return float(m.get("orderPriceMinTickSize") or 0.01)


def walk(levels, ours_px, size, target, disc, tick, bid):
    """(our share of this side, size-adjusted price or None); our order at the back of its price level"""
    better = (lambda p: p >= ours_px - 1e-9) if bid else (lambda p: p <= ours_px + 1e-9)
    lv = [(p, q, False) for p, q in levels if better(p)] + [(ours_px, size, True)] + [(p, q, False) for p, q in levels if not better(p)]
    best = lv[0][0]
    mine = comp = cum = 0.0
    adj = None
    for p, q, me in lv:
        take = min(q, target - cum)
        if take <= 0:
            break
        w = disc ** round(abs(best - p) / tick) * take
        mine, comp = (mine + w, comp) if me else (mine, comp + w)
        cum += take
        if cum >= target - 1e-9:
            adj = p
            break
    return (mine / (mine + comp) if adj is not None and mine + comp > 0 else 0.0), adj


def choose(P, k=20):
    now = datetime.now(timezone.utc)
    ranked = sorted(P.values(), key=lambda r: -r["pool"] / r["n"])
    out = []
    for r in ranked:
        if len(out) >= k:
            break
        st = r["start"] and datetime.fromisoformat(r["start"].replace(" ", "T").replace("Z", "+00:00"))
        if st and st - now <= timedelta(days=14):
            continue
        b = book(r["slug"])
        if not b or not b["bids"] or not b["offers"]:
            continue
        mid = (b["bids"][0][0] + b["offers"][0][0]) / 2
        if 0.10 <= mid <= 0.90:
            out.append({**r, "tick": tick_of(r["slug"])})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--back", action="store_true", help="quote one tick behind the best price")
    ap.add_argument("--size", type=float, default=1000)
    ap.add_argument("--every", type=float, default=30)
    ap.add_argument("--hours", type=float, default=24 * 14)
    a = ap.parse_args()
    sp, logp = os.path.join(HERE, f"pmuslp{a.tag}_state.json"), os.path.join(HERE, f"pmuslp{a.tag}.jsonl")
    fillp, midp = os.path.join(HERE, f"pmuslp{a.tag}_fills.jsonl"), os.path.join(HERE, f"pmuslp{a.tag}_mids.jsonl")
    try:
        st = json.load(open(sp))
    except (OSError, ValueError):
        mk = choose(programs())
        st = {"markets": mk, "pos": {m["slug"]: {"inv": 0.0, "cash": 0.0, "reward": 0.0, "rebate": 0.0, "fills": 0,
                                                    "bid": None, "offer": None, "traded": None, "cool_bid": 0, "cool_offer": 0,
                                                    "mid": None} for m in mk}}
        json.dump(st, open(sp, "w"))
    print(len(st["markets"]), "markets:", [m["slug"] for m in st["markets"]], flush=True)
    stop, last, prog_t = time.time() + 3600 * a.hours, time.time(), time.time()
    while time.time() < stop:
        t0 = time.time()
        gap = t0 - last > 300
        dt = min(t0 - last, 90)
        last = t0
        if t0 - prog_t > 3600:                                   # refresh program sizes (n markets, pool) hourly
            try:
                P = programs()
                for m in st["markets"]:
                    if m["slug"] in P:
                        m.update({k: P[m["slug"]][k] for k in ("pool", "n", "target", "disc", "max_spread")})
                prog_t = t0
            except Exception as err:
                print(datetime.now(timezone.utc).strftime("%H:%M"), "programs refresh failed", repr(err)[:100], flush=True)
        mids = []
        for m in st["markets"]:
            p = st["pos"][m["slug"]]
            try:
                b = book(m["slug"])
                if not b or not b["bids"] or not b["offers"]:
                    p["bid"] = p["offer"] = None
                    continue
                bb, bo = b["bids"][0][0], b["offers"][0][0]
                mid = (bb + bo) / 2
                traded = b["traded"] > (p["traded"] or b["traded"])
                # 1) fills of the quotes that rested since the last loop (never across an outage gap)
                if not gap and traded:
                    if p["bid"] is not None and bb < p["bid"] - 1e-9:
                        p["inv"] += a.size; p["cash"] -= a.size * p["bid"]; p["fills"] += 1; p["cool_bid"] = t0 + 300
                        p["rebate"] += 0.0125 * a.size * p["bid"] * (1 - p["bid"])
                        open(fillp, "a").write(json.dumps({"ts": round(t0), "slug": m["slug"], "side": "buy", "px": p["bid"], "mid_before": p["mid"], "mid_now": mid}) + "\n")
                    if p["offer"] is not None and bo > p["offer"] + 1e-9:
                        p["inv"] -= a.size; p["cash"] += a.size * p["offer"]; p["fills"] += 1; p["cool_offer"] = t0 + 300
                        p["rebate"] += 0.0125 * a.size * p["offer"] * (1 - p["offer"])
                        open(fillp, "a").write(json.dumps({"ts": round(t0), "slug": m["slug"], "side": "sell", "px": p["offer"], "mid_before": p["mid"], "mid_now": mid}) + "\n")
                p["traded"], p["mid"] = b["traded"], mid
                mids.append([m["slug"], round(mid, 4)])
                # 2) new quotes, unless the market left the frozen bounds
                st_ = m["start"] and datetime.fromisoformat(m["start"].replace(" ", "T").replace("Z", "+00:00"))
                ok = 0.10 <= mid <= 0.90 and not (st_ and st_ - datetime.now(timezone.utc) <= timedelta(days=14))
                off = m["tick"] if a.back else 0.0
                p["bid"] = round(bb - off, 4) if ok and t0 >= p["cool_bid"] and p["inv"] < 2 * a.size and bb - off > 0 else None
                p["offer"] = round(bo + off, 4) if ok and t0 >= p["cool_offer"] and p["inv"] > -2 * a.size and bo + off < 1 else None
                # 3) reward for this snapshot
                sb, ab = walk(b["bids"], p["bid"], a.size, m["target"], m["disc"], m["tick"], True) if p["bid"] is not None else (0.0, None)
                so, ao = walk(b["offers"], p["offer"], a.size, m["target"], m["disc"], m["tick"], False) if p["offer"] is not None else (0.0, None)
                if m["max_spread"] is not None and (ab is None or ao is None or (ao - ab) / 2 > m["max_spread"] + 1e-9):
                    sb = so = 0.0
                if not gap:
                    p["reward"] += (sb + so) * m["pool"] * dt / 86400 / (2 * m["n"])
            except Exception as err:
                print(datetime.now(timezone.utc).strftime("%H:%M"), m["slug"][:30], "error", repr(err)[:120], flush=True)
        json.dump(st, open(sp, "w"))
        open(midp, "a").write(json.dumps({"ts": round(t0), "mids": mids}) + "\n")
        P_ = st["pos"].values()
        tot = {"t": datetime.now(timezone.utc).isoformat(timespec="seconds"), "reward": round(sum(p["reward"] for p in P_), 2),
               "rebate": round(sum(p["rebate"] for p in P_), 2), "mtm": round(sum(p["cash"] + p["inv"] * (p["mid"] or 0) for p in P_), 2),
               "fills": sum(p["fills"] for p in P_), "quoting": sum(p["bid"] is not None or p["offer"] is not None for p in P_)}
        tot["net"] = round(tot["reward"] + tot["rebate"] + tot["mtm"], 2)
        open(logp, "a").write(json.dumps(tot) + "\n")
        time.sleep(max(1, a.every - (time.time() - t0)))


if __name__ == "__main__":
    main()
