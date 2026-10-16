"""PAPER-ONLY real-time NFL LIP bot.  Quotes nothing anywhere: reads the books written by the running recorder live/kxlipbook.py and
public trades (GET /markets/trades, no keys), decides what the base touch strategy (100 each side at the best bid, klb validity rules,
inventory cap 2x size) would quote, scores our official LIP snapshot share, and paper-fills queue-aware (PLAN_NFL_LIP_VALIDATE addendum 2).
Purpose: measure real-time latency / book staleness, to compare with the after-the-fact scorer (backfill/nfl_lip_forward.py).

  .venv/bin/python live/nfllip_paper.py [--root live/kxlipbook] [--out live/nfllip_paper.jsonl] [--series N|C|A,B] [--max-seconds S]

Output lines (jsonl): {"k":"q",...} one per ticker per sweep; {"k":"fill",...}; {"k":"hourly",...} summary.
Conventions (conservative): a quote becomes live at the wall time we decided it (not the book time); fills ignore fees; cancels
come from BEHIND us (queue ahead only shrinks by prints); reward accrues from each new book record held until the next (<= 60 s),
excluded snapshots = 0; inventory is marked to the last book mid (no settlement)."""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import time
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kxlipbook as KL  # noqa: E402  (Api GET wrapper, iso_ts, fnum, series lists; stdlib + requests only)

SIZE, CAP_MULT, EPS = 100.0, 2, 1e-9
MAX_DT = 60.0


# ---------------------------------------------------------------------------------------------------------- vendored helpers
def side_official(levels, target, disc, ours, px):
    """verbatim copy of backfill/kalshi_lip_official.side_official (unit-tested equal): our normalised share of one side, or None."""
    lv = {}
    for p, q in levels:
        lv[round(p, 4)] = lv.get(round(p, 4), 0.0) + q
    if ours > 0 and px is not None:
        lv[round(px, 4)] = lv.get(round(px, 4), 0.0) + ours
    cum, ref, qual = 0.0, None, []
    for p in sorted(lv, reverse=True):
        cum += lv[p]
        qual.append(p)
        if ref is None and cum >= target / 5:
            ref = p
        if cum >= target:
            break
    else:
        return None
    tot = sum(disc ** max(0, round((ref - p) * 100)) * lv[p] for p in qual)
    if ours <= 0 or px is None or round(px, 4) not in qual:
        return 0.0
    return disc ** max(0, round((ref - px) * 100)) * ours / tot


def read_gz_bytes(path):
    """decompress a (possibly truncated, multi-member) recorder gzip: the open hourly file has no end-of-stream marker."""
    with open(path, "rb") as f:
        data = f.read()
    out = []
    while data:
        d = zlib.decompressobj(31)
        try:
            out.append(d.decompress(data))
        except zlib.error:
            break
        if not d.eof:
            break
        data = d.unused_data
    return b"".join(out)


def iter_lines(path):
    lines = read_gz_bytes(path).decode("utf-8", "replace").split("\n")
    if lines and lines[-1] != "":                                    # unterminated last line = partial write
        lines = lines[:-1]
    return [l for l in lines if l]


# ---------------------------------------------------------------------------------------------------------- core logic
def best_first(raw):
    """recorder side [[price,size],..] ascending (best bid last) -> [(price,size)] best first, size > 0."""
    return [(float(p), float(q)) for p, q in reversed(raw or []) if p is not None and q is not None and q > 0]


def decide(yl, nl, inv, size=SIZE, cap=SIZE * CAP_MULT):
    """base touch quote: [yes_px, no_px] (None = no quote).  klb rules: price in (0.0005, 0.9995), not crossed, side under cap."""
    px = [yl[0][0] if yl else None, nl[0][0] if nl else None]
    if px[0] is not None and px[1] is not None and px[0] + px[1] >= 1 - EPS:        # crossed book: neither
        return [None, None]
    return [p if (p is not None and 0.0005 < p < 0.9995 and inv[i] < cap - EPS) else None for i, p in enumerate(px)]


