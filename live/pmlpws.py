"""Paper liquidity provider on Polymarket's public market websocket (results/PLAN_PMLPWS.md).  Read-only, no keys.

Same markets, size and scoring as the 1-minute `_tight` run (live/pmlp.py), but quotes follow the best bid/offer on
every book update (after --latency ms) and fills are checked against every trade print as it arrives.
  python live/pmlpws.py --tag _ws
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import ssl
import time
from datetime import datetime, time as dtime, timedelta, timezone

import requests
import websockets

from curfew import UK, close, close_capped, exitable, quiet, winding
from pmlp import latest_comp

HERE = os.path.dirname(os.path.abspath(__file__))
WS = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
GAMMA = "https://gamma-api.polymarket.com"


class Paper:
    sel = sel_ref = None                                   # --select-from off unless __init__ sets them

    def __init__(self, a):
        self.pull_key = getattr(a, "pull_key", "pull")
        self.a = a
        if a.universe == "spike":                            # the ~130 reward markets of results/PM_SPIKE*.md
            import glob
            ms = []
            for f in sorted(glob.glob(os.path.join(HERE, "..", "backfill", "data_local", "pmspike", "0x*.json"))):
                m = json.load(open(f))["meta"]
                if m["rate"] > 0 and m["v"] > 0 and m["min_size"] <= a.size:
                    ms.append({k: m[k] for k in ("cid", "token", "question", "rate", "v", "min_size", "tick", "end")})
            src = {"markets": ms}
        else:
            src = json.load(open(os.path.join(HERE, "pmlp_tight_state.json")))
        self.sp, self.lp = os.path.join(HERE, f"pmlpws{a.tag}_state.json"), os.path.join(HERE, f"pmlpws{a.tag}.jsonl")
        self.fp = os.path.join(HERE, f"pmlpws{a.tag}_fills.jsonl")
        try:
            self.st = json.load(open(self.sp))
        except (OSError, ValueError):
            self.st = {"markets": src["markets"], "pos": {m["cid"]: {"inv": 0.0, "cash": 0.0, "reward": 0.0, "fills": 0}
                                                         for m in src["markets"]}}
        self.M = {m["token"]: m for m in self.st["markets"]}
        self.no = {}                                          # NO token -> YES token
        self.start = {}                                       # YES token -> market creation time (unix), --min-age
        cache_p = os.path.join(HERE, "pm_gamma_cache.json")             # shared by all ws bots: 150 calls per start
        try:                                                            # x 11 bots got rate-limited -> crash loop
            cache = json.load(open(cache_p))
        except (OSError, ValueError):
            cache = {}
        for m in self.st["markets"]:
            g = cache.get(m["cid"])
            for attempt in range(4):
                if g is not None:
                    break
                try:
                    g = requests.get(f"{GAMMA}/markets", params={"condition_ids": m["cid"]}, timeout=30).json()
                    cache[m["cid"]] = g
                except (requests.RequestException, ValueError):
                    time.sleep(2 + 3 * attempt)
            g = g or []
            if g and g[0].get("startDate"):
                self.start[m["token"]] = datetime.fromisoformat(g[0]["startDate"].replace("Z", "+00:00")).timestamp()
            toks = json.loads(g[0]["clobTokenIds"]) if g else []
            if len(toks) == 2:
                self.no[toks[1]] = toks[0]
        try:
            json.dump(cache, open(cache_p + ".tmp", "w"))
            os.replace(cache_p + ".tmp", cache_p)
        except OSError:
            pass
        self.book = {t: {"bids": {}, "asks": {}} for t in self.M}
        self.q = {t: {"bid": None, "ask": None, "pend": None, "cool_bid": 0, "cool_ask": 0} for t in self.M}
        self.mid = {}
        self.jump, self.jump_t = {}, 0.0
        self.spike, self.spike_read = {}, 0.0
        self.sel_ref = getattr(a, "select_from", None)        # PLAN_MKTSEL_SPIKE_FWD: None = off, every market quotes
        self.sel = set() if self.sel_ref else None            # selected cids; empty until the first selection
        self.sel_t = self.sel_first = None
        self.sel_n, self.sel_warm = getattr(a, "select_n", 30), 20.0
        self.thr = float(open(os.path.join(HERE, "..", "backfill", "data_local", "pmjump", "calm_threshold.txt")).read())

    def best(self, t):
        b = self.book[t]
        return (max(b["bids"]) if b["bids"] else None), (min(b["asks"]) if b["asks"] else None)

    def rg_block(self, t, now, inv):
        """--rev-guard (PLAN_REVGUARD): (no_bid, no_ask).  d = mid now - mid 15 min ago, from the latest stored sample at or
        before now-15min (none, or one older than 20 min = no history, no guard).  d >= +1 tick blocks the bid, d <= -1 tick
        the ask; the side that reduces inventory (bid when short, ask when long) is never blocked."""
        h, mid = getattr(self, "mid_hist", {}).get(t), self.mid.get(t)
        if not getattr(self.a, "rev_guard", False) or not h or mid is None:
            return False, False
        ref = None
        for ts, m in h:
            if ts > now - 900:
                break
            ref = (ts, m)
        if ref is None or ref[0] < now - 1200:
            return False, False
        d, tick = mid - ref[1], self.M[t]["tick"] - 1e-9
        return (d >= tick and inv >= 0), (d <= -tick and inv <= 0)

    def requote(self, t, now):
        """new target quotes; they become active after the reaction delay"""
        bb, ba = self.best(t)
        if bb is None or ba is None:
            self.q[t].update(bid=None, ask=None, pend=None)
            return
        self.mid[t] = (bb + ba) / 2
        if getattr(self.a, "rev_guard", False):                           # store (ts, mid), at most 1/s, last 20 min
            h = self.__dict__.setdefault("mid_hist", {}).setdefault(t, [])
            if not h or now - h[-1][0] >= 1.0:
                h.append((now, self.mid[t]))
            while len(h) > 1 and h[0][0] < now - 1200:
                h.pop(0)
        p, size = self.st["pos"][self.M[t]["cid"]], self.a.size
        young = self.a.min_age and now - self.start.get(t, now) < self.a.min_age * 86400   # unknown age = young
        if quiet(now) or young or (self.a.calm and self.pulled(t)) or (self.a.spike and self.spike_pull(t)):                     # PLAN_PMLP_CALM rule, as pmlp.py --calm
            self.q[t]["pend"] = (now + self.a.latency / 1000, None, None)
            return
        off = self.M[t]["tick"] if self.a.back else 0.0                    # --back: one tick behind the touch
        bid = round(bb - off, 4) if p["inv"] < 2 * size and now >= self.q[t]["cool_bid"] and bb - off > 0 else None
        ask = round(ba + off, 4) if p["inv"] > -2 * size and now >= self.q[t]["cool_ask"] and ba + off < 1 else None
        if self.a.wind:                                                   # PLAN_WINDDOWN D: only the side that shrinks inventory
            p["reduce"] = p.get("reduce", False) and p["inv"] != 0
            if winding(now) or p["reduce"]:
                bid = bid if p["inv"] < 0 else None
                ask = ask if p["inv"] > 0 else None
        if self.sel is not None and self.M[t]["cid"] not in self.sel:     # dropped by --select-from: reduce-only, flat = no quotes
            bid = bid if p["inv"] < 0 else None
            ask = ask if p["inv"] > 0 else None
        nb, na = self.rg_block(t, now, p["inv"])                          # --rev-guard (PLAN_REVGUARD)
        bid, ask = (None if nb else bid), (None if na else ask)
        if self.a.liq_cap and (bid is not None or ask is not None):       # never quote a fill we could not exit within 3 ticks
            bids, asks = sorted(self.book[t]["bids"].items(), reverse=True), sorted(self.book[t]["asks"].items())
            d = 3 * self.M[t]["tick"]
            if bid is not None and p["inv"] >= 0 and not exitable(p["inv"] + size, bids, asks, self.mid[t], d):
                bid = None
            if ask is not None and p["inv"] <= 0 and not exitable(p["inv"] - size, bids, asks, self.mid[t], d):
                ask = None
        self.q[t]["pend"] = (now + self.a.latency / 1000, bid, ask)

    def pulled(self, t):
        from datetime import timedelta
        m, mid = self.M[t], self.mid[t]
        end = datetime.fromisoformat(m["end"].replace("Z", "+00:00"))
        return (end - datetime.now(timezone.utc) <= timedelta(days=14) or not 0.10 <= mid <= 0.90
                or (self.jump.get(t) or 0) >= self.thr)

    def spike_pull(self, t):
        """live spike signal from spikelive.py; a missing or stale (> 5 min) file pulls everything"""
        now = time.time()
        if now - self.spike_read > 15:
            self.spike_read = now
            try:
                self.spike = json.load(open(os.path.join(HERE, "spike_pulls.json")))
            except (OSError, ValueError):
                self.spike = {}
        if now - self.spike.get("ts", 0) > 300:
            return True
        return bool((self.spike.get("markets") or {}).get(t, {}).get(self.pull_key, False))

    def refresh_jump(self):
        """hourly trailing-24h jumpiness per market (pmlp.jumpiness; None during an outage = not jumpy, as pmlp)"""
        if not self.a.calm or time.time() - self.jump_t < 3600:
            return
        from pmlp import jumpiness
        self.jump_t = time.time()
        for t in self.M:
            try:
                self.jump[t] = jumpiness(t)
            except Exception:
                self.jump[t] = None

    def activate(self, t, now):
        pend = self.q[t]["pend"]
        if pend and now >= pend[0]:
            self.q[t]["bid"], self.q[t]["ask"], self.q[t]["pend"] = pend[1], pend[2], None

    def trade(self, t, yes_px, bought_yes, ts, now):
        self.activate(t, now)
        m, q, size = self.M[t], self.q[t], self.a.size
        p = self.st["pos"][m["cid"]]
        side = None
        drop = self.sel is not None and m["cid"] not in self.sel                    # --select-from: dropped market, reduce-only
        red = self.a.wind or drop
        nb, na = self.rg_block(t, now, p["inv"])                                   # --rev-guard: a resting quote the guard
        if nb:                                                                     # now blocks is cancelled, not filled
            q["bid"] = None
        if na:
            q["ask"] = None
        if q["bid"] is not None and not bought_yes and yes_px < q["bid"] - 1e-9 and not (drop and p["inv"] >= 0):
            side, px = "buy_yes", q["bid"]
            fs = min(size, -p["inv"]) if red and p["inv"] < 0 else size     # --wind: reduce to 0, no flip
            p["inv"] += fs; p["cash"] -= fs * px
            q["bid"], q["cool_bid"] = None, now + 60
        elif q["ask"] is not None and bought_yes and yes_px > q["ask"] + 1e-9 and not (drop and p["inv"] <= 0):
            side, px = "sell_yes", q["ask"]
            fs = min(size, p["inv"]) if red and p["inv"] > 0 else size
            p["inv"] -= fs; p["cash"] += fs * px
            q["ask"], q["cool_ask"] = None, now + 60
        if side:
            p["fills"] += 1
            was = p["inv"] + (fs if side == "sell_yes" else -fs)
            if was == 0 or was * p["inv"] < 0:
                p["since"] = now
            with open(self.fp, "a") as f:
                f.write(json.dumps({"logged": datetime.now(timezone.utc).isoformat(timespec="milliseconds"), "trade_ms": ts,
                                    "cid": m["cid"], "token": t, "question": m["question"], "side": side, "price": px,
                                    "size": fs, "mid": self.mid.get(t), "trade_yes_px": yes_px, "inv_after": p["inv"]}) + "\n")

    def select_scores(self, now):
        """cid -> reference-bot fill P&L over the 7 days before `now`: sum of signed YES size x (current mid - fill price).
        Fills are YES-terms already (NO prints are converted in trade()).  buy_yes +size, sell_yes -size; flatten/settle
        rows carry no direction, so their signed size is the change in inv_after since the cid's previous row."""
        lo, cids = now - 7 * 86400, {m["cid"]: t for t, m in self.M.items()}
        sc, prev, last_mid, fills = {c: 0.0 for c in cids}, {}, {}, []
        try:
            lines = open(os.path.join(HERE, f"pmlpws{self.sel_ref}_fills.jsonl")).read().splitlines()
        except OSError:
            lines = []
        rows = []
        for ln in lines:
            try:
                r = json.loads(ln)
                ts = datetime.fromisoformat(r["logged"].replace("Z", "+00:00")).timestamp()
            except (ValueError, KeyError, TypeError):
                continue
            if r.get("cid") in cids and ts < now:                       # causal: only fills logged before the ranking
                rows.append((ts, r))
        for ts, r in sorted(rows, key=lambda x: x[0]):
            c, inv = r["cid"], r.get("inv_after") or 0.0
            d = r["size"] if r["side"] == "buy_yes" else -r["size"] if r["side"] == "sell_yes" else inv - prev.get(c, 0.0)
            prev[c] = inv
            if r.get("mid") is not None:
                last_mid[c] = r["mid"]
            if ts >= lo and r.get("price") is not None:
                fills.append((c, d, r["price"]))
        mids = {c: self.mid.get(t, last_mid.get(c)) for c, t in cids.items()}
        for c, d, px in fills:
            if mids[c] is not None:
                sc[c] += d * (mids[c] - px)
        return {c: round(x, 6) for c, x in sc.items()}

    def maybe_select(self, now):
        """--select-from: select at start-up (after a short warm-up for book snapshots) and at the first call after each
        06:45 UK.  Returns True when a selection was made."""
        if not self.sel_ref:
            return False
        if self.sel_t is None:
            self.sel_first = self.sel_first or now
            if now - self.sel_first < self.sel_warm:
                return False
            why = "start"
        else:
            d = datetime.fromtimestamp(now, UK)
            b = datetime.combine(d.date(), dtime(6, 45), UK)
            if b > d:
                b -= timedelta(days=1)
            if self.sel_t >= b.timestamp():
                return False
            why = "daily"
        sc = self.select_scores(now)
        self.sel = set(sorted(sc, key=lambda c: (-sc[c], c))[:self.sel_n])
        self.sel_t = now
        with open(os.path.join(HERE, f"pmlpws{self.a.tag}_select.jsonl"), "a") as f:
            f.write(json.dumps({"t": datetime.fromtimestamp(now, timezone.utc).isoformat(timespec="seconds"), "why": why,
                                "selected": sorted(self.sel, key=lambda c: (-sc[c], c)), "scores": sc}) + "\n")
        for t in self.M:                                                 # apply at once, not on the next book update
            if self.book[t]["bids"] and self.book[t]["asks"]:
                self.requote(t, now)
        return True

    def on(self, msg, now):
        typ = msg.get("event_type")
        if typ == "book" and msg.get("asset_id") in self.M:
            t = msg["asset_id"]
            self.book[t] = {"bids": {float(x["price"]): float(x["size"]) for x in msg.get("bids", [])},
                            "asks": {float(x["price"]): float(x["size"]) for x in msg.get("asks", [])}}
            self.requote(t, now)
        elif typ == "price_change":
            for c in msg.get("price_changes", []):
                t = c.get("asset_id")
                if t not in self.M:
                    continue
                side = self.book[t]["bids" if c["side"] == "BUY" else "asks"]
                px, sz = float(c["price"]), float(c["size"])
                if sz > 0:
                    side[px] = sz
                else:
                    side.pop(px, None)
                self.activate(t, now)
                self.requote(t, now)
        elif typ == "last_trade_price":
            t, px, buy = msg.get("asset_id"), float(msg["price"]), msg.get("side") == "BUY"
            if t in self.M:
                self.trade(t, px, buy, msg.get("timestamp"), now)
            elif t in self.no:                                   # NO print: buying NO at q = selling YES at 1 - q
                self.trade(self.no[t], 1 - px, not buy, msg.get("timestamp"), now)

    def wind_down(self, now):
        """curfew.py: no quotes, and close any position against the live book before the blackout"""
        for t in self.M:
            self.q[t].update(bid=None, ask=None, pend=None)
            self.flatten(t)
            if self.a.wind:                                   # capped cross leaves a remainder: hold it, reduce-only after 06:35
                p = self.st["pos"][self.M[t]["cid"]]
                p["reduce"] = bool(p["inv"])

    def time_stop(self, now):
        """--max-hold: close a position held longer than max_hold seconds (quoting continues)"""
        for t, m in self.M.items():
            p = self.st["pos"][m["cid"]]
            if p["inv"] and now - p.get("since", now) >= self.a.max_hold:
                self.flatten(t)

    def levels(self, t):
        """best-first (bids, asks) with the depth our own capped crosses already consumed removed (the paper cross does not
        change the real book, so without this the remainder would be re-sold into the same levels and marked at them)"""
        bids, asks = self.book[t]["bids"], self.book[t]["asks"]
        e = getattr(self, "eaten", {}).get(t)
        if e:
            bids = {px: sz - e.get(px, 0.0) for px, sz in bids.items()}
            asks = {px: sz - e.get(px, 0.0) for px, sz in asks.items()}
        return (sorted(((px, sz) for px, sz in bids.items() if sz > 1e-9), reverse=True),
                sorted((px, sz) for px, sz in asks.items() if sz > 1e-9))

    def flatten(self, t):
        m = self.M[t]
        p = self.st["pos"][m["cid"]]
        if p["inv"]:
            bids, asks = self.levels(t)
            if self.a.wind:                                   # PLAN_WINDDOWN D: cross only depth within 2 ticks of mid
                bb, ba = self.best(t)
                if not bids or not asks or bb is None or ba is None:
                    return
                mid = (bb + ba) / 2                          # mid from the real book, not the depth net of our own crosses
                cash, done, avg = close_capped(p["inv"], bids, asks, mid, 2 * m["tick"])
                if not done:
                    return
                with open(self.fp, "a") as f:
                    f.write(json.dumps({"logged": datetime.now(timezone.utc).isoformat(timespec="milliseconds"), "trade_ms": None,
                                        "cid": m["cid"], "token": t, "question": m["question"], "side": "flatten",
                                        "price": round(avg, 4), "size": abs(done), "mid": mid, "trade_yes_px": None,
                                        "inv_after": p["inv"] - done}) + "\n")
                p["cash"] += cash
                left, ate = abs(done), self.__dict__.setdefault("eaten", {}).setdefault(t, {})
                for px, sz in (bids if done > 0 else asks):          # remember the depth we consumed
                    if abs(px - mid) > 2 * m["tick"] + 1e-9 or left <= 1e-9:
                        break
                    take = min(left, sz)
                    ate[px], left = ate.get(px, 0.0) + take, left - take
                p["inv"] -= done
                if abs(p["inv"]) < 1e-9:
                    p["inv"] = 0.0
                    p.pop("since", None)
                    self.eaten.pop(t, None)
                return
            cash, avg = close(p["inv"], bids, asks)
            if avg is None:
                print(datetime.now(timezone.utc).strftime("%H:%M"), m["question"][:30], "flatten skipped: exit side empty",
                      flush=True)
                return
            with open(self.fp, "a") as f:
                f.write(json.dumps({"logged": datetime.now(timezone.utc).isoformat(timespec="milliseconds"), "trade_ms": None,
                                    "cid": m["cid"], "token": t, "question": m["question"], "side": "flatten",
                                    "price": round(avg, 4), "size": abs(p["inv"]), "mid": self.mid.get(t), "trade_yes_px": None,
                                    "inv_after": 0.0}) + "\n")
            p["cash"] += cash
            p["inv"] = 0.0
            p.pop("since", None)

    def settle(self, t, m, p):
        """closed market: book the position at the resolution price (CLOB winner flags)"""
        try:
            c = requests.get(f"https://clob.polymarket.com/markets/{m['cid']}", timeout=30).json()
        except Exception:
            return
        yes = next((x for x in c.get("tokens", []) if x.get("token_id") == t), None)
        if not c.get("closed") or yes is None or not any(x.get("winner") for x in c.get("tokens", [])):
            return
        px = 1.0 if yes.get("winner") else 0.0
        with open(self.fp, "a") as f:
            f.write(json.dumps({"logged": datetime.now(timezone.utc).isoformat(timespec="milliseconds"), "trade_ms": None,
                                "cid": m["cid"], "token": t, "question": m["question"], "side": "settle", "price": px,
                                "size": abs(p["inv"]), "mid": p.get("mark"), "trade_yes_px": None, "inv_after": 0.0}) + "\n")
        p["cash"] += p["inv"] * px
        p["inv"], p["liq"], p["mark"] = 0.0, 0.0, px
        p.pop("since", None)

    def sample(self, dt):
        """once a minute: reward share against the book (pmlp's formula) and the log line"""
        self.refresh_jump()
        now = time.time()
        if now - getattr(self, "comp_t", 0) > 600:
            self.comp, self.comp_t = latest_comp(), now
        if quiet(now):
            self.wind_down(now)
        elif self.a.max_hold:
            self.time_stop(now)
        for t, m in self.M.items():
            self.activate(t, now)
            q, p, mid = self.q[t], self.st["pos"][m["cid"]], self.mid.get(t)
            if mid is None:
                continue
            nb, na = self.rg_block(t, now, p["inv"])                      # --rev-guard: no reward on a quote it now blocks
            if nb:
                q["bid"] = None
            if na:
                q["ask"] = None
            v, b = m["v"], self.book[t]

            def side(levels):
                return sum(((v - abs(px - mid) * 100) / v) ** 2 * qq for px, qq in levels.items()
                           if abs(px - mid) * 100 < v and qq >= m["min_size"])
            others = (side(b["bids"]) + side(b["asks"])) / 2
            dd = max(mid - (q["bid"] or mid), (q["ask"] or mid) - mid) * 100
            s = ((v - dd) / v) ** 2 if dd < v else 0.0
            qb = s * self.a.size if q["bid"] is not None else 0.0
            qa = s * self.a.size if q["ask"] is not None else 0.0
            ours = min(qb, qa) if not 0.10 <= mid <= 0.90 else max(min(qb, qa), max(qb, qa) / 3)
            if ours > 0:
                p["reward"] += ours / (ours + others) * m["rate"] / 1440 * dt / 60
                c = self.comp.get(m["cid"])
                oth = max(others, c * m["rate"]) if c is not None else others
                p["reward_safe"] = p.get("reward_safe", 0.0) + ours / (ours + oth) * m["rate"] / 1440 * dt / 60
            if not p["inv"]:
                getattr(self, "eaten", {}).pop(t, None)
            if p["inv"] and (b["bids"] if p["inv"] > 0 else b["asks"]):     # exit value now (depth-walked)
                p["liq"] = close(p["inv"], *self.levels(t))[0]
            elif p["inv"]:
                p.pop("liq", None)                                          # exit side empty: fall back to mid mark
            else:
                p["liq"] = 0.0
        P = self.st["pos"].values()
        mids = {self.M[t]["cid"]: x for t, x in self.mid.items()}
        for t, m in self.M.items():                                    # resolved markets settle at 0/1; a missing
            p = self.st["pos"][m["cid"]]                                # mid falls back to the last mark, never 0
            if m["cid"] in mids:
                p["mark"] = mids[m["cid"]]
            elif p["inv"] and now - p.get("settle_t", 0) > 1800:
                p["settle_t"] = now
                self.settle(t, m, p)
        mids = {**{c: p["mark"] for c, p in self.st["pos"].items() if p.get("mark") is not None}, **mids}
        tot = {"t": datetime.now(timezone.utc).isoformat(timespec="seconds"), "reward": round(sum(p["reward"] for p in P), 2),
               "mtm": round(sum(p["cash"] + p["inv"] * mids.get(c, 0) for c, p in self.st["pos"].items()), 2),
               "fills": sum(p["fills"] for p in P)}
        tot["reward_safe"] = round(sum(p.get("reward_safe", p["reward"]) for p in P), 2)
        tot["mtm_liq"] = round(sum(p["cash"] + p.get("liq", p["inv"] * mids.get(c, 0)) for c, p in self.st["pos"].items()), 2)
        tot["net"] = round(tot["reward"] + tot["mtm"], 2)
        tot["net_safe"] = round(tot["reward_safe"] + tot["mtm_liq"], 2)   # conservative headline (audit 10 Oct)
        json.dump(self.st, open(self.sp, "w"))
        with open(self.lp, "a") as f:
            f.write(json.dumps(tot) + "\n")

    async def run(self):
        ctx = ssl.create_default_context(cafile=os.environ.get("SSL_CERT_FILE")) if os.environ.get("SSL_CERT_FILE") else None
        stop, wait = time.time() + 3600 * self.a.hours, 1
        while time.time() < stop:
            try:
                async with websockets.connect(WS, ssl=ctx, ping_interval=10, max_size=2 ** 24) as ws:
                    await ws.send(json.dumps({"assets_ids": list(self.M) + list(self.no), "type": "market"}))
                    print(datetime.now(timezone.utc).strftime("%H:%M:%S"), "connected", len(self.M), "markets", flush=True)
                    wait, last = 1, time.time()
                    self.refresh_jump()
                    while time.time() < stop:
                        raw = await asyncio.wait_for(ws.recv(), 120)
                        now = time.time()
                        msgs = json.loads(raw)
                        for m in msgs if isinstance(msgs, list) else [msgs]:
                            self.on(m, now)
                        self.maybe_select(now)
                        if now - last >= 60:
                            self.sample(min(now - last, 90))
                            last = now
            except Exception as err:
                for q in self.q.values():                          # quotes are not live while disconnected
                    q.update(bid=None, ask=None, pend=None)
                print(datetime.now(timezone.utc).strftime("%H:%M:%S"), "reconnect in", wait, "s:", repr(err)[:120], flush=True)
                await asyncio.sleep(wait)
                wait = min(300, wait * 2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="_ws")
    ap.add_argument("--size", type=float, default=500)
    ap.add_argument("--latency", type=float, default=250, help="ms between a book change and our new quote counting")
    ap.add_argument("--hours", type=float, default=24 * 14)
    ap.add_argument("--spike", action="store_true", help="pull quotes on live/spike_pulls.json (spikelive.py)")
    ap.add_argument("--back", action="store_true", help="quote one tick behind the best bid/ask (PLAN_SPIKE40_BACK)")
    ap.add_argument("--pull-key", default="pull", help="which spike_pulls.json flag: pull (30%%) or pull40 (PLAN_SPIKE40)")
    ap.add_argument("--calm", action="store_true", help="pull quotes as pmlp.py --calm (PLAN_PMLP_CALM.md)")
    ap.add_argument("--max-hold", type=float, default=0, help="close any position held longer than this many seconds")
    ap.add_argument("--min-age", type=float, default=0, help="do not quote markets created fewer than this many days ago (PLAN_MIN_AGE)")
    ap.add_argument("--wind", action="store_true", help="reduce-only 21:45-23:45, curfew crosses only 2 ticks, rest held (PLAN_WINDDOWN D)")
    ap.add_argument("--liq-cap", action="store_true", help="never quote a side whose fill could not be exited within 3 ticks of mid")
    ap.add_argument("--select-from", default=None, help="tag of a reference bot (e.g. _ws130_spike40bh): quote only the --select-n "
                    "markets with the best 7-day fill P&L in its fills file, re-ranked daily after 06:45 UK (PLAN_MKTSEL_SPIKE_FWD)")
    ap.add_argument("--rev-guard", action="store_true", help="no bid after the mid rose >= 1 tick in 15 min, no ask after it fell "
                    ">= 1 tick; inventory-reducing side exempt (PLAN_REVGUARD)")
    ap.add_argument("--select-n", type=int, default=30, help="how many markets --select-from keeps")
    ap.add_argument("--universe", default="tight", choices=["tight", "spike"],
                    help="tight = pmlp_tight's 20 markets; spike = the ~130 reward markets of PM_SPIKE")
    ap.add_argument("--no-curfew", action="store_true", help="always-on host (GitHub Actions cloud twin): no blackout wind-down")
    a = ap.parse_args()
    if a.no_curfew:
        globals()["quiet"] = lambda ts=None: False
    asyncio.run(Paper(a).run())


if __name__ == "__main__":
    main()
