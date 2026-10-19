"""Backtest of the frozen plan results/PLAN_KALSHI_LIP.md: paper LP on Kalshi liquidity-incentive (LIP) markets.
Public endpoints only: no keys, no auth, no orders.  Two sub-commands:

  .venv/bin/python backfill/kalshi_lip_bt.py dl      # resumable download -> backfill/data_local/kalshi_lip/lip.sqlite
  .venv/bin/python backfill/kalshi_lip_bt.py run     # DEV report (holdout stays locked)
  .venv/bin/python backfill/kalshi_lip_bt.py run --holdout   # the single look at HOLDOUT + final report (results/KALSHI_LIP_BT.md)

Design decisions that the plan leaves open are marked DECISION in the code and repeated in the report.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sqlite3
import sys
import time
import zlib
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data_local", "kalshi_lip")
DB = os.path.join(DATA, "lip.sqlite")
RESULTS = os.path.join(HERE, "..", "results")
B = "https://api.elections.kalshi.com/trade-api/v2"

FAM_N = ["KXNFLFFPTSLADDER", "KXNFLESCALATORREC", "KXNFLLADDERRECYDS", "KXNFLLADDERREC",
         "KXNFLESCALATORRECYDS", "KXNFLESCALATORRSHYDS", "KXNFLLADDERRSHYDS"]
FAM_C = ["KXGOLD15M", "KXSILVER15M", "KXWTI15M", "KXNATGAS15M", "KXCOPPER15M", "KXPLATINUM15M", "KXPALLADIUM15M",
         "KXEURUSD15M", "KXGBPUSD15M", "KXUSDJPY15M", "KXAUDUSD15M", "KXUSDCAD15M"]
SPLIT = "2026-09-20T00:00:00Z"        # DEV = windows ending before; HOLDOUT = windows from this date on
C_LOOKBACK_DAYS = 30
SIZE, CAP_MULT = 100, 2


def iso(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def series_of(t):
    return t.split("-")[0]


def fam_of(s):
    return "N" if s in FAM_N else "C" if s in FAM_C else None


# ====================================================================================================== download
class Api:
    def __init__(self, gap=0.1):
        self.s, self.gap, self.t = requests.Session(), gap, 0.0
        self.n = 0

    def get(self, path, **p):
        for a in range(10):
            dt = self.gap - (time.time() - self.t)
            if dt > 0:
                time.sleep(dt)
            self.t = time.time()
            self.n += 1
            try:
                r = self.s.get(B + path, params=p, timeout=60)
            except requests.RequestException as e:
                time.sleep(min(60, 2 ** a))
                continue
            if r.status_code == 429 or r.status_code >= 500:
                time.sleep(min(60, 2 ** (a + 1)))
                continue
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r.json()
        raise RuntimeError("giving up " + path)


SCHEMA = """
CREATE TABLE IF NOT EXISTS programs(id TEXT PRIMARY KEY, ticker TEXT, series TEXT, start_date TEXT, end_date TEXT,
  period_reward REAL, target REAL, disc REAL, descr TEXT, paid_out INT, status TEXT);
CREATE TABLE IF NOT EXISTS markets(ticker TEXT PRIMARY KEY, series TEXT, js TEXT);
CREATE TABLE IF NOT EXISTS trades(trade_id TEXT PRIMARY KEY, ticker TEXT, ts REAL, yes_price REAL, no_price REAL, cnt REAL,
  taker_side TEXT);
CREATE INDEX IF NOT EXISTS ix_tr ON trades(ticker, ts);
CREATE TABLE IF NOT EXISTS candles(ticker TEXT, end_ts INT, bid_c REAL, ask_c REAL, bid_l REAL, bid_h REAL, ask_l REAL, ask_h REAL,
  px_c REAL, vol REAL, PRIMARY KEY(ticker, end_ts));
