"""Polymarket "Elon Musk # tweets <window>" bracket markets vs a running-count nowcast, on real taker trades.

Settlement = Polymarket's own tracker (xtracker.polymarket.com) post count in the window; its API returns every post
with createdAt and importedAt (when the tracker saw it), from 2025-10-31.  So at any moment we know the official
running count.
CHECK first: the tracker count for each closed window must land in Polymarket's winning bracket.
Model at decision time t (only posts IMPORTED before t count as known):
  remaining posts N ~ negative binomial, mean = (posts in the previous 7 days / 168) x hours left,
  dispersion k fitted once on daily counts of the train period only (frozen for the holdout).
  P(bracket) = P(count_so_far + N in bracket).
Entries: first real taker trade per market/side per 6-hour block inside the window; size = later same-side taker
volume at that price or better in the block (max 100 shares); Polymarket fee from the market's schedule
(default 0.05*p*(1-p)).  Margin picked on 2025-11..2026-03, run once on 2026-04..10.
Placebo: the same model fed a count that is 24 h stale.
  python backfill/tweets.py
"""
from __future__ import annotations

import json
import math
import os
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests

import dohfix  # noqa: F401
from pmtouchdata import jget, trades

D = "data_local/tweets"
ET = ZoneInfo("America/New_York")
TRAIN, HOLD = ("2025-11-01", "2026-04-01"), ("2026-04-01", "2026-10-04")
CAP = 100


def posts():
    p = f"{D}/posts.parquet"
    if not os.path.exists(p):
        d = requests.get("https://xtracker.polymarket.com/api/users/elonmusk/posts", timeout=120).json()["data"]
        P = pd.DataFrame(d)[["platformId", "createdAt", "importedAt"]]
        P["created"] = pd.to_datetime(P.createdAt, utc=True)
        P["imported"] = pd.to_datetime(P.importedAt, utc=True)
        P.drop_duplicates("platformId")[["platformId", "created", "imported"]].to_parquet(p)
    return pd.read_parquet(p).sort_values("created")


def window(desc, end):
    m = re.search(r"from ([A-Z][a-z]+ \d{1,2}),? ?(\d{4})?,? (\d{1,2}:\d{2} [AP]M) ET to ([A-Z][a-z]+ \d{1,2}),? (\d{4}),? (\d{1,2}:\d{2} [AP]M) ET", desc)
    if not m:
        return None
    y = m.group(2) or m.group(5)
    s = datetime.strptime(f"{m.group(1)} {y} {m.group(3)}", "%B %d %Y %I:%M %p").replace(tzinfo=ET)
    e = datetime.strptime(f"{m.group(4)} {m.group(5)} {m.group(6)}", "%B %d %Y %I:%M %p").replace(tzinfo=ET)
    if s > e:                                                          # window crossing a year end
        s = s.replace(year=s.year - 1)
    return pd.Timestamp(s).tz_convert("UTC"), pd.Timestamp(e).tz_convert("UTC")


def bracket(q):
    """(lo, hi) inclusive post-count range from a market question; None if unparseable"""
    q = q.replace(",", "")
    ql = q.lower()
    m = re.search(r"(\d+)\s*-\s*(\d+)\s*(?:tweets|posts|times)", ql)
    if m:
        return (int(m.group(1)), int(m.group(2)))
    m = re.search(r"(\d+)\+\s*(?:tweets|posts|times)?", ql) or re.search(r"(\d+) or more", ql)
    if m:
        return (int(m.group(1)), None)
    m = re.search(r"more than (\d+)", ql)
    if m:
        return (int(m.group(1)) + 1, None)
    m = re.search(r"(?:less|fewer) than (\d+)", ql)
    if m:
        return (None, int(m.group(1)) - 1)
    m = re.search(r"between (\d+)\s*-\s*(\d+)", ql)
    if m:
        return (int(m.group(1)), int(m.group(2)))
    return None


