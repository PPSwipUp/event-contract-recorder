"""Seeded random draw of Kalshi liquidity programs for the general-LIP forward paper test (results/PLAN_LIP_GENERAL_FWD.md).
Read-only public GET.  Draw list is APPEND-ONLY in live/lipgen_draw.jsonl:
  {"k":"draw","ts","seed","n","alloc":{cat:k},"programs":[{row..,"cat":..}]}      initial 60 (written once, before recording)
  {"k":"order","cat":c,"ids":[program ids in seeded order]}                       replacement order (same seed)
  {"k":"replace","ts","ended":id,"program":{row..,"cat":..}}                      a drawn program ended -> next in order
  {"k":"end","ts","id"}                                                           drawn program ended and nothing replaced it
  .venv/bin/python live/lipgen_draw.py --init        # one-off: draw + save (refuses if the file already has a draw)
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kxlipbook as KL  # noqa: E402

DRAW_FILE = os.path.join(HERE, "lipgen_draw.jsonl")
CAT_FILE = os.path.join(HERE, "lipgen_series_cat.json")
SEED, N, MIN_H = 0, 60, 12.0
EXCLUDE_PREFIX = "KXNFL"


def eligible(rows, now, min_h=MIN_H):
    """active liquidity programs: started, not paid out, end >= now + min_h hours, not KXNFL*.  Sorted by id."""
    out = []
    for r in rows:
        if r.get("incentive_type") != "liquidity" or r.get("paid_out"):
            continue
        s0, s1 = KL.iso_ts(r.get("start_date", "")), KL.iso_ts(r.get("end_date", ""))
        if s0 is None or s1 is None or not (s0 <= now and s1 >= now + min_h * 3600):
            continue
        if KL.series_of(r["market_ticker"]).startswith(EXCLUDE_PREFIX):
            continue
        out.append(r)
    return sorted(out, key=lambda r: r["id"])


def allocate(counts, n=N):
    """largest-remainder proportional allocation of n over {cat: count}; ties by category name.  Never exceeds a category's count."""
    tot = sum(counts.values())
    if tot == 0:
        return {}
    ex = {c: n * v / tot for c, v in counts.items()}
    a = {c: min(counts[c], int(e)) for c, e in ex.items()}
    left = n - sum(a.values())
    for c in sorted(counts, key=lambda c: (-(ex[c] - int(ex[c])), c)):
        if left <= 0:
            break
        if a[c] < counts[c]:
            a[c] += 1
            left -= 1
    return {c: k for c, k in a.items() if k}


def seeded_orders(rows_by_cat, seed=SEED):
    """per-category replacement/draw order: ids sorted, then shuffled by one random.Random(seed) walked over sorted categories."""
    rnd = random.Random(seed)
    orders = {}
    for c in sorted(rows_by_cat):
        ids = sorted(r["id"] for r in rows_by_cat[c])
        rnd.shuffle(ids)
        orders[c] = ids
    return orders