CREATE TABLE IF NOT EXISTS done(kind TEXT, key TEXT, n INT, PRIMARY KEY(kind, key));
CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT);
"""


def db(path=DB):
    os.makedirs(DATA, exist_ok=True)
    c = sqlite3.connect(path, timeout=300)
    c.executescript(SCHEMA)
    return c


def fl(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def dl_programs(api, c, refresh=False):
    if not refresh and c.execute("select 1 from meta where k='programs_pull_ts'").fetchone():
        print("programs: cached", flush=True)
        return
    want = set(FAM_N + FAM_C)
    rows = {}
    for status in ("active", "closed", "paid_out"):
        cur, n = None, 0
        while True:
            p = {"status": status, "type": "liquidity", "limit": 1000}
            if cur:
                p["cursor"] = cur
            d = api.get("/incentive_programs", **p)
            for r in d["incentive_programs"]:
                n += 1
                if r.get("incentive_type") == "liquidity" and series_of(r["market_ticker"]) in want:
                    rows[r["id"]] = (r["id"], r["market_ticker"], series_of(r["market_ticker"]), r["start_date"], r["end_date"],
                                     r["period_reward"] / 10000.0, fl(r.get("target_size_fp")), r["discount_factor_bps"] / 10000.0,
                                     r.get("incentive_description"), int(bool(r.get("paid_out"))), status)
            cur = d.get("next_cursor")
            if not cur or not d["incentive_programs"]:
                break
        print(f"programs {status}: scanned {n}, tracked so far {len(rows)}", flush=True)
    c.execute("delete from programs")
    c.executemany("insert or replace into programs values(?,?,?,?,?,?,?,?,?,?,?)", list(rows.values()))
    c.execute("insert or replace into meta values('programs_pull_ts', ?)", (str(time.time()),))
    c.commit()


def select_windows(c):
    """Program windows in scope: ended >=2h before the pull, family N all, family C starting in the last 30 days of the pull."""
    pull = float(c.execute("select v from meta where k='programs_pull_ts'").fetchone()[0])
    P = pd.read_sql("select * from programs", c)
    P["s0"] = P.start_date.map(iso)
    P["s1"] = P.end_date.map(iso)
    P["fam"] = P.series.map(fam_of)
    c0 = pull - C_LOOKBACK_DAYS * 86400
    keep = (P.s1 <= pull - 7200) & (((P.fam == "N")) | ((P.fam == "C") & (P.s0 >= c0)))
    return P[keep].copy(), pull


def dl_markets(api, c, P):
    for s, g in P.groupby("series"):
        lo, hi = int(g.s1.min() - 86400), int(g.s1.max() + 2 * 86400)
        if c.execute("select 1 from done where kind='mkts' and key=?", (f"{s}:{lo}:{hi}",)).fetchone():
            continue
        cur, n = None, 0
        while True:
            p = {"series_ticker": s, "min_close_ts": lo, "max_close_ts": hi, "limit": 1000}
            if cur:
                p["cursor"] = cur
            d = api.get("/markets", **p)
            c.executemany("insert or replace into markets values(?,?,?)", [(m["ticker"], s, json.dumps(m)) for m in d["markets"]])
            n += len(d["markets"])
            cur = d.get("cursor")
            if not cur or not d["markets"]:
                break
        c.execute("insert or replace into done values('mkts',?,?)", (f"{s}:{lo}:{hi}", n))
        c.commit()
        print(f"markets {s}: {n}", flush=True)
    have = {r[0] for r in c.execute("select ticker from markets")}
    for t in sorted(set(P.ticker) - have):                     # stragglers outside the listing
        d = api.get(f"/markets/{t}")
        if d and d.get("market"):
            c.execute("insert or replace into markets values(?,?,?)", (t, series_of(t), json.dumps(d["market"])))
    c.commit()


def dl_trades(api, c, P):
    T = P.groupby("ticker").agg(s0=("s0", "min"), s1=("s1", "max")).reset_index()
    done = {r[0] for r in c.execute("select key from done where kind='trades'")}
    todo = T[~T.ticker.isin(done)]
    print(f"trades: {len(T)} markets, {len(todo)} to fetch", flush=True)
    t0 = time.time()
    for i, r in enumerate(todo.itertuples(), 1):
        rows, cur = [], None
        while True:
            p = {"ticker": r.ticker, "min_ts": int(r.s0 - 60), "max_ts": int(r.s1 + 60), "limit": 1000}
            if cur:
                p["cursor"] = cur
            d = api.get("/markets/trades", **p)
            for x in d["trades"]:
                rows.append((x["trade_id"], x["ticker"], iso(x["created_time"]), fl(x["yes_price_dollars"]), fl(x["no_price_dollars"]),
                             fl(x["count_fp"]), x["taker_side"]))
            cur = d.get("cursor")
            if not cur or not d["trades"]:
                break
        c.executemany("insert or ignore into trades values(?,?,?,?,?,?,?)", rows)
        c.execute("insert or replace into done values('trades',?,?)", (r.ticker, len(rows)))
        if i % 200 == 0:
            c.commit()
            print(f"  trades {i}/{len(todo)}  {time.time() - t0:.0f}s  reqs={api.n}", flush=True)
    c.commit()


def dl_candles(api, c, P):
    T = P.groupby("ticker").agg(s0=("s0", "min"), s1=("s1", "max")).reset_index()
    done = {r[0] for r in c.execute("select key from done where kind='candles'")}
    T = T[~T.ticker.isin(done)].sort_values("s1")
    print(f"candles: {len(T)} markets to fetch", flush=True)
    # greedy batches under the API cap (n_markets x span_minutes <= 10000)
    batches, cur = [], []
    for r in T.itertuples():
        trial = cur + [r]
        span = (max(x.s1 for x in trial) - min(x.s0 for x in trial)) / 60 + 4
        if cur and (len(trial) * span > 9000 or len(trial) > 100):
            batches.append(cur)
            cur = [r]
        else:
            cur = trial
    if cur:
        batches.append(cur)
    t0 = time.time()
    for i, b in enumerate(batches, 1):
        lo, hi = int(min(x.s0 for x in b) - 120), int(max(x.s1 for x in b) + 60)
        if len(b) == 1:                                        # single-market endpoint: <=5000 candles per request -> chunk
            cs = []
            for x0 in range(lo, hi, 4000 * 60):
                d = api.get(f"/series/{series_of(b[0].ticker)}/markets/{b[0].ticker}/candlesticks", start_ts=x0,
                            end_ts=min(hi, x0 + 4000 * 60), period_interval=1)
                cs += (d or {}).get("candlesticks", [])
            ms = [{"market_ticker": b[0].ticker, "candlesticks": cs}]
        else:
            d = api.get("/markets/candlesticks", market_tickers=",".join(x.ticker for x in b), start_ts=lo, end_ts=hi, period_interval=1)
            ms = d["markets"]
        rows = []
        for m in ms:
            for k in m["candlesticks"]:
                f = lambda a, b_: (k.get(a) or {}).get(b_)
                rows.append((m["market_ticker"], k["end_period_ts"], fl(f("yes_bid", "close_dollars")), fl(f("yes_ask", "close_dollars")),
                             fl(f("yes_bid", "low_dollars")), fl(f("yes_bid", "high_dollars")), fl(f("yes_ask", "low_dollars")),
                             fl(f("yes_ask", "high_dollars")), fl(f("price", "close_dollars")), fl(k.get("volume_fp"))))
        c.executemany("insert or replace into candles values(?,?,?,?,?,?,?,?,?,?)", rows)
        c.executemany("insert or replace into done values('candles',?,?)",
                      [(x.ticker, sum(1 for r in rows if r[0] == x.ticker)) for x in b])
        c.commit()
        if i % 25 == 0 or i == len(batches):
            print(f"  candle batches {i}/{len(batches)}  {time.time() - t0:.0f}s  reqs={api.n}", flush=True)


def cmd_dlc(a):
    """Candles only, into a side database (lets the backtest be tested while the long trade download is still running)."""
    api = Api()
    c0 = db()
    P, pull = select_windows(c0)
    c = db(os.path.join(DATA, "lip_candles.sqlite"))
    dl_candles(api, c, P)
    print("candles side-db complete", flush=True)


def cmd_dl(a):
    api, c = Api(), db()
    dl_programs(api, c, a.refresh_programs)
    P, pull = select_windows(c)
    print(f"windows in scope: {len(P)} ({P.groupby('fam').size().to_dict()}), markets {P.ticker.nunique()}, pull={datetime.fromtimestamp(pull, timezone.utc)}", flush=True)
    dl_markets(api, c, P)
    dl_trades(api, c, P)
    dl_candles(api, c, P)
    print("download complete", flush=True)


# ====================================================================================================== backtest
FEE_RATE = 0.0175               # general maker-fee formula (only used for the SENSITIVITY column; series fee_type is 'quadratic' = no maker fee)
SHIFTS = (-1800, 0, 1800)       # kickoff = occurrence_datetime - 3h, +/-30 min
CAP = CAP_MULT * SIZE
EPS = 1e-6
SEED = 20261013
N_PLACEBO = 100
VARIANTS = {"touch": 0, "back1": 1}


class Mk:
    """One program window / market, prepared as numpy arrays."""
    pass


def tick_arrays(js):
    pr = js.get("price_ranges") or [{"start": "0", "end": "1", "step": "0.01"}]
    pr = sorted(pr, key=lambda r: float(r["start"]))
    return np.array([float(r["start"]) for r in pr]), np.array([float(r["step"]) for r in pr])


def step_down(base, k, starts, steps):
    """base: array of prices (nan allowed); k: int array (ticks back).  One tick = step of the range just below the price."""
    p = base.copy()
    for i in range(1, int(k.max()) + 1 if len(k) else 1):
        m = (k >= i) & np.isfinite(p)
        if m.any():
            ix = np.clip(np.searchsorted(starts, p[m] - 1e-9, side="right") - 1, 0, len(steps) - 1)
            p[m] = np.round(p[m] - steps[ix], 4)
    return p


def build_mk(tk, pr, js, tdf, cdf):
    """pr: program row (s0,s1,period_reward,fam,series); js: market json; tdf/cdf: this ticker's trades / candles (sorted)."""
    m = Mk()
    tdf, cdf = tdf.sort_values("ts", kind="stable"), cdf.sort_values("end_ts", kind="stable")
    m.ticker, m.fam, m.series, m.pool = tk, pr.fam, pr.series, float(pr.period_reward)
    m.s0, m.s1 = float(pr.s0), float(pr.s1)
    m.close = iso(js["close_time"])
    m.end = min(m.s1, m.close)
    m.starts, m.steps = tick_arrays(js)
    sv = fl(js.get("settlement_value_dollars"))
    m.sv = sv
    m.kick = iso(js["occurrence_datetime"]) - 3 * 3600 if (m.fam == "N" and js.get("occurrence_datetime")) else float("nan")
    M0 = int(math.ceil(m.s0 / 60.0) * 60)
    nM = max(0, int(math.ceil((m.end - M0) / 60.0)))
    m.M = M0 + 60 * np.arange(nM)
    m.dur = np.minimum(60.0, m.end - m.M)
    ce = cdf.end_ts.values.astype(np.int64)
    b, a = cdf.bid_c.values.astype(float), cdf.ask_c.values.astype(float)
    pos = np.searchsorted(ce, m.M, side="right") - 1             # last candle that ENDED at or before the minute start
    okp = pos >= 0
    bb = np.where(okp, b[np.clip(pos, 0, None)], np.nan) if len(ce) else np.full(nM, np.nan)
    aa = np.where(okp, a[np.clip(pos, 0, None)], np.nan) if len(ce) else np.full(nM, np.nan)
    b_ok, a_ok = np.isfinite(bb) & (bb > 0) & (bb < 1), np.isfinite(aa) & (aa > 0) & (aa < 1)
    crossed = b_ok & a_ok & (bb >= aa)
    m.base = [np.where(b_ok & ~crossed, bb, np.nan), np.where(a_ok & ~crossed, np.round(1 - aa, 4), np.nan)]
    # forward-filled valid mid for the 60-min mark
    m.ce = ce
    good = np.isfinite(b) & np.isfinite(a) & (b > 0) & (a < 1) & (b < a) if len(ce) else np.array([], bool)
    m.mid = pd.Series(np.where(good, (b + a) / 2, np.nan)).ffill().values if len(ce) else np.array([])
    # prints inside the quoting window
    ts = tdf.ts.values
    k = (ts >= M0) & (ts < m.end)
    m.ts, m.cnt = ts[k], tdf.cnt.values[k]
    m.j = ((m.ts - M0) // 60).astype(np.int64)
    m.side_hit = (tdf.taker_side.values[k] == "yes").astype(np.int8)          # 0: taker sold YES (hits yes bids); 1: taker bought YES (hits no bids)
    m.px = [tdf.yes_price.values[k], tdf.no_price.values[k]]
    m.ix = [np.nonzero(m.side_hit == 0)[0], np.nonzero(m.side_hit == 1)[0]]
    return m


def alloc(j, c, size=SIZE, cap=CAP):
    """Sequential back-of-queue allocation: per minute the resting size is min(size, cap - filled so far); a print fills min(rest, print)."""
    out, cum, curj, rem = [], 0.0, -1, 0.0
    for jj, cc in zip(j, c):
        if jj != curj:
            curj = jj
            rem = min(size, cap - cum)
        if rem <= EPS:
            if cum >= cap - EPS:
                break
            out.append(0.0)
            continue
        f = cc if cc < rem else rem
        out.append(f)
        rem -= f
        cum += f
    out += [0.0] * (len(j) - len(out))                         # prints after the cap was reached
    return out


def sim(mk, ky, kn, full=True):
    """ky/kn: int arrays (ticks back per minute) for the YES and NO quote.  Returns dict of window metrics."""
    nM = len(mk.M)
    r = {"contracts": 0.0, "events": 0, "pnl": 0.0, "pnl_fee": 0.0, "pnl_mark": 0.0, "pool_both": 0.0, "pool_any": 0.0, "thru": 0.0}
    if nM == 0 or mk.sv is None:
        return r
    span = mk.s1 - mk.s0
    live, fills = [], []
    for side, k in ((0, ky), (1, kn)):
        q = step_down(mk.base[side], k, mk.starts, mk.steps)
        valid = np.isfinite(q) & (q > 0.0005) & (q < 0.9995)
        ix = mk.ix[side]
        fj = np.zeros(0, np.int64)
        ff = np.zeros(0)
        fi = np.zeros(0, np.int64)
        if len(ix):
            j = mk.j[ix]
            hit = valid[j] & (mk.px[side][ix] < q[j] - EPS)
            ci = np.nonzero(hit)[0]
            if len(ci):
                f = np.array(alloc(j[ci].tolist(), mk.cnt[ix][ci].tolist()))
                nz = f > EPS
                fj, ff, fi = j[ci][nz], f[nz], ix[ci][nz]
        bc = np.bincount(fj, weights=ff, minlength=nM) if len(fj) else np.zeros(nM)
        cs = np.cumsum(bc) - bc
        live.append(valid & (cs < CAP - EPS))
        fills.append((side, fj, ff, fi, q[fj] if len(fj) else np.zeros(0)))
    r["pool_both"] = mk.pool * float(mk.dur[live[0] & live[1]].sum()) / span
    r["pool_any"] = mk.pool * float(mk.dur[live[0] | live[1]].sum()) / span
    pre = {s: [0.0, 0.0, 0.0, 0.0, 0.0] for s in SHIFTS}
    for sft in SHIFTS:
        lb = live[0] & live[1]
        if np.isfinite(mk.kick):
            pre_m = mk.M < mk.kick + sft
            pre[sft][3] = mk.pool * float(mk.dur[lb & pre_m].sum()) / span          # pool accrued pre-kickoff (both sides live)
            pre[sft][4] = mk.pool * float(mk.dur[lb & ~pre_m].sum()) / span
    sv = mk.sv
    for side, fj, ff, fi, fq in fills:
        if not len(ff):
            continue
        ftime = mk.ts[fi]
        pay = (sv - fq) if side == 0 else ((1.0 - sv) - fq)
        pnl_i = ff * pay
        r["contracts"] += float(ff.sum())
        r["thru"] += float((ff * (fq - mk.px[side][fi])).sum())            # contract-weighted distance the print went through our price
        r["events"] += len(ff)
        r["pnl"] += float(pnl_i.sum())
        g = np.bincount(fj, weights=ff * fq * (1 - fq) * FEE_RATE)
        r["pnl_fee"] -= float(np.ceil(g[g > 0] * 100 - 1e-9).sum() / 100.0)
        if full:
            tm = ftime + 3600.0
            pos = np.searchsorted(mk.ce, tm, side="right") - 1
            midv = np.where((pos >= 0) & (tm < mk.close), mk.mid[np.clip(pos, 0, None)] if len(mk.mid) else np.nan, np.nan)
            use = np.where(np.isfinite(midv), midv, sv)                  # beyond close / no valid mid -> settlement value
            markpay = (use - fq) if side == 0 else ((1.0 - use) - fq)
            r["pnl_mark"] += float((ff * markpay).sum())
            if np.isfinite(mk.kick):
                for sft in SHIFTS:
                    m_ = ftime < mk.kick + sft
                    pre[sft][0] += float(pnl_i[m_].sum())
                    pre[sft][1] += float(pnl_i[~m_].sum())
                    pre[sft][2] += float(ff[m_].sum())
    r["pnl_fee"] += r["pnl"]
    if full and np.isfinite(mk.kick):
        for sft in SHIFTS:
            tag = {-1800: "m30", 0: "k0", 1800: "p30"}[sft]
            r[f"pnl_pre_{tag}"], r[f"pnl_in_{tag}"], r[f"ctr_pre_{tag}"], r[f"pool_pre_{tag}"], r[f"pool_in_{tag}"] = pre[sft]
    if not full:
        r.pop("pnl_mark")
    return r


def load_universe():
    c = sqlite3.connect(DB, timeout=600)
    P, pull = select_windows(c)
    M = {t: json.loads(js) for t, js in c.execute("select ticker, js from markets")}
    T = pd.read_sql("select ticker, ts, yes_price, no_price, cnt, taker_side from trades order by ticker, ts", c)
    cdb = os.environ.get("KLIP_CDB")                           # testing only: candles from the side database
    cc = sqlite3.connect(cdb, timeout=600) if cdb else c
    C = pd.read_sql("select ticker, end_ts, bid_c, ask_c, vol from candles order by ticker, end_ts", cc)
    dn = {r[0] for r in c.execute("select key from done where kind='trades'")}
    dc = {r[0] for r in cc.execute("select key from done where kind='candles'")}
    return P, pull, M, T, C, dn, dc


def build_all(P, M, T, C, dn, dc):
    tg = {t: g for t, g in T.groupby("ticker", sort=False)}
    cg = {t: g for t, g in C.groupby("ticker", sort=False)}
    empty_t = T.iloc[0:0]
    mks, drop = {}, {}
    for pr in P.itertuples():
        tk = pr.ticker
        js = M.get(tk)
        why = None
        if js is None:
            why = "no market meta"
        elif js.get("status") not in ("finalized", "settled") or fl(js.get("settlement_value_dollars")) is None:
            why = "unsettled/void"
        elif tk not in dn or tk not in dc:
            why = "not downloaded"
        elif tk not in cg:
            why = "no 1-min candles"
        if why:
            drop[tk] = why
            continue
        td, cd = tg.get(tk, empty_t), cg[tk]
        # tape completeness: contracts in the tape vs candle volume over the same minutes
        a0, a1 = math.floor(pr.s0 / 60) * 60, math.ceil(pr.s1 / 60) * 60
        tv = float(td.cnt[(td.ts >= a0) & (td.ts < a1)].sum())
        cv = float(cd.vol[(cd.end_ts > a0) & (cd.end_ts <= a1)].sum())
        if abs(tv - cv) > max(1.0, 0.02 * cv):
            drop[tk] = "tape != candle volume"
            continue
        mks[tk] = build_mk(tk, pr, js, td, cd)
        mks[tk].cl = pr.cluster
        mks[tk].split = pr.split
    return mks, drop


def prep_windows(P):
    P["fam"] = P.series.map(fam_of)
    P["split"] = np.where(P.s1 <= iso(SPLIT), "DEV", "HOLDOUT")
    st = pd.to_datetime(P.s0, unit="s", utc=True)
    iw = st.dt.isocalendar()
    P["cluster"] = np.where(P.fam == "N", iw.year.astype(str) + "-W" + iw.week.astype(str).str.zfill(2), st.dt.strftime("%Y-%m-%d"))
    return P


MKS = {}


def _work(args):
    split, tickers, placebo = args
    out, pl = [], []
    for tk in tickers:
        mk = MKS[tk]
        nM = len(mk.M)
        for name, k in VARIANTS.items():
            r = sim(mk, np.full(nM, k), np.full(nM, k))
            r.update(ticker=tk, variant=name)
            out.append(r)
        if placebo:
            rng = np.random.default_rng([SEED, zlib.crc32(tk.encode())])
            for d in range(N_PLACEBO):
                kk = rng.integers(0, 4, size=(2, nM))
                r = sim(mk, kk[0], kk[1], full=False)
                pl.append((tk, d, r["pnl"], r["pool_both"], r["contracts"]))
    return out, pl


def run_split(mks, which, placebo, procs=7):
    import multiprocessing as mp
    tks = [t for t, m in mks.items() if m.split == which]
    ch = [tks[i::procs * 4] for i in range(procs * 4)]
    with mp.get_context("fork").Pool(procs) as pool:
        res = pool.map(_work, [(which, c, placebo) for c in ch if c], chunksize=1)
    rows = [r for a, _ in res for r in a]
    pl = [r for _, b in res for r in b]
    return pd.DataFrame(rows), pd.DataFrame(pl, columns=["ticker", "d", "pnl", "pool_both", "contracts"])


def cl_t(x, g):
    x = np.asarray(x, float)
    n = len(x)
    if n < 2:
        return float("nan"), float("nan"), float("nan"), 0
    mu = x.mean()
    u = pd.Series(x - mu).groupby(np.asarray(g)).sum()
    G = len(u)
    if G < 2:
        return mu, float("nan"), float("nan"), G
    se = math.sqrt(float((u ** 2).sum()) * G / (G - 1)) / n
    return mu, se, (mu / se if se > 0 else float("nan")), G


def summarize(W, mks):
    W = W.copy()
    W["fam"] = W.ticker.map(lambda t: mks[t].fam)
    W["series"] = W.ticker.map(lambda t: mks[t].series)
    W["cluster"] = W.ticker.map(lambda t: mks[t].cl)
    W["pool"] = W.ticker.map(lambda t: mks[t].pool)
    W["be_w"] = np.maximum(0, -W.pnl) / W.pool_both.where(W.pool_both > 0)
    return W


def table(W, label):
    rows = []
    for (fam, v), g in W.groupby(["fam", "variant"]):
        mu, se, t, G = cl_t(g.pnl, g.cluster)
        tot, pool = g.pnl.sum(), g.pool_both.sum()
        rows.append(dict(split=label, fam=fam, variant=v, windows=len(g), markets=g.ticker.nunique(), win_with_fill=int((g.events > 0).sum()),
                         fill_events=int(g.events.sum()), contracts=round(g.contracts.sum(), 1), pnl_settle=round(tot, 2),
                         pnl_per_win=round(mu, 4), t_cluster=round(t, 2), clusters=G, pnl_mark60=round(g.pnl_mark.sum(), 2),
                         pnl_fee_sens=round(g.pnl_fee.sum(), 2), thru_c=round(100 * g.thru.sum() / max(g.contracts.sum(), 1e-9), 2),
                         pnl_per_contract_c=round(100 * tot / max(g.contracts.sum(), 1e-9), 2), pct_win_pos=round(100 * float((g.pnl > 0).mean()), 1), pool_both=round(pool, 2), pool_any=round(g.pool_any.sum(), 2),
                         be_pooled=(max(0.0, -tot) / pool if pool > 0 else float("nan")),
                         be_pooled_grossloss=(float(np.maximum(0, -g.pnl).sum()) / pool if pool > 0 else float("nan")),
                         be_pooled_anyside=(max(0.0, -tot) / g.pool_any.sum() if g.pool_any.sum() > 0 else float("nan")),
                         be_win_median=float(g.be_w.median()), be_win_mean=float(g.be_w.mean())))
    return pd.DataFrame(rows)


# ------------------------------------------------------------------------------------------ independent reference simulator
def ref_sim(pr, js, td, cd, k, log=None):
    """Slow, loop-based re-implementation used only to validate the vectorised engine and for the hand spot-check.
    pr: program row; td/cd: pandas frames of the market's trades / candles; k: ticks back (0 or 1)."""
    s0, s1 = float(pr.s0), float(pr.s1)
    close = iso(js["close_time"])
    end = min(s1, close)
    sv = float(js["settlement_value_dollars"])
    rngs = sorted(js["price_ranges"], key=lambda r: float(r["start"]))

    def down(p):
        st = [float(r["step"]) for r in rngs if float(r["start"]) <= p - 1e-9][-1]
        return round(p - st, 4)

    cs = [(int(r.end_ts), r.bid_c, r.ask_c) for r in cd.itertuples()]
    prints = [(float(r.ts), r.yes_price, r.no_price, r.cnt, r.taker_side, r.Index) for r in td.itertuples()]
    cum = [0.0, 0.0]
    pnl = contracts = 0.0
    events = 0
    pool_live = 0.0
    M = int(math.ceil(s0 / 60.0) * 60)
    while M < end:
        st = None
        for e, b, a in cs:
            if e <= M:
                st = (e, b, a)
            else:
                break
        q = [None, None]
        if st:
            _, b, a = st
            bok = b is not None and not math.isnan(b) and 0 < b < 1
            aok = a is not None and not math.isnan(a) and 0 < a < 1
            if bok and aok and b >= a:
                bok = aok = False
            for side, ok, base in ((0, bok, b), (1, aok, round(1 - a, 4) if aok else None)):
                if ok:
                    p = base
                    for _ in range(k):
                        p = down(p)
                    if 0.0005 < p < 0.9995:
                        q[side] = p
        live = [q[x] is not None and cum[x] < CAP - EPS for x in (0, 1)]
        if live[0] and live[1]:
            pool_live += min(60.0, end - M)
        rem = [min(SIZE, CAP - cum[x]) if q[x] is not None else 0.0 for x in (0, 1)]
        for ts_, yp, npx, cnt, ts_side, ix in prints:
            if not (M <= ts_ < min(M + 60, end)):
                continue
            side = 0 if ts_side == "no" else 1
            if q[side] is None or rem[side] <= EPS:
                continue
            px = yp if side == 0 else npx
            if px < q[side] - EPS:
                f = min(rem[side], cnt)
                rem[side] -= f
                cum[side] += f
                pay = (sv - q[side]) if side == 0 else ((1 - sv) - q[side])
                pnl += f * pay
                contracts += f
                events += 1
                if log is not None:
                    log.append(dict(minute_start=M, candle_end_ts=st[0], candle_bid_c=st[1], candle_ask_c=st[2], side="YES bid" if side == 0 else "NO bid",
                                    quote=q[side], print_ts=ts_, print_yes_price=yp, print_no_price=npx, print_count=cnt, print_taker_side=ts_side,
                                    fill_size=f, payoff_per_contract=pay, fill_pnl=f * pay))
        M += 60
    return dict(pnl=pnl, contracts=contracts, events=events, pool_both=pr.period_reward * pool_live / (s1 - s0))


def cmd_validate(a):
    global MKS
    P, pull, M, T, C, dn, dc = load_universe()
    P = prep_windows(P)
    mks, drop = build_all(P, M, T, C, dn, dc)
    rng = np.random.default_rng(1)
    pick = rng.choice(sorted(mks), size=min(a.n, len(mks)), replace=False)
    tg, cg = T.groupby("ticker"), C.groupby("ticker")
    Pi = P.set_index("ticker")
    worst, nfill, nbad = 0.0, 0, 0
    for tk in pick:
        mk = mks[tk]
        pr = Pi.loc[tk]
        pr = pr.copy()
        pr["s0"], pr["s1"] = mk.s0, mk.s1
        for name, kk in VARIANTS.items():
            e = sim(mk, np.full(len(mk.M), kk), np.full(len(mk.M), kk))
            td = tg.get_group(tk) if tk in tg.groups else T.iloc[0:0]
            r = ref_sim(pr, M[tk], td, cg.get_group(tk), kk)
            d = max(abs(e["pnl"] - r["pnl"]), abs(e["contracts"] - r["contracts"]), abs(e["pool_both"] - r["pool_both"]), abs(e["events"] - r["events"]))
            worst = max(worst, d)
            nfill += e["events"]
            if d > 1e-6 and nbad < 5:
                nbad += 1
                print("MISMATCH", tk, name, e["pnl"], r["pnl"], e["contracts"], r["contracts"], e["pool_both"], r["pool_both"], e["events"], r["events"])
    print(f"validated {len(pick)} windows x 2 variants vs independent loop simulator: max abs diff {worst:.2e}, fill events compared {nfill}")


# ------------------------------------------------------------------------------------------------------- report
def md(df, cols=None, fmt=None):
    cols = cols or list(df.columns)
    fmt = fmt or {}
    out = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for _, r in df.iterrows():
        cells = []
        for c in cols:
            v = r[c]
            if c in fmt:
                v = fmt[c](v)
            elif isinstance(v, float):
                v = "nan" if math.isnan(v) else f"{v:,.4g}" if abs(v) < 1 else f"{v:,.2f}"
            cells.append(str(v))
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out)