def markets():
    p = f"{D}/markets.parquet"
    if os.path.exists(p):
        return pd.read_parquet(p)
    rows, off = [], 0
    while True:
        evs = jget("https://gamma-api.polymarket.com/events", series_slug="elon-tweets", closed="true", limit=100, offset=off)
        if not isinstance(evs, list) or not evs:
            break
        off += 100
        for e in evs:
            if e["endDate"] < "2025-11-08":
                continue
            for m in e["markets"]:
                w = window(m.get("description") or e.get("description") or "", e["endDate"])
                b = bracket(m["question"])
                res = json.loads(m.get("outcomePrices") or "[]")
                if not w or not b or not res:
                    continue
                fs = m.get("feeSchedule") or {}
                rows.append({"event": e["slug"], "cid": m["conditionId"], "question": m["question"], "lo": b[0], "hi": b[1],
                             "start": w[0], "end": w[1], "result": "yes" if float(res[0]) > 0.5 else "no",
                             "rate": float(fs.get("rate") or 0.05) if m.get("feesEnabled", True) else 0.0,
                             "volume": float(m.get("volume") or 0)})
    M = pd.DataFrame(rows)
    M.to_parquet(p)
    return M


def nb_k(daily):
    m, v = daily.mean(), daily.var()
    return m * m / (v - m) if v > m else 1e6


def nb_cdf(x, mean, k):
    """P(N <= x) for negative binomial with mean, size k (vectorised over x >= -1)"""
    p = k / (k + mean)
    xs = np.arange(0, int(max(x.max(), 0)) + 1)
    logpmf = (np.vectorize(math.lgamma)(xs + k) - math.lgamma(k) - np.vectorize(math.lgamma)(xs + 1)
              + k * math.log(p) + xs * math.log1p(-p))
    c = np.concatenate([[0.0], np.cumsum(np.exp(logpmf))])
    return c[np.clip(x + 1, 0, len(c) - 1).astype(int)]