def snapshot(yl, nl, q, target, disc, size=SIZE):
    """-> (share_yes, share_no, excluded).  Excluded (either side cannot reach target) counts 0 reward."""
    sy = side_official(yl, target, disc, size if q[0] is not None else 0.0, q[0])
    sn = side_official(nl, target, disc, size if q[1] is not None else 0.0, q[1])
    return sy, sn, sy is None or sn is None


def mid_of(yl, nl):
    if yl and nl and yl[0][0] + nl[0][0] < 1 - EPS:
        return (yl[0][0] + 1 - nl[0][0]) / 2
    return None


def fill_print(qo, rest, inv, minute, px, c, size=SIZE, cap=SIZE * CAP_MULT):
    """one print against a quote object qo={'px','ahead'}.  rest=[minute, remaining]; inv=current contracts on this side.
    Through our price: queue ahead cleared, fill min(print, rest).  At our price: fills once size ahead is exhausted.  Returns filled size."""
    if qo is None:
        return 0.0
    if rest[0] != minute:
        rest[0], rest[1] = minute, min(size, cap - inv)
    if rest[1] <= EPS or inv >= cap - EPS:
        return 0.0
    if px < qo["px"] - EPS:
        qo["ahead"] = 0.0
        f = c
    elif abs(px - qo["px"]) <= EPS:
        a = qo["ahead"] or 0.0
        if a >= c:
            qo["ahead"] = a - c
            return 0.0
        qo["ahead"] = 0.0
        f = c - a
    else:
        return 0.0
    f = min(f, rest[1])
    rest[1] -= f
    return f


