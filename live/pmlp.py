"""Paper liquidity provider for Polymarket's liquidity-rewards program.  Read-only: it never places orders.

Each minute (Polymarket samples the book once a minute), for each chosen market:
  quote : a hypothetical bid at mid - d and ask at mid + d (YES scale), X shares each, d = max(1 tick, v/3)
          (v = the market's max qualifying spread); a side is dropped when inventory on it would exceed 2X
  reward: our score S*X with S = ((v - d)/v)^2 against the qualifying orders already in the real book
          (others' score = mean of their bid-side and ask-side scores); accrue share * daily rate / 1440
  fills : every real taker trade since the last minute that printed AT OR THROUGH our quote fills our whole
          remaining size there at OUR price (pessimistic: we are filled whenever price trades through us)
  P&L   : cash + inventory marked at mid; rewards counted separately.  Maker rebates are ignored (conservative).
Markets: the highest daily pools among those ending more than 14 days out with mid in [0.10, 0.90] and both books
quoted (long-dated questions; no live sports games, no short crypto contracts).  State survives restarts.
  python live/pmlp.py --markets 20 --size 200
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import requests

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backfill"))
import dohfix  # noqa: F401,E402

HERE = os.path.dirname(os.path.abspath(__file__))
S = requests.Session()
CLOB, GAMMA, DATA = "https://clob.polymarket.com", "https://gamma-api.polymarket.com", "https://data-api.polymarket.com"


def jget(url, **p):
    for attempt in range(5):
        try:
            r = S.get(url, params=p, timeout=30)
            if r.status_code == 200:
                return r.json()
        except requests.RequestException:
            pass
        time.sleep(1 + 2 * attempt)
    return None


def rewarded():
    out, cur = [], ""
    while True:
        r = jget(f"{CLOB}/rewards/markets/current", **({"next_cursor": cur} if cur else {}))
        if not r:
            return out
        out += r.get("data", [])
        cur = r.get("next_cursor")
        if not cur or cur == "LTE=" or not r.get("data"):
            return out


def choose(n, size):
    R = sorted(rewarded(), key=lambda x: -float(x.get("total_daily_rate") or 0))
    picked, horizon = [], datetime.now(timezone.utc) + timedelta(days=14)
    for r in R:
        if len(picked) >= n:
            break
        m = jget(f"{GAMMA}/markets", condition_ids=r["condition_id"])
        if not m:
            continue
        m = m[0]
        end = m.get("endDate")
        if not end or datetime.fromisoformat(end.replace("Z", "+00:00")) < horizon or not m.get("enableOrderBook"):
            continue
        if size < float(r.get("rewards_min_size") or 0):
            continue
        tok = json.loads(m["clobTokenIds"])[0]
        b = book(tok)
        if not b or not b["bids"] or not b["asks"]:
            continue
        mid = (b["bids"][0][0] + b["asks"][0][0]) / 2
        if not 0.10 <= mid <= 0.90:
            continue
        picked.append({"cid": r["condition_id"], "token": tok, "question": m["question"], "rate": float(r["total_daily_rate"]),
                       "v": float(r["rewards_max_spread"]), "min_size": float(r.get("rewards_min_size") or 0),
                       "tick": float(m.get("orderPriceMinTickSize") or 0.01), "end": end})
    return picked


def book(token):
    b = jget(f"{CLOB}/book", token_id=token)
    if not b:
        return None
    return {"bids": sorted(((float(x["price"]), float(x["size"])) for x in b.get("bids", [])), reverse=True),
            "asks": sorted((float(x["price"]), float(x["size"])) for x in b.get("asks", []))}


def new_trades(cid, since):
    """taker trades after `since` (unix s), as (ts, YES price, taker bought YES?)"""
    j = jget(f"{DATA}/trades", market=cid, limit=500, takerOnly="true") or []
    out = []
    for t in j:
        if t["timestamp"] <= since:
            continue
        yes_px = float(t["price"]) if t["outcome"] == "Yes" else 1 - float(t["price"])
        bought_yes = (t["side"] == "BUY") == (t["outcome"] == "Yes")
        out.append((t["timestamp"], yes_px, bought_yes))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--markets", type=int, default=20)
    ap.add_argument("--size", type=float, default=200)
    ap.add_argument("--hours", type=float, default=24 * 14)
    a = ap.parse_args()
    state_path, log_path = os.path.join(HERE, "pmlp_state.json"), os.path.join(HERE, "pmlp.jsonl")
    try:
        st = json.load(open(state_path))
    except (OSError, ValueError):
        mk = choose(a.markets, a.size)
        st = {"markets": mk, "pos": {m["cid"]: {"inv": 0.0, "cash": 0.0, "reward": 0.0, "fills": 0, "last": int(time.time()),
                                                "bid": None, "ask": None, "mid": None} for m in mk}}
        json.dump(st, open(state_path, "w"))
    print(len(st["markets"]), "markets:", [m["question"][:40] for m in st["markets"]], flush=True)
    stop = time.time() + 3600 * a.hours
    while time.time() < stop:
        t0 = time.time()
        for m in st["markets"]:
            p = st["pos"][m["cid"]]
            try:
                # 1) fills against the quotes we had up since the last sample
                tr = new_trades(m["cid"], p["last"])
                for ts, px, bought_yes in sorted(tr):
                    if p["bid"] is not None and not bought_yes and px <= p["bid"] + 1e-9:
                        p["inv"] += a.size; p["cash"] -= a.size * p["bid"]; p["fills"] += 1; p["bid"] = None
                    if p["ask"] is not None and bought_yes and px >= p["ask"] - 1e-9:
                        p["inv"] -= a.size; p["cash"] += a.size * p["ask"]; p["fills"] += 1; p["ask"] = None
                if tr:
                    p["last"] = max(ts for ts, _, _ in tr)
                # 2) fresh book -> new quotes and this sample's reward
                b = book(m["token"])
                if not b or not b["bids"] or not b["asks"]:
                    p["bid"] = p["ask"] = None
                    continue
                mid = (b["bids"][0][0] + b["asks"][0][0]) / 2
                v, tick = m["v"], m["tick"]
                d = max(tick, math.ceil(v / 3 / 100 / tick) * tick)          # dollars from mid
                p["mid"] = mid
                p["bid"] = round(mid - d, 4) if p["inv"] < 2 * a.size and mid - d > 0 else None
                p["ask"] = round(mid + d, 4) if p["inv"] > -2 * a.size and mid + d < 1 else None

                def side(levels):
                    return sum(((v - abs(px - mid) * 100) / v) ** 2 * q for px, q in levels
                               if abs(px - mid) * 100 < v and q >= m["min_size"])
                others = (side(b["bids"]) + side(b["asks"])) / 2
                s = ((v - d * 100) / v) ** 2 if d * 100 < v else 0.0
                q_bid = s * a.size if p["bid"] is not None else 0.0
                q_ask = s * a.size if p["ask"] is not None else 0.0
                ours = min(q_bid, q_ask) if not 0.10 <= mid <= 0.90 else max(min(q_bid, q_ask), max(q_bid, q_ask) / 3)
                if ours > 0:
                    p["reward"] += ours / (ours + others) * m["rate"] / 1440
            except Exception as err:
                print(datetime.now(timezone.utc).strftime("%H:%M"), m["question"][:30], "error", repr(err)[:120], flush=True)
        json.dump(st, open(state_path, "w"))
        tot = {"t": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "reward": round(sum(p["reward"] for p in st["pos"].values()), 2),
               "mtm": round(sum(p["cash"] + p["inv"] * (p["mid"] or 0) for p in st["pos"].values()), 2),
               "fills": sum(p["fills"] for p in st["pos"].values()),
               "gross_inventory_$": round(sum(abs(p["inv"]) * (p["mid"] or 0) for p in st["pos"].values()), 2)}
        tot["net"] = round(tot["reward"] + tot["mtm"], 2)
        with open(log_path, "a") as f:
            f.write(json.dumps(tot) + "\n")
        time.sleep(max(1, 60 - (time.time() - t0)))


if __name__ == "__main__":
    main()