class Draw:
    """State of the draw, persisted in the append-only jsonl.  cat_of(series)->category and open_ok(ticker)->bool are injected."""

    def __init__(self, path=DRAW_FILE):
        self.path = path
        self.orders, self.drawn, self.ended = {}, {}, set()      # drawn: id -> program dict (incl. cat); ended: ids
        self.active = {}                                         # id -> program dict of currently live slots
        if os.path.exists(path):
            for l in open(path):
                if l.strip():
                    self._apply(json.loads(l))

    @property
    def initialised(self):
        return bool(self.drawn)

    def _apply(self, o):
        k = o["k"]
        if k == "draw":
            for p in o["programs"]:
                self.drawn[p["id"]] = p
                self.active[p["id"]] = p
        elif k == "order":
            self.orders[o["cat"]] = o["ids"]
        elif k == "replace":
            self.ended.add(o["ended"])
            self.active.pop(o["ended"], None)
            self.drawn[o["program"]["id"]] = o["program"]
            self.active[o["program"]["id"]] = o["program"]
        elif k == "end":
            self.ended.add(o["id"])
            self.active.pop(o["id"], None)

    def _append(self, o):
        with open(self.path, "a") as f:
            f.write(json.dumps(o, separators=(",", ":")) + "\n")
            f.flush()
            os.fsync(f.fileno())
        self._apply(o)

    def _pick(self, cands_by_id, order, cat_of_id, open_ok, taken_tickers, n):
        """walk `order`, take the first n eligible, unused, open-market, unseen-ticker programs."""
        got = []
        for i in order:
            if len(got) >= n:
                break
            r = cands_by_id.get(i)
            if r is None or i in self.drawn or r["market_ticker"] in taken_tickers:
                continue
            if not open_ok(r["market_ticker"]):
                continue
            got.append(dict(r, cat=cat_of_id[i]))
            taken_tickers.add(r["market_ticker"])
        return got

    def init(self, rows, now, cat_of_series, open_ok, n=N, seed=SEED):
        if self.initialised:
            raise RuntimeError("draw already exists; refusing to redraw")
        el = eligible(rows, now)
        cat_of_id = {r["id"]: cat_of_series(KL.series_of(r["market_ticker"])) for r in el}
        by_cat = {}
        for r in el:
            by_cat.setdefault(cat_of_id[r["id"]], []).append(r)
        alloc = allocate({c: len(v) for c, v in by_cat.items()}, n)
        orders = seeded_orders(by_cat, seed)
        byid = {r["id"]: r for r in el}
        taken, progs = set(), []
        for c in sorted(alloc):
            progs += self._pick(byid, orders[c], cat_of_id, open_ok, taken, alloc[c])
        for c in sorted(orders):
            self._append({"k": "order", "cat": c, "ids": orders[c]})
        self._append({"k": "draw", "ts": now, "seed": seed, "n": n, "alloc": alloc, "programs": progs})
        return progs

    def extend(self, rows, now, cat_of_series, open_ok, n):
        """PLAN AMENDMENT 1: add n more programs by walking the SAME stored seeded orders (no redraw).  Allocation over
        categories = largest-remainder proportional to currently eligible, not-yet-drawn programs in those orders."""
        if not self.initialised:
            raise RuntimeError("no initial draw")
        el = {r["id"]: r for r in eligible(rows, now)}
        cat_of_id = {i: cat_of_series(KL.series_of(r["market_ticker"])) for i, r in el.items()}
        counts = {c: sum(1 for i in ids if i in el and i not in self.drawn) for c, ids in self.orders.items()}
        alloc = allocate({c: k for c, k in counts.items() if k}, n)
        taken, progs = {q["market_ticker"] for q in self.active.values()}, []
        for c in sorted(alloc):
            progs += self._pick(el, self.orders[c], cat_of_id, open_ok, taken, alloc[c])
        self._append({"k": "draw", "ts": now, "seed": SEED, "n": n, "alloc": alloc, "programs": progs, "amend": 1})
        return progs

    def maintain(self, rows, now, cat_of_series, open_ok):
        """call after each full programs pull.  Programs whose end passed (or that vanished/paid out) are replaced by the next in the
        seeded order of the same category (else the next category's order, sorted by name).  Returns list of new programs."""
        by_id = {r["id"]: r for r in rows}
        el = {r["id"]: r for r in eligible(rows, now)}
        cat_of_id = {i: cat_of_series(KL.series_of(r["market_ticker"])) for i, r in el.items()}
        new = []
        for pid in sorted(self.active):
            p = self.active[pid]
            cur = by_id.get(pid)
            gone = cur is None or cur.get("paid_out") or (KL.iso_ts((cur or p)["end_date"]) or 0) <= now
            if not gone:
                continue
            taken = {q["market_ticker"] for q in self.active.values()}
            cats = [p["cat"]] + [c for c in sorted(self.orders) if c != p["cat"]]
            pick = []
            for c in cats:
                pick = self._pick(el, self.orders.get(c, []), cat_of_id, open_ok, taken, 1)
                if pick:
                    break
            if pick:
                self._append({"k": "replace", "ts": now, "ended": pid, "program": pick[0]})
                new.append(pick[0])
            else:
                self._append({"k": "end", "ts": now, "id": pid})
        return new


# ------------------------------------------------------------------------------------------------------- io helpers
def pull_programs(api):
    rows, cur = [], None
    for _ in range(40):
        p = {"status": "active", "type": "liquidity", "limit": 1000}
        if cur:
            p["cursor"] = cur
        d = api.get("/incentive_programs", p)
        if d is None:
            return None                                  # incomplete pull: caller must not act on it
        rows += d.get("incentive_programs") or []
        cur = d.get("next_cursor")
        if not cur or not d.get("incentive_programs"):
            break
    return rows


class CatCache:
    def __init__(self, api, path=CAT_FILE):
        self.api, self.path = api, path
        try:
            self.m = json.load(open(path))
        except (OSError, ValueError):
            self.m = {}

    def __call__(self, series):
        if series not in self.m:
            d = self.api.get("/series/" + series)
            c = ((d or {}).get("series") or {}).get("category")
            if not c:
                return "Unknown"                         # transient failure: do not cache
            self.m[series] = c
            json.dump(self.m, open(self.path, "w"))
        return self.m[series]


class OpenCheck:
    """market is tradable now: GET /markets/{ticker} status in (open, active).  Unknown (request failed) -> False (conservative)."""

    def __init__(self, api):
        self.api = api

    def __call__(self, ticker):
        d = self.api.get("/markets/" + ticker)
        return ((d or {}).get("market") or {}).get("status") in ("open", "active")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--init", action="store_true")
    ap.add_argument("--extend", type=int, default=0, help="PLAN AMENDMENT 1: add N programs from the stored seeded orders")
    ap.add_argument("--file", default=DRAW_FILE)
    a = ap.parse_args()
    if not a.init and not a.extend:
        ap.error("--init or --extend N required")
    api = KL.Api(gap=0.25)
    dr = Draw(a.file)
    if a.extend:
        rows = pull_programs(api)
        if rows is None:
            sys.exit("program pull failed")
        progs = dr.extend(rows, time.time(), CatCache(api), OpenCheck(api), a.extend)
        print(len(progs), "programs added; active", len(dr.active), "; req", api.n_req)
        return
    if dr.initialised:
        sys.exit("draw already exists")
    rows = pull_programs(api)
    if rows is None:
        sys.exit("program pull failed")
    now = time.time()
    progs = dr.init(rows, now, CatCache(api), OpenCheck(api))
    print(len(progs), "programs drawn; req", api.n_req)


if __name__ == "__main__":
    main()