def spot_check(mks, Wh, P, M, T, C):
    """Hand-checkable fill: first HOLDOUT family-C touch window (alphabetical) with 2..6 fill events."""
    cand = Wh[(Wh.fam == "C") & (Wh.variant == "touch") & (Wh.events >= 2) & (Wh.events <= 6)].sort_values("ticker")
    if cand.empty:
        return "no suitable window"
    tk = cand.iloc[0].ticker
    pr = P.set_index("ticker").loc[tk]
    td, cd = T[T.ticker == tk], C[C.ticker == tk]
    log = []
    ref = ref_sim(pr, M[tk], td, cd, 0, log)
    eng = Wh[(Wh.ticker == tk) & (Wh.variant == "touch")].iloc[0]
    js = M[tk]
    L = [f"Window: {tk}  program {pr.start_date} -> {pr.end_date}  pool ${pr.period_reward:.2f}  market close {js['close_time']}  "
         f"result={js.get('result')} settlement_value_dollars={js.get('settlement_value_dollars')}  price_level_structure={js.get('price_level_structure')}",
         f"Reproduce: sqlite3 backfill/data_local/kalshi_lip/lip.sqlite \"select * from trades where ticker='{tk}' order by ts\" ; "
         f"\"select * from candles where ticker='{tk}' order by end_ts\"", ""]
    for f in log[:3]:
        t = datetime.fromtimestamp(f["print_ts"], timezone.utc).strftime("%H:%M:%S.%f")[:-3]
        m0 = datetime.fromtimestamp(f["minute_start"], timezone.utc).strftime("%H:%M:%S")
        ce = datetime.fromtimestamp(f["candle_end_ts"], timezone.utc).strftime("%H:%M:%S")
        L.append(f"- Minute starting {m0}Z: the candle that ended {ce}Z has yes_bid close {f['candle_bid_c']}, yes_ask close {f['candle_ask_c']}. "
                 f"Touch {f['side']} quote = " + (f"{f['candle_bid_c']}" if f["side"] == "YES bid" else f"1 - {f['candle_ask_c']} = {f['quote']}") +
                 f". Print at {t}Z: taker_side={f['print_taker_side']}, yes_price={f['print_yes_price']}, no_price={f['print_no_price']}, count={f['print_count']}. "
                 + (f"Taker sold YES; strictly through since {f['print_yes_price']} < {f['quote']}" if f["side"] == "YES bid" else
                    f"Taker bought YES; strictly through since no_price {f['print_no_price']} < {f['quote']}") +
                 f" -> fill = min(remaining, print) = {f['fill_size']:g} at {f['quote']}. Payoff per contract at settlement = "
                 + (f"{js['settlement_value_dollars']} - {f['quote']}" if f["side"] == "YES bid" else f"(1 - {js['settlement_value_dollars']}) - {f['quote']}")
                 + f" = {f['payoff_per_contract']:+.4f}; fill P&L {f['fill_pnl']:+.4f}.")
    L += ["", f"All {len(log)} fills by the independent loop simulator: contracts {ref['contracts']:g}, P&L {ref['pnl']:+.4f}, pool accrued (both sides live) ${ref['pool_both']:.4f}.",
          f"Vectorised engine for the same window: contracts {eng.contracts:g}, P&L {eng.pnl:+.4f}, pool accrued ${eng.pool_both:.4f}  (difference {abs(ref['pnl'] - eng.pnl):.1e})."]
    return "\n".join(L)


