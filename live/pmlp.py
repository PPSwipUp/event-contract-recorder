"""Paper liquidity provider for Polymarket's liquidity-rewards program.  Read-only: it never places orders.

Each minute (Polymarket samples the book once a minute), for each chosen market:
  quote : a hypothetical bid at floor(mid - d) and ask at ceil(mid + d) on the tick grid, X shares each, d = v/3
          (or half a tick = join the touch, --dist tick)
          (v = the market's max qualifying spread); a side is dropped when inventory on it would exceed 2X
  reward: our score S*X with S = ((v - d)/v)^2 against the qualifying orders already in the real book
          (others' score = mean of their bid-side and ask-side scores); accrue share * daily rate / 1440
  fills : every real taker trade since the last minute that printed strictly THROUGH our quote fills our whole
          size at OUR price (back of the queue: at-price prints go to the orders already there)
  P&L   : cash + inventory marked at mid; rewards counted separately.  Maker rebates are ignored (conservative).
Markets: the highest daily pools among those ending more than 14 days out with mid in [0.10, 0.90] and both books
quoted (long-dated questions; no live sports games, no short crypto contracts).  State survives restarts.
Every fill is appended to pmlp<tag>_fills.jsonl (market, time, side, price, mid).
--calm (results/PLAN_PMLP_CALM.md): every loop, stop quoting a market whose end is <= 14 days away or whose mid is
outside [0.10, 0.90]; and pull quotes while its trailing-24h jumpiness (mean |hourly price change| over the last 24 h,
refreshed hourly) is >= the frozen threshold in backfill/data_local/pmjump/calm_threshold.txt.
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


def jumpiness(token):
    """mean |hourly YES price change| over the last 24 hours (the "day" predictor in results/PM_JUMP.md)"""
    h = (jget(f"{CLOB}/prices-history", market=token, interval="1d", fidelity=60) or {}).get("history", [])
    p = [x["p"] for x in sorted(h, key=lambda x: x["t"])][-25:]
    if len(p) < 7:                                                   # pmjump used min_periods=6 changes
        return None
    return sum(abs(b - a) for a, b in zip(p, p[1:])) / (len(p) - 1)


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
    ap.add_argument("--dist", default="third", choices=["third", "tick"], help="quote v/3 or one tick from mid")
    ap.add_argument("--tag", default="", help="suffix for state/log files (parallel paper runs)")
    ap.add_argument("--calm", action="store_true", help="per-loop 14-day/mid filter + pull when jumpy (PLAN_PMLP_CALM)")
    a = ap.parse_args()
    state_path = os.path.join(HERE, f"pmlp{a.tag}_state.json")
    log_path = os.path.join(HERE, f"pmlp{a.tag}.jsonl")
    fills_path = os.path.join(HERE, f"pmlp{a.tag}_fills.jsonl")
    thr = float(open(os.path.join(HERE, "..", "backfill", "data_local", "pmjump", "calm_threshold.txt")).read())
    jump, jump_t = {}, {}

    def log_fill(m, p, ts, side, px, trade_px):
        with open(fills_path, "a") as f:
            f.write(json.dumps({"logged": datetime.now(timezone.utc).isoformat(timespec="seconds"), "trade_ts": ts,
                                "cid": m["cid"], "token": m["token"], "question": m["question"], "side": side, "price": px,
                                "size": a.size, "mid": p["mid"], "trade_yes_px": trade_px, "inv_after": p["inv"]}) + "\n")
    try:
        st = json.load(open(state_path))
    except (OSError, ValueError):
        mk = choose(a.markets, a.size)
        st = {"markets": mk, "pos": {m["cid"]: {"inv": 0.0, "cash": 0.0, "reward": 0.0, "fills": 0, "last": int(time.time()),
                                                "bid": None, "ask": None, "mid": None} for m in mk}}
        json.dump(st, open(state_path, "w"))
    print(len(st["markets"]), "markets:", [m["question"][:40] for m in st["markets"]], flush=True)
    stop = time.time() + 3600 * a.hours
    last_loop = time.time()
    while time.time() < stop:
        t0 = time.time()
        if t0 - last_loop > 300:                       # came back from an outage (e.g. the school Wi-Fi night curfew):
            for p in st["pos"].values():               # quotes were not live meanwhile, so don't fill them against
                p["bid"] = p["ask"] = None             # the trades that happened during the gap
                p["last"] = int(t0)
            print(datetime.now(timezone.utc).strftime("%H:%M"), f"resumed after {(t0 - last_loop) / 60:.0f} min gap", flush=True)
        last_loop = t0
        for m in st["markets"]:
            p = st["pos"][m["cid"]]
            try:
                # 1) fills against the quotes we had up since the last sample
                tr = new_trades(m["cid"], p["last"])
                for ts, px, bought_yes in sorted(tr):
                    # back of the queue: only prints strictly THROUGH our price reach us (60-day replay showed the
                    # at-price "front of queue" rule is fantasy when 20k-2M shares already sit at the touch)
                    if p["bid"] is not None and not bought_yes and px < p["bid"] - 1e-9:
                        p["inv"] += a.size; p["cash"] -= a.size * p["bid"]; p["fills"] += 1
                        log_fill(m, p, ts, "buy_yes", p["bid"], px); p["bid"] = None
                    if p["ask"] is not None and bought_yes and px > p["ask"] + 1e-9:
                        p["inv"] -= a.size; p["cash"] += a.size * p["ask"]; p["fills"] += 1
                        log_fill(m, p, ts, "sell_yes", p["ask"], px); p["ask"] = None
                if tr:
                    p["last"] = max(ts for ts, _, _ in tr)
                # 2) fresh book -> new quotes and this sample's reward
                b = book(m["token"])
                if not b or not b["bids"] or not b["asks"]:
                    p["bid"] = p["ask"] = None
                    continue
                mid = (b["bids"][0][0] + b["asks"][0][0]) / 2
                if a.calm:
                    if time.time() - jump_t.get(m["cid"], 0) > 3600:
                        jump[m["cid"]], jump_t[m["cid"]] = jumpiness(m["token"]), time.time()
                    end = datetime.fromisoformat(m["end"].replace("Z", "+00:00"))
                    p["pulled"] = (end - datetime.now(timezone.utc) <= timedelta(days=14) or not 0.10 <= mid <= 0.90
                                   or (jump[m["cid"]] or 0) >= thr)
                    if p["pulled"]:
                        p["mid"], p["bid"], p["ask"] = mid, None, None
                        p["pulled_min"] = p.get("pulled_min", 0) + 1
                        continue
                v, tick = m["v"], m["tick"]
                d = tick if a.dist == "tick" else max(tick, math.ceil(v / 3 / 100 / tick) * tick)   # dollars from mid
                p["mid"] = mid
                if a.dist == "tick":
                    d = tick / 2                                                 # join the best bid / ask
                bid = round(math.floor(round((mid - d) / tick, 6)) * tick, 4)       # valid prices only (tick grid)
                ask = round(math.ceil(round((mid + d) / tick, 6)) * tick, 4)
                p["bid"] = bid if p["inv"] < 2 * a.size and bid > 0 else None
                p["ask"] = ask if p["inv"] > -2 * a.size and ask < 1 else None

                def side(levels):
                    return sum(((v - abs(px - mid) * 100) / v) ** 2 * q for px, q in levels
                               if abs(px - mid) * 100 < v and q >= m["min_size"])
                others = (side(b["bids"]) + side(b["asks"])) / 2
                dd = max(mid - bid, ask - mid) * 100
                s = ((v - dd) / v) ** 2 if dd < v else 0.0
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
        if a.calm:
            tot["pulled_now"] = sum(bool(p.get("pulled")) for p in st["pos"].values())
        tot["net"] = round(tot["reward"] + tot["mtm"], 2)
        with open(log_path, "a") as f:
            f.write(json.dumps(tot) + "\n")
        time.sleep(max(1, 60 - (time.time() - t0)))


if __name__ == "__main__":
    main()