def main():
    os.makedirs(D, exist_ok=True)
    P = posts()
    M = markets()
    # CHECK: tracker count in each window vs the winning bracket
    win = M[M.result == "yes"].copy()
    win["count"] = [((P.created >= s) & (P.created < e)).sum() for s, e in zip(win.start, win.end)]
    win["ok"] = [(lo is None or pd.isna(lo) or c >= lo) and (hi is None or pd.isna(hi) or c <= hi) for c, lo, hi in zip(win["count"], win.lo, win.hi)]
    win = win[win.start >= P.created.min()]
    check = f"tracker count lands in the winning bracket for {win.ok.sum()} of {len(win)} closed windows"
    print(check, flush=True)
    tp = f"{D}/trades.parquet"
    if not os.path.exists(tp):
        with ThreadPoolExecutor(6) as ex:
            res = list(ex.map(trades, M[(M.volume > 0) & (M.start >= P.created.min())].cid))
        pd.DataFrame([t for r in res for t in r]).to_parquet(tp)
    T = pd.read_parquet(tp).merge(M, on="cid")
    T["t"] = pd.to_datetime(T.ts, unit="s", utc=True)
    T = T[(T.t >= T.start) & (T.t < T.end - pd.Timedelta(minutes=10))]
    buy_yes = ((T.side == "BUY") & (T.outcome == "Yes")) | ((T.side == "SELL") & (T.outcome == "No"))
    T["taker"] = np.where(buy_yes, "yes", "no")
    T["px"] = np.where(T.side == "BUY", T.price, 1 - T.price)
    T["block"] = T.t.dt.floor("6h")
    T = T[(T.px > 0.005) & (T.px < 0.995)].sort_values("t")
    k_ = ["cid", "taker", "block"]
    E = T.groupby(k_).head(1).copy()
    J = E[k_ + ["t", "px"]].merge(T[k_ + ["t", "px", "size"]], on=k_, suffixes=("", "_o"))
    av = J[(J.t_o > J.t) & (J.px_o <= J.px + 1e-9)].groupby(k_)["size"].sum()
    E = E.join(av.rename("avail"), on=k_)
    E["avail"] = E.avail.fillna(0)

    # dispersion from TRAIN-period daily counts only (no posts exist before the train period; a first version used
    # 'before TRAIN' = 1 day of data and silently fell back to Poisson -> overconfident)
    tr = P[(P.created >= pd.Timestamp(TRAIN[0], tz="UTC")) & (P.created < pd.Timestamp(TRAIN[1], tz="UTC"))]
    daily = tr.set_index("created").resample("1D").size()
    K = nb_k(daily.iloc[1:-1])
    assert K < 1e5, "dispersion estimate failed"
    imp = np.sort(P.imported.values.astype("datetime64[ns]").astype("int64"))
    cre = np.sort(P.created.values.astype("datetime64[ns]").astype("int64"))

    def model(stale_h=0):
        out = []
        for r in E.itertuples():
            t = r.t - pd.Timedelta(hours=stale_h)
            known = P[(P.imported <= t) & (P.created >= r.start)]
            so_far = len(known)
            rate = ((P.imported <= t) & (P.created > t - pd.Timedelta(days=7))).sum() / 168
            hours = (r.end - r.t).total_seconds() / 3600 + stale_h
            mean = max(rate * hours, 1e-6)
            lo = -1 if pd.isna(r.lo) else r.lo - so_far - 1                   # need N >= lo - so_far
            hi = 10 ** 6 if pd.isna(r.hi) else r.hi - so_far
            if hi < 0:
                out.append(0.0)
                continue
            c = nb_cdf(np.array([min(hi, 5000), max(lo, -1)]), mean, K)
            out.append(float(c[0] - (c[1] if lo >= 0 else 0.0)))
        return np.array(out)

    def finish(X, p_yes):
        X = X.copy()
        X["p_yes"] = p_yes
        X["p"] = np.where(X.taker == "yes", X.p_yes, 1 - X.p_yes)
        X["won"] = np.where(X.taker == "yes", X.result == "yes", X.result == "no").astype(float)
        X["fee"] = 100 * X.rate * X.px * (1 - X.px)
        X["edge_c"] = 100 * (X.p - X.px) - X.fee
        X["pnl_c"] = 100 * X.won - 100 * X.px - X.fee
        X["day"] = X.t.dt.strftime("%Y-%m-%d")
        return X

    from pmtouch import run
    E1 = finish(E, model())
    E1["half"] = np.where(E1.day < HOLD[0], "train", "holdout")
    L = ["# Polymarket 'Elon Musk # tweets' brackets vs a running-count nowcast", "", f"CHECK: {check}", "",
         f"Entries: {len(E1)}; negative-binomial size k = {K:.2f} (daily counts {TRAIN[0]}..{TRAIN[1]})", "",
         "## Accuracy (Brier)", "", E1.groupby("half").apply(lambda x: pd.Series({
             "n": len(x), "model": ((x.p - x.won) ** 2).mean(), "traded_price": ((x.px - x.won) ** 2).mean()})).round(4).to_markdown(), ""]
    G = pd.DataFrame([{"margin_c": m, **run(E1, m, *TRAIN)} for m in (3, 5, 8, 12, 20)])
    best = G[G.bets >= 50].sort_values("week_t", ascending=False).iloc[0]
    L += ["## Picked on 2025-11..2026-03", "", G.to_markdown(index=False), "", f"Chosen: margin {best.margin_c}c", ""]
    Pl = finish(E, model(stale_h=24))
    rows = [{"bot": "model", **run(E1, best.margin_c, *HOLD)}, {"bot": "model, cap 500", **run(E1, best.margin_c, *HOLD, cap=500)},
            {"bot": "placebo: count 24 h stale", **run(Pl, best.margin_c, *HOLD)}]
    L += ["## Holdout 2026-04..10 (run once)", "", pd.DataFrame(rows).to_markdown(index=False), ""]
    open("../results/TWEETS.md", "w").write("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    main()