def write_report(P, pull, mks, drop, Wd, Wh, PL, Td, Th, M, T, C):
    cond = lambda x: x
    L = []
    A = L.append
    cov = P.copy()
    cov["status"] = cov.ticker.map(lambda t: "simulated" if t in mks else "dropped: " + drop.get(t, "?"))
    cc = cov.groupby(["fam", "split", "status"]).size().rename("windows").reset_index()
    nfill = pd.concat([Td, Th])
    A("# Kalshi LIP paper-LP backtest (frozen plan results/PLAN_KALSHI_LIP.md)\n")
    A(f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}Z by `backfill/kalshi_lip_bt.py` (`dl` then `run --holdout`). Program/market/trade/candle pull completed "
      f"{datetime.fromtimestamp(pull, timezone.utc).strftime('%Y-%m-%d %H:%M')}Z (programs snapshot). Public endpoints only, no keys, no orders.\n")
    A("## Verdict (gate (3) pending)\n")
    A("GATE_PLACEHOLDER\n")
    A("## 1. Setup as run (deviations from nothing; open points are labelled DECISION)\n")
    A(f"- Families: N = 7 NFL ladder series ({', '.join(FAM_N)}); C = 12 fifteen-minute commodity/FX series ({', '.join(FAM_C)}), program windows starting in the last 30 days of the pull. KXBTC15M/KXETH15M/KXCRYPTOLEAD15M not used.")
    A(f"- Split: DEV = windows ending <= {SPLIT}; HOLDOUT = the rest. Holdout computed once (`HOLDOUT_LOOKED` lock file). N has no DEV windows (NFL LIP started 23 Sep), so **N is descriptive only**.")
    A(f"- Quote: one passive bid per side (YES bid, NO bid) per minute while the program is active and before close; size {SIZE}; touch = previous minute's candle yes_bid close (YES) / 1 - yes_ask close (NO); back1 = one tick lower (tick from the market's `price_ranges`). Re-priced every minute (back of queue each minute).")
    A(f"- Fills: only taker prints strictly through our price (YES bid: taker_side=no with yes_price < quote; NO bid: taker_side=yes with no_price < quote); equal price never fills; fill = min(remaining quote, print count), at our price; remaining quote per minute = min({SIZE}, {CAP} - cumulative filled on that side); cap {CAP_MULT} x size per side per market. DECISION: a partly filled quote keeps resting for the rest of that minute and is re-quoted at full size next minute.")
    A("- DECISION: a side is skipped in a minute if the previous candle has no valid bid (YES) / ask (NO) (bid<=0, ask>=1, missing) or the book is crossed; missing candles are forward-filled from the last candle (a minute with no change/trades has no candle).")
    A("- Fees: series `fee_type` = `quadratic` (taker-only) for all 19 series -> maker fee = 0 in the headline numbers (see section 8). Sensitivity column charges the general maker formula 0.0175 x C x P x (1-P), rounded up to the cent per minute-side order.")
    A("- P&L: PRIMARY = hold to settlement (`settlement_value_dollars`; YES payoff sv - p, NO payoff (1-sv) - q). SECONDARY = mark at candle mid 60 min after each fill (last valid candle mid; settlement value if the market closes first). For 15-minute markets the 60-min mark is always past close, so SECONDARY == PRIMARY for family C by construction.")
    A("- Pool accrual = program pool x (minutes where BOTH our quotes were live and under the cap) / program minutes. DECISION: both-sides-live is the primary denominator (matches the LIP's two-sided-liquidity requirement; conservative); an either-side variant is reported. Break-even share = max(0, -fill P&L) / pool accrued; pooled uses summed P&L and summed pool.")
    A("- NFL kickoff = `occurrence_datetime` - 3 h (an inference), also -30 / +30 min. Fills are split by fill time; pool accrual by quote minute.")
    A("- Clustering: week of window start (N), UTC day of window start (C). t = mean window P&L / cluster-robust SE (CR1). Placebo: per minute and side a random offset of 0-3 ticks, 100 draws per holdout window set, fixed seed.\n")
    A("## 2. Counts\n")
    A(md(cc))
    A("")
    A("Fills and windows per family / split / variant (simulated windows only):\n")
    A(md(nfill, ["split", "fam", "variant", "windows", "markets", "win_with_fill", "fill_events", "contracts"]))
    A("\n## 3. Results by split\n")
    cols = ["split", "fam", "variant", "windows", "pnl_settle", "pnl_per_win", "t_cluster", "clusters", "pnl_mark60", "pnl_fee_sens", "pnl_per_contract_c", "thru_c", "pct_win_pos", "pool_both", "be_pooled", "be_pooled_grossloss", "be_pooled_anyside", "be_win_median"]
    A(md(nfill, cols))
    A("\n(`be_pooled` = max(0, -sum P&L) / sum pool accrued; 0 means the fills were profitable on net, so no reward is needed. `be_pooled_grossloss` sums only the losing windows. `be_win_median` is the median over windows of the per-window break-even share, NaN windows (no accrual) excluded.)\n")
    A("## 4. NFL pre-kickoff vs in-game (HOLDOUT, family N)\n")
    Wn = Wh[Wh.fam == "N"]
    rows = []
    for v, g in Wn.groupby("variant"):
        for tag, lab in (("m30", "kickoff-30m"), ("k0", "kickoff=occ-3h"), ("p30", "kickoff+30m")):
            pre, inn = g[f"pnl_pre_{tag}"].sum(), g[f"pnl_in_{tag}"].sum()
            pp, pi = g[f"pool_pre_{tag}"].sum(), g[f"pool_in_{tag}"].sum()
            rows.append(dict(variant=v, kickoff=lab, contracts_pre=g[f"ctr_pre_{tag}"].sum(), contracts_in=g.contracts.sum() - g[f"ctr_pre_{tag}"].sum(),
                             pnl_pre=pre, pnl_in=inn, pool_pre=pp, pool_in=pi,
                             be_pre=max(0, -pre) / pp if pp > 0 else float("nan"), be_in=max(0, -inn) / pi if pi > 0 else float("nan")))
    A(md(pd.DataFrame(rows)))
    A("\n## 5. Placebo (HOLDOUT, random 0-3 tick offsets, 100 draws)\n")
    PL["fam"] = PL.ticker.map(lambda t: mks[t].fam)
    pr_ = PL.groupby(["fam", "d"]).agg(pnl=("pnl", "sum"), pool=("pool_both", "sum"), ctr=("contracts", "sum")).reset_index()
    prow = []
    for fam, g in pr_.groupby("fam"):
        for v in VARIANTS:
            o = Th[(Th.fam == fam) & (Th.variant == v)].iloc[0]
            prow.append(dict(fam=fam, option=v, option_pnl=o.pnl_settle, placebo_mean=g.pnl.mean(), placebo_p5=g.pnl.quantile(.05), placebo_p95=g.pnl.quantile(.95),
                             frac_placebo_ge_option=float((g.pnl >= o.pnl_settle).mean()), option_be=o.be_pooled,
                             placebo_median_be=float((np.maximum(0, -g.pnl) / g.pool).median()), placebo_contracts=g.ctr.mean(), option_contracts=o.contracts))
    PLT = pd.DataFrame(prow)
    A(md(PLT))
    A("\n## 6. Gate (HOLDOUT)\n")
    grows = []
    for _, o in Th.iterrows():
        pp = PLT[(PLT.fam == o.fam) & (PLT.option == o.variant)].iloc[0]
        g1 = "descriptive (no DEV)" if o.fam == "N" else ("PASS" if o.be_pooled < 0.05 else "FAIL")
        g2 = "descriptive (no DEV)" if o.fam == "N" else ("n/a" if math.isnan(o.t_cluster) else ("PASS" if o.t_cluster > -2 else "FAIL"))
        pl = "descriptive (no DEV)" if o.fam == "N" else ("PASS" if pp.frac_placebo_ge_option < 0.05 else "FAIL")
        grows.append(dict(fam=o.fam, variant=o.variant, g1_be_lt_0p05=g1, be_pooled=o.be_pooled, g2_t_gt_m2=g2, t=o.t_cluster, clusters=o.clusters,
                          placebo_not_as_good=pl, frac_placebo_ge_option=pp.frac_placebo_ge_option, g3_forward_share="PENDING"))
    GT = pd.DataFrame(grows)
    A(md(GT))
    A("\nGate (1): pooled holdout break-even share < 0.05. Gate (2): clustered t of per-window fill P&L > -2. Placebo reading: PASS if fewer than 5% of random-offset placebo draws have pooled P&L >= the option's (literal reading of 'must not do as well'). Gate (3) needs the forward recorder (live/kxlipbook.py): median measured share of our 100 lots >= 2x the break-even share.\n")
    A("## 7. Spot-check of one fill by hand\n")
    A("```\n" + spot_check(mks, Wh, P, M, T, C) + "\n```\n")
    A("## 8. Maker fee schedule verification\n")
    A("FEE_PLACEHOLDER\n")
    A("## 9. Data coverage and caveats\n")
    A("CAVEAT_PLACEHOLDER\n")
    txt = "\n".join(L)
    open(os.path.join(RESULTS, "KALSHI_LIP_BT.md"), "w").write(txt)
    GT.to_csv(os.path.join(DATA, "gate_table.csv"), index=False)
    PLT.to_csv(os.path.join(DATA, "placebo_table.csv"), index=False)
    print(GT.to_string())
    print(PLT.to_string())
    print("report written (placeholders VERDICT/FEE/CAVEAT to fill in)")


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    d = sp.add_parser("dl")
    d.add_argument("--refresh-programs", action="store_true")
    d.set_defaults(fn=cmd_dl)
    sp.add_parser("dlc").set_defaults(fn=cmd_dlc)
    v = sp.add_parser("validate")
    v.add_argument("-n", type=int, default=300)
    v.set_defaults(fn=cmd_validate)
    r = sp.add_parser("run")
    r.add_argument("--holdout", action="store_true")
    r.add_argument("--again", action="store_true", help="allow a second look at the holdout (breaks the single-look rule; logged)")
    r.set_defaults(fn=cmd_run)
    a = ap.parse_args()
    a.fn(a)