class Tk:
    """paper state of one ticker."""

    def __init__(self, prog):
        self.p = prog
        self.inv, self.cost = [0.0, 0.0], [0.0, 0.0]
        self.cur = [None, None]                     # current quote objects per side
        self.hist = []                              # (eff_time, [qo_yes, qo_no])
        self.rest = [[-1, 0.0], [-1, 0.0]]
        self.reward, self.fills, self.mid = 0.0, 0, None
        self.prev_ts, self.prev_share = None, 0.0
        self.last_book_ts = None

    def on_book(self, ts, now, yl, nl):
        """new book record -> log dict.  Accrue reward of the previous snapshot over (prev_ts, ts], then re-decide."""
        p = self.p
        if self.prev_ts is not None and self.prev_share:
            dt = max(0.0, min(min(ts, p["s1"]), self.prev_ts + MAX_DT) - max(self.prev_ts, p["s0"]))
            self.reward += p["pool"] * self.prev_share * dt / (p["s1"] - p["s0"])
        q = decide(yl, nl, self.inv)
        for i, (lv, px) in enumerate(((yl, q[0]), (nl, q[1]))):
            if px is None:
                self.cur[i] = None
            elif self.cur[i] is None or abs(self.cur[i]["px"] - px) > EPS:
                self.cur[i] = {"px": px, "ahead": dict(lv).get(px, 0.0)}      # (re)join at the back of the queue
        self.hist.append((now, list(self.cur)))
        self.hist = [h for h in self.hist if h[0] > now - 1800]
        sy, sn, ex = snapshot(yl, nl, q, p["target"], p["disc"])
        self.prev_ts, self.prev_share = ts, (0.0 if ex else (sy + sn) / 2)
        self.last_book_ts, self.mid = ts, mid_of(yl, nl) or self.mid
        return q, sy, sn, ex

    def on_trade(self, ts, yp, np_, c, taker):
        """public print -> list of (side, price, filled).  taker 'no' sold YES into yes bids; taker 'yes' bought YES into no bids."""
        side = 0 if taker == "no" else 1 if taker == "yes" else None
        if side is None:
            return []
        h = None
        for e in self.hist:                         # quote in effect at the print
            if e[0] <= ts:
                h = e
        if h is None or h[1][side] is None:
            return []
        f = fill_print(h[1][side], self.rest[side], self.inv[side], int(ts // 60), (yp, np_)[side], c)
        if f > EPS:
            px = h[1][side]["px"]
            self.inv[side] += f
            self.cost[side] += f * px
            self.fills += 1
            return [(side, px, f)]
        return []

    def mark_pnl(self):
        if self.mid is None:
            return 0.0
        return self.inv[0] * self.mid - self.cost[0] + self.inv[1] * (1 - self.mid) - self.cost[1]


# ---------------------------------------------------------------------------------------------------------- io
def files(root, stream):
    return sorted(glob.glob(os.path.join(root, "*", f"{stream}_*.jsonl.gz")))


def active_programs(root, series, now):
    """latest row per liquidity program id from the last 3 meta files; active = start <= now < end."""
    best = {}
    for p in files(root, "meta")[-3:]:
        for l in iter_lines(p):
            if not (l.startswith('{"k":"prog"') or l.startswith('{"k":"progs_full"')):
                continue
            try:
                o = json.loads(l)
            except ValueError:
                continue
            for r in ([o["row"]] if o["k"] == "prog" else o.get("rows", [])):
                if r.get("incentive_type") == "liquidity" and (r["id"] not in best or o["ts"] >= best[r["id"]][0]):
                    best[r["id"]] = (o["ts"], r)
    out = {}
    for _, r in best.values():
        tk, s0, s1 = r["market_ticker"], KL.iso_ts(r["start_date"]), KL.iso_ts(r["end_date"])
        tg = KL.fnum(r.get("target_size_fp"))
        if KL.series_of(tk) in series and s0 and s1 and s0 <= now < s1 and not r.get("paid_out") and tg:
            out[tk] = dict(ticker=tk, s0=s0, s1=s1, pool=r["period_reward"] / 10000.0, target=tg, disc=r["discount_factor_bps"] / 10000.0)
    return out


def latest_books(root, wanted):
    """newest book record per wanted ticker from the newest (up to 2) books files."""
    res = {}
    for p in reversed(files(root, "books")[-2:]):
        for l in iter_lines(p):
            if not l.startswith('{"k":"b"'):
                continue
            i = l.find('"t":"') + 5
            tk = l[i:l.find('"', i)]
            if tk in wanted:
                try:
                    o = json.loads(l)
                except ValueError:
                    continue
                if tk not in res or o["ts"] > res[tk]["ts"]:
                    res[tk] = o
        if len(res) == len(wanted):
            break
    return res


class Bot:
    def __init__(self, a, api=None, clock=time.time):
        self.a, self.api, self.now = a, api or KL.Api(), clock
        self.T, self.progs, self.seen = {}, {}, {}
        self.tape_hi, self.t_prog, self.t_tape, self.t_sum, self.t_hb = None, 0.0, 0.0, self.now(), 0.0
        self.out = open(a.out, "a")
        self.n_fail = 0

    def w(self, o):
        self.out.write(json.dumps(o, separators=(",", ":")) + "\n")

    def sweep(self):
        now = self.now()
        if now - self.t_prog >= 60:
            self.t_prog = now
            self.progs = active_programs(self.a.root, self.a.series, now)
            for tk, p in self.progs.items():
                if tk not in self.T:
                    self.T[tk] = Tk(p)
        act = {tk: p for tk, p in self.progs.items() if p["s0"] <= now < p["s1"]}
        books = latest_books(self.a.root, set(act)) if act else {}
        for tk in act:
            b, t = books.get(tk), self.T[tk]
            if b is None:
                continue
            new = b["ts"] != t.last_book_ts
            line = {"k": "q", "ts": round(now, 3), "ticker": tk, "book_ts": b["ts"], "age": round(now - b["ts"], 3), "new": new}
            if new:
                q, sy, sn, ex = t.on_book(b["ts"], now, best_first(b["y"]), best_first(b["n"]))
                line.update(qy=q[0], qn=q[1], share_yes=sy, share_no=sn, excluded=ex)
            else:
                line.update(qy=t.cur[0] and t.cur[0]["px"], qn=t.cur[1] and t.cur[1]["px"], excluded=None)
            line.update(inv=t.inv, reward=round(t.reward, 6))
            self.w(line)
        self.out.flush()

    def poll_tape(self):
        now = self.now()
        if self.tape_hi is None:
            self.tape_hi = now - 30
        cur, pages, hi, trs_all = None, 0, self.tape_hi, []
        while pages < 40:
            p = {"min_ts": int(self.tape_hi - 10), "limit": 1000}
            if cur:
                p["cursor"] = cur
            d = self.api.get("/markets/trades", p)
            if d is None:
                self.n_fail += 1
                if pages == 0:
                    return
                break
            pages += 1
            trs = d.get("trades") or []
            for x in trs:
                ct = KL.iso_ts(x.get("created_time", ""))
                if ct is None:
                    continue
                hi = max(hi, ct)
                if x.get("ticker") in self.T and x["trade_id"] not in self.seen:
                    self.seen[x["trade_id"]] = ct
                    trs_all.append((ct, x))
            cur = d.get("cursor")
            if not cur or not trs:
                break
        self.tape_hi = hi
        self.seen = {k: v for k, v in self.seen.items() if v > hi - 1800}
        for ct, x in sorted(trs_all, key=lambda z: z[0]):
            t = self.T[x["ticker"]]
            for side, px, f in t.on_trade(ct, KL.fnum(x.get("yes_price_dollars")), KL.fnum(x.get("no_price_dollars")),
                                          KL.fnum(x.get("count_fp")) or 0.0, x.get("taker_side")):
                self.w({"k": "fill", "ts": round(self.now(), 3), "trade_ts": ct, "ticker": x["ticker"], "side": ("yes", "no")[side],
                        "px": px, "size": f, "inv": t.inv})
        self.out.flush()

    def summary(self):
        now = self.now()
        ages = sorted(now - t.last_book_ts for t in self.T.values() if t.last_book_ts)
        o = {"k": "hourly", "ts": round(now, 3), "tickers": len(self.T), "active": len(self.progs),
             "est_reward": round(sum(t.reward for t in self.T.values()), 4), "fills": sum(t.fills for t in self.T.values()),
             "contracts": sum(sum(t.inv) for t in self.T.values()), "mark_pnl": round(sum(t.mark_pnl() for t in self.T.values()), 4),
             "age_median": ages[len(ages) // 2] if ages else None, "age_max": ages[-1] if ages else None}
        self.w(o)
        self.out.flush()
        return o

    def run(self, max_seconds=None):
        t0 = self.now()
        while max_seconds is None or self.now() - t0 < max_seconds:
            s = self.now()
            try:
                self.sweep()
                if s - self.t_tape >= 60 and self.T:
                    self.t_tape = s
                    self.poll_tape()
                if s - self.t_sum >= self.a.summary_every:
                    self.t_sum = s
                    print(time.strftime("%H:%M:%S"), "SUMMARY", json.dumps(self.summary()), flush=True)
                if s - self.t_hb >= 60:
                    self.t_hb = s
                    print(time.strftime("%H:%M:%S"), f"HB active={len(self.progs)} tickers={len(self.T)} reward={sum(t.reward for t in self.T.values()):.4f} "
                          f"fills={sum(t.fills for t in self.T.values())} tape_fail={self.n_fail}", flush=True)
            except Exception as e:                  # never die unattended
                print(time.strftime("%H:%M:%S"), "ERR", type(e).__name__, str(e)[:200], flush=True)
            time.sleep(max(0.0, self.a.sweep - (self.now() - s)))
        print(time.strftime("%H:%M:%S"), "FINAL", json.dumps(self.summary()), flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.path.join(HERE, "kxlipbook"))
    ap.add_argument("--out", default=os.path.join(HERE, "nfllip_paper.jsonl"))
    ap.add_argument("--series", default="N", help="N (NFL ladders, default), C (15-min commodity/FX) or comma list of series")
    ap.add_argument("--max-seconds", type=float, default=None)
    ap.add_argument("--sweep", type=float, default=15.0)
    ap.add_argument("--summary-every", type=float, default=3600.0)
    a = ap.parse_args()
    a.series = set(KL.FAM_N if a.series == "N" else KL.FAM_C if a.series == "C" else a.series.split(","))
    Bot(a).run(a.max_seconds)


if __name__ == "__main__":
    main()
