"""Read-only forward recorder for the Kalshi liquidity-incentive (LIP) paper-LP plan (results/PLAN_KALSHI_LIP.md).
Public endpoints only: no keys, no auth, no orders.  Needed for gate (3): our measurable share of the pool.

What it records (UTC date dir  live/kxlipbook/YYYY-MM-DD/, hourly gzip files, one JSON object per line):
  books_HH.jsonl.gz  every --sweep s (15): full raw order books (batched, <=100 tickers per request) for
                       * family N : tickers with an ACTIVE liquidity program in the 7 NFL ladder series
                       * family C : every OPEN market of the 12 fifteen-minute commodity/FX series
                       * controls : KXRT (program-active tickers) and KXCRYPTOLEAD15M (open markets)
                     {"k":"b","s":sweep_id,"ts":..,"t":ticker,"y":[[price,size],..],"n":[[price,size],..]}  (y/n = yes/no bids,
                     ascending price, best bid last).  A book is written only when it CHANGED vs the last written one, on the
                     first sweep of each hour, and at least every 10 min; so an unchanged book is implied (forward-fill within
                     the file) unless the ticker is in the sweep line's "miss" list.
                     {"k":"sw","s":..,"ts0":..,"ts1":..,"n":requested,"ok":fetched,"miss":[tickers not fetched]}
  tape_HH.jsonl.gz   trade tape for every market of the tracked series, from the global /markets/trades feed, polled each minute
                     {"k":"tr","ts":created_time,"t":ticker,"id":trade_id,"yp":yes_price,"np":no_price,"c":count,"ts_side":taker_side,"blk":bool}
  meta_HH.jsonl.gz   {"k":"prog"} new/changed program rows (every --prog-every s); {"k":"progs_full"} the whole tracked program table
                     hourly; {"k":"mkt"} market meta (first seen + hourly).
Log: live/kxlipbook.log (and stdout), one HB heartbeat line per minute.
Survives outages (school Wi-Fi blackout): every call retries with backoff and returns None on failure; the loop never raises;
failed sweeps are logged as ok=0 sweep lines.  Gaps are visible as missing/ok=0 sweeps.

  .venv/bin/python -u live/kxlipbook.py                 # run forever (launch from live/ or repo root)
  .venv/bin/python -u live/kxlipbook.py --max-seconds 180   # bounded test run
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import logging
import os
import signal
import sys
import time
import zlib
from datetime import datetime, timezone

import requests

BASE = "https://api.elections.kalshi.com/trade-api/v2"
HERE = os.path.dirname(os.path.abspath(__file__))

FAM_N = ["KXNFLFFPTSLADDER", "KXNFLESCALATORREC", "KXNFLLADDERRECYDS", "KXNFLLADDERREC",
         "KXNFLESCALATORRECYDS", "KXNFLESCALATORRSHYDS", "KXNFLLADDERRSHYDS"]
FAM_C = ["KXGOLD15M", "KXSILVER15M", "KXWTI15M", "KXNATGAS15M", "KXCOPPER15M", "KXPLATINUM15M", "KXPALLADIUM15M",
         "KXEURUSD15M", "KXGBPUSD15M", "KXUSDJPY15M", "KXAUDUSD15M", "KXUSDCAD15M"]
# controls (my choice): KXRT = long-window (~7 d) non-sport LIP series, ~210 markets, liquid books -> checks that measured
# share is not NFL-specific; KXCRYPTOLEAD15M = the one crypto 15-min series with a liquidity LIP -> a 15-min control for C.
CTL_PROG = ["KXRT"]
CTL_OPEN = ["KXCRYPTOLEAD15M"]
PROG_DRIVEN = FAM_N + CTL_PROG        # universe = tickers with an active program window
OPEN_DRIVEN = FAM_C + CTL_OPEN        # universe = every open market (programs open/close with the 15-min market)
TRACKED = set(PROG_DRIVEN + OPEN_DRIVEN)
MKT_KEYS = ["ticker", "event_ticker", "status", "open_time", "close_time", "occurrence_datetime", "expected_expiration_time",
            "expiration_time", "price_level_structure", "floor_strike", "strike_type", "volume_fp", "open_interest_fp",
            "yes_bid_dollars", "yes_ask_dollars", "last_price_dollars", "result", "settlement_value_dollars", "title"]

log = logging.getLogger("kxlipbook")


def series_of(ticker: str) -> str:
    return ticker.split("-")[0]


def iso_ts(s):
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


class Api:
    """GET wrapper: spacing, retries with backoff, never raises. Returns parsed JSON or None; .last_status of the last try."""

    def __init__(self, gap=0.12, tries=4, timeout=25):
        self.s = requests.Session()
        self.s.headers["User-Agent"] = "kxlipbook-readonly/1.0"
        self.gap, self.tries, self.timeout = gap, tries, timeout
        self.t_last = 0.0
        self.n_req = self.n_err = self.n_ok = 0
        self.last_status = None
        self.last_err_log = 0.0

    def get(self, path, params=None):
        for a in range(self.tries):
            dt = self.gap - (time.time() - self.t_last)
            if dt > 0:
                time.sleep(dt)
            self.t_last = time.time()
            self.n_req += 1
            try:
                r = self.s.get(BASE + path, params=params, timeout=self.timeout)
                self.last_status = r.status_code
                if r.status_code == 429 or r.status_code >= 500:
                    ra = r.headers.get("Retry-After")
                    wait = min(60.0, float(ra)) if ra and ra.replace(".", "", 1).isdigit() else min(60.0, 2.0 ** (a + 1))
                    self._err(f"HTTP {r.status_code} {path}; backoff {wait:.0f}s")
                    time.sleep(wait)
                    continue
                if r.status_code >= 400:                       # client error: retrying is pointless
                    self.n_err += 1
                    return None
                self.n_ok += 1
                return r.json()
            except (requests.RequestException, ValueError) as e:
                self.last_status = None
                self._err(f"{type(e).__name__} {path}: {str(e)[:120]}")
                time.sleep(min(30.0, 2.0 ** a))
        self.n_err += 1
        return None

    def _err(self, msg):
        if time.time() - self.last_err_log > 30:              # rate-limit error logging (outages are hours long)
            self.last_err_log = time.time()
            log.warning(msg)


class Out:
    """Hourly gzip jsonl writers: root/YYYY-MM-DD/<stream>_HH.jsonl.gz, appended (concatenated gzip members), sync-flushed."""

    def __init__(self, root):
        self.root = root
        self.f = {}                                            # stream -> (path, GzipFile)
        self.lines = collections.Counter()

    def path(self, stream, ts):
        d = datetime.fromtimestamp(ts, timezone.utc)
        return os.path.join(self.root, d.strftime("%Y-%m-%d"), f"{stream}_{d.strftime('%H')}.jsonl.gz")

    def write(self, stream, ts, obj):
        p = self.path(stream, ts)
        cur = self.f.get(stream)
        if cur is None or cur[0] != p:
            if cur:
                cur[1].close()
            os.makedirs(os.path.dirname(p), exist_ok=True)
            cur = (p, gzip.GzipFile(p, "ab", compresslevel=6))
            self.f[stream] = cur
        cur[1].write((json.dumps(obj, separators=(",", ":")) + "\n").encode())
        self.lines[stream] += 1

    def flush(self):
        for _, g in self.f.values():
            g.flush(zlib.Z_SYNC_FLUSH)                         # data readable even if we are killed / the laptop sleeps

    def close(self):
        for _, g in self.f.values():
            g.close()
        self.f = {}

    def day_bytes(self, ts):
        d = os.path.dirname(self.path("x", ts))
        try:
            return sum(os.path.getsize(os.path.join(d, x)) for x in os.listdir(d))
        except OSError:
            return 0


def fnum(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def levels(raw):
    return [[fnum(p), fnum(q)] for p, q in (raw or [])]


class Recorder:
    def __init__(self, api, root, clock=time.time, sleep=time.sleep, sweep_s=15.0, prog_every=300.0, disc_every=60.0,
                 tape_every=60.0, meta_every=3600.0, keyframe_s=600.0, batch=100, tape_pages=80):
        self.api, self.out, self.now, self.sleep = api, Out(root), clock, sleep
        self.sweep_s, self.prog_every, self.disc_every = sweep_s, prog_every, disc_every
        self.tape_every, self.meta_every, self.keyframe_s = tape_every, meta_every, keyframe_s
        self.batch, self.tape_pages = batch, tape_pages
        self.prog = {}                 # id -> row (tracked series, all statuses seen in the active pull)
        self.prog_active = {}          # ticker -> (start, end) for program-driven series
        self.open15 = {}               # ticker -> market meta for open-driven series
        self.meta_seen = {}            # ticker -> ts meta last written
        self.last_book = {}            # ticker -> (key, ts_written)
        self.hour_of_last_sweep = None
        self.sweep_id = 0
        self.due = {"prog": 0.0, "disc": 0.0, "tape": 0.0, "meta": 0.0, "progfull": 0.0}
        self.tape_hi = None
        self.tape_ids = collections.OrderedDict()
        self.stop = False
        self.c = collections.Counter()                         # counters since last heartbeat
        self.consec_fail = 0
        self.last_ok = self.now()

    # ---- universe -------------------------------------------------------------------------------------------------
    def refresh_programs(self):
        t = self.now()
        rows, cur, ok = [], None, True
        for _ in range(40):
            p = {"status": "active", "type": "liquidity", "limit": 1000}
            if cur:
                p["cursor"] = cur
            d = self.api.get("/incentive_programs", p)
            if d is None:
                ok = False
                break
            rows += d.get("incentive_programs") or []
            cur = d.get("next_cursor")
            if not cur or not d.get("incentive_programs"):
                break
        if not rows and not ok:
            self.c["prog_fail"] += 1
            return
        act = {}
        for r in rows:
            if r.get("incentive_type") != "liquidity":
                continue
            s = series_of(r["market_ticker"])
            if s not in TRACKED:
                continue
            old = self.prog.get(r["id"])
            if old != r:
                self.prog[r["id"]] = r
                self.out.write("meta", t, {"k": "prog", "ts": t, "row": r})
                self.c["prog_rows"] += 1
            if s in PROG_DRIVEN:
                a, b = iso_ts(r["start_date"]), iso_ts(r["end_date"])
                if a is not None and b is not None and a <= t < b:
                    act[r["market_ticker"]] = (a, b)
        if ok:                                                 # only replace the universe after a complete pull
            self.prog_active = act
        # forget finished programs from memory (keep ~1 day)
        self.prog = {k: v for k, v in self.prog.items() if (iso_ts(v["end_date"]) or 1e18) > t - 86400}
        self.c["prog_ok"] += 1

    def write_progs_full(self):
        t = self.now()
        self.out.write("meta", t, {"k": "progs_full", "ts": t, "rows": list(self.prog.values())})

    def list_open(self, series):
        out, cur = [], None
        for _ in range(10):
            p = {"series_ticker": series, "status": "open", "limit": 1000}
            if cur:
                p["cursor"] = cur
            d = self.api.get("/markets", p)
            if d is None:
                return None
            out += d.get("markets") or []
            cur = d.get("cursor")
            if not cur or not d.get("markets"):
                break
        return out

    def write_meta(self, m, force=False):
        t = self.now()
        tk = m["ticker"]
        if not force and tk in self.meta_seen and t - self.meta_seen[tk] < self.meta_every:
            return
        self.meta_seen[tk] = t
        self.out.write("meta", t, {"k": "mkt", "ts": t, "m": {k: m.get(k) for k in MKT_KEYS if k in m}})

    def discover(self):
        """Open markets of the open-driven series (every disc_every s)."""
        t = self.now()
        cur = {}
        for s in OPEN_DRIVEN:
            ms = self.list_open(s)
            if ms is None:
                cur.update({k: v for k, v in self.open15.items() if series_of(k) == s})   # keep last known on failure
                self.c["disc_fail"] += 1
                continue
            for m in ms:
                cur[m["ticker"]] = m
                self.write_meta(m)
        self.open15 = cur

    def refresh_meta(self):
        """Hourly meta for program-driven series (only tickers with an active program)."""
        for s in PROG_DRIVEN:
            ms = self.list_open(s)
            if ms is None:
                self.c["meta_fail"] += 1
                continue
            for m in ms:
                if m["ticker"] in self.prog_active:
                    self.write_meta(m, force=True)

    def universe(self):
        return sorted(set(self.prog_active) | set(self.open15))

    # ---- books ----------------------------------------------------------------------------------------------------
    def fetch_books(self, tickers, res):
        """res: ticker -> (yes, no). Splits a failing batch to isolate bad tickers."""
        if not tickers:
            return
        d = self.api.get("/markets/orderbooks", [("tickers", x) for x in tickers])
        if d is None:
            if self.api.last_status is not None and 400 <= self.api.last_status < 500 and len(tickers) > 1:
                h = len(tickers) // 2
                self.fetch_books(tickers[:h], res)
                self.fetch_books(tickers[h:], res)
            return
        for o in d.get("orderbooks") or []:
            ob = o.get("orderbook_fp") or {}
            res[o.get("ticker")] = (levels(ob.get("yes_dollars")), levels(ob.get("no_dollars")))

    def sweep(self):
        t0 = self.now()
        tickers = self.universe()
        self.sweep_id += 1
        hr = int(t0 // 3600)
        keyframe = hr != self.hour_of_last_sweep
        self.hour_of_last_sweep = hr
        res = {}
        for i in range(0, len(tickers), self.batch):
            self.fetch_books(tickers[i:i + self.batch], res)
        t1 = self.now()
        changed = 0
        for tk in tickers:
            if tk not in res:
                continue
            y, n = res[tk]
            key = json.dumps([y, n], separators=(",", ":"))
            prev = self.last_book.get(tk)
            if keyframe or prev is None or prev[0] != key or t1 - prev[1] >= self.keyframe_s:
                self.out.write("books", t1, {"k": "b", "s": self.sweep_id, "ts": round(t1, 3), "t": tk, "y": y, "n": n})
                self.last_book[tk] = (key, t1)
                changed += 1
        miss = [tk for tk in tickers if tk not in res]
        self.out.write("books", t1, {"k": "sw", "s": self.sweep_id, "ts0": round(t0, 3), "ts1": round(t1, 3),
                                     "n": len(tickers), "ok": len(res), "miss": miss if len(miss) <= 50 else miss[:50] + ["..."]})
        self.out.flush()
        self.c["sweeps"] += 1
        self.c["books_req"] += len(tickers)
        self.c["books_ok"] += len(res)
        self.c["books_written"] += changed
        if tickers and not res:
            self.consec_fail += 1
            self.c["sweeps_fail"] += 1
        else:
            if res:
                self.last_ok = t1
            self.consec_fail = 0
        # drop state of tickers that left the universe
        for tk in [k for k in self.last_book if k not in set(tickers)]:
            del self.last_book[tk]

    # ---- tape -----------------------------------------------------------------------------------------------------
    def poll_tape(self):
        t = self.now()
        if self.tape_hi is None:
            self.tape_hi = t - 90
        min_ts = int(self.tape_hi - 10)                        # 10 s overlap, dedup by trade_id
        cur, pages, hi, kept, capped = None, 0, self.tape_hi, 0, False
        while True:
            p = {"min_ts": min_ts, "limit": 1000}
            if cur:
                p["cursor"] = cur
            d = self.api.get("/markets/trades", p)
            if d is None:
                self.c["tape_fail"] += 1
                if pages == 0:
                    return                                     # nothing consumed; retry next poll with same min_ts
                break
            pages += 1
            trs = d.get("trades") or []
            for x in trs:
                ct = iso_ts(x.get("created_time", ""))
                if ct is None:
                    continue
                hi = max(hi, ct)
                tk = x.get("ticker", "")
                if series_of(tk) not in TRACKED or x["trade_id"] in self.tape_ids:
                    continue
                self.tape_ids[x["trade_id"]] = ct
                self.out.write("tape", ct, {"k": "tr", "ts": x["created_time"], "t": tk, "id": x["trade_id"],
                                            "yp": fnum(x.get("yes_price_dollars")), "np": fnum(x.get("no_price_dollars")),
                                            "c": fnum(x.get("count_fp")), "ts_side": x.get("taker_side"),
                                            "blk": bool(x.get("is_block_trade"))})
                kept += 1
            cur = d.get("cursor")
            if not cur or not trs:
                break
            if pages >= self.tape_pages:
                capped = True
                break
        if capped:
            self.c["tape_capped"] += 1
            log.warning("tape poll capped at %d pages: possible gap", pages)
        self.tape_hi = hi
        while self.tape_ids and next(iter(self.tape_ids.values())) < hi - 1800:
            self.tape_ids.popitem(last=False)
        self.out.flush()
        self.c["tape_written"] += kept
        self.c["tape_pages"] += pages

    # ---- loop -----------------------------------------------------------------------------------------------------
    def heartbeat(self):
        t = self.now()
        by = {"N": 0, "C": 0, "ctl": 0}
        for tk in self.universe():
            s = series_of(tk)
            by["N" if s in FAM_N else "C" if s in FAM_C else "ctl"] += 1
        c = self.c
        log.info("HB utc=%s sweeps=%d fail=%d books=%d/%d written=%d tape=%d prog_rows=%d univ=N%d/C%d/ctl%d req=%d err=%d "
                 "last_ok_age=%ds consec_fail=%d day_gz_MB=%.2f", datetime.fromtimestamp(t, timezone.utc).strftime("%H:%M:%S"),
                 c["sweeps"], c["sweeps_fail"], c["books_ok"], c["books_req"], c["books_written"], c["tape_written"],
                 c["prog_rows"], by["N"], by["C"], by["ctl"], self.api.n_req, self.api.n_err, int(t - self.last_ok),
                 self.consec_fail, self.out.day_bytes(t) / 1e6)
        self.c = collections.Counter()

    def tick_tasks(self):
        t = self.now()
        for name, fn, every in (("prog", self.refresh_programs, self.prog_every), ("disc", self.discover, self.disc_every)):
            if t >= self.due[name]:
                before = self.c[name + "_fail"]
                self._safe(fn)
                self.due[name] = t + (30.0 if self.c[name + "_fail"] > before else every)   # retry sooner after a failure
        if t >= self.due["meta"] and self.prog_active:
            self._safe(self.refresh_meta)
            self.due["meta"] = t + self.meta_every
        if t >= self.due["progfull"] and self.prog:
            self._safe(self.write_progs_full)
            self.due["progfull"] = t + 3600
            self.out.flush()

    def _safe(self, fn):
        try:
            fn()
        except Exception:
            log.exception("task %s crashed (continuing)", getattr(fn, "__name__", fn))
            self.c["task_exc"] += 1

    def run(self, max_seconds=None):
        t_start = self.now()
        nxt, next_hb = t_start, t_start + 60
        next_tape = t_start + 5
        log.info("START series N=%d C=%d ctl=%s out=%s sweep=%ss", len(FAM_N), len(FAM_C), CTL_PROG + CTL_OPEN, self.out.root,
                 self.sweep_s)
        try:
            while not self.stop:
                t = self.now()
                if max_seconds is not None and t - t_start >= max_seconds:
                    break
                if t >= nxt:
                    self._safe(self.tick_tasks)
                    self._safe(self.sweep)
                    if self.consec_fail:                       # outage: back off instead of hammering a dead link
                        self.sleep(min(60.0, 5.0 * 2 ** min(self.consec_fail, 4)))
                    nxt = max(nxt + self.sweep_s, self.now() + 1.0)
                    if self.now() > nxt:
                        self.c["overrun"] += 1
                if self.now() >= next_tape:
                    self._safe(self.poll_tape)
                    next_tape = self.now() + self.tape_every
                if self.now() >= next_hb:
                    self._safe(self.heartbeat)
                    next_hb += 60
                    if next_hb < self.now():
                        next_hb = self.now() + 60
                self.sleep(max(0.05, min(nxt, next_tape, next_hb) - self.now()))
        finally:
            self.heartbeat()
            self.out.close()
            log.info("STOP")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.path.join(HERE, "kxlipbook"))
    ap.add_argument("--sweep", type=float, default=15.0)
    ap.add_argument("--max-seconds", type=float, default=None)
    ap.add_argument("--log", default=os.path.join(HERE, "kxlipbook.log"))
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.FileHandler(a.log), logging.StreamHandler(sys.stdout)])
    rec = Recorder(Api(), a.root, sweep_s=a.sweep)
    for sg in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sg, lambda *_: setattr(rec, "stop", True))
    while True:                                                # last-resort guard: never exit because of a bug
        try:
            rec.run(a.max_seconds)
            break
        except Exception:
            log.exception("run loop crashed; restarting in 10 s")
            time.sleep(10)
            rec.out.close()


if __name__ == "__main__":
    main()