def cmd_run(a):
    global MKS
    P, pull, M, T, C, dn, dc = load_universe()
    P = prep_windows(P)
    mks, drop = build_all(P, M, T, C, dn, dc)
    MKS = mks
    print(f"windows in scope {len(P)}, simulated {len(mks)}, dropped {pd.Series(drop).value_counts().to_dict()}", flush=True)
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 40)
    Wd, _ = run_split(mks, "DEV", False)
    Wd = summarize(Wd, mks)
    Td = table(Wd, "DEV")
    Wd.to_csv(os.path.join(DATA, "windows_dev.csv"), index=False)
    print(Td.to_string())
    if not a.holdout:
        return
    lock = os.path.join(DATA, "HOLDOUT_LOOKED")
    if os.path.exists(lock) and not a.again:
        sys.exit("holdout already looked at (single-look rule): " + open(lock).read())
    with open(lock, "a") as fh:
        fh.write(f"holdout run at {datetime.now(timezone.utc).isoformat()}{' (AGAIN)' if a.again else ''}\n")
    Wh, PL = run_split(mks, "HOLDOUT", True)
    Wh = summarize(Wh, mks)
    Wh.to_csv(os.path.join(DATA, "windows_holdout.csv"), index=False)
    PL.to_csv(os.path.join(DATA, "placebo_holdout.csv"), index=False)
    Th = table(Wh, "HOLDOUT")
    print(Th.to_string())
    write_report(P, pull, mks, drop, Wd, Wh, PL, Td, Th, M, T, C)


if __name__ == "__main__":
    main()
