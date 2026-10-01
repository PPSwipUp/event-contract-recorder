"""Big database of Kalshi hourly crypto price markets since 2024, from archived trades, and a large-scale test.

collect:  for every hourly event of SERIES in [start, end): its markets near the money (within NEAR of the price at
          the open, nearest MAXM), each with strikes + Kalshi's result, and every real trade 10-20 min after the open.
evaluate: per series - (1) is the model's probability more accurate than the price people actually traded at?
          (2) the frozen rules and the walk-forward bot, by year, and excluding Aug-Sep 2026 (used to pick rules).

  python backfill/db.py collect --series KXBTCD --product BTC-USD --start 2024-03-01 --end 2024-06-01 --out chunk
  python backfill/db.py evaluate --series KXBTCD --product BTC-USD --chunks chunks --out results/DB_KXBTCD.md
"""
from __future__ import annotations

import argparse
import glob
import itertools
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

import research
from backtest import fee_c, hourly, sigmas
from collect import coinbase, event_ticker, markets_of
from tradebt import WINDOW, _trades, brackets

NEAR, MAXM = 0.03, 10


def collect(a):
    start = datetime.fromisoformat(a.start).replace(tzinfo=timezone.utc)
    end = min(datetime.fromisoformat(a.end).replace(tzinfo=timezone.utc), datetime.now(timezone.utc) - timedelta(hours=2))
    spot = coinbase(a.product, start - timedelta(hours=3), end + timedelta(hours=2))
    px = pd.Series(spot.c.values, index=pd.to_datetime(spot.ts, unit="s", utc=True)).sort_index()

    def one(close):
        try:
            return _one(close)
        except Exception as err:                         # one stubborn event must not lose the whole chunk
            print(f"skipped {close:%Y-%m-%d %H}: {err}", flush=True)
            return []

    def _one(close):
        ev = event_ticker(a.series, close)
        ms = markets_of(a.series, ev)
        if not ms:
            return []
        op = pd.Timestamp(ms[0].get("open_time") or (close - timedelta(hours=1)).isoformat())
        s = px.asof(op)
        if not np.isfinite(s):
            return []
        cand = []
        for m in ms:
            lo, hi = m.get("floor_strike"), m.get("cap_strike")
            ref = hi if lo is None else lo if hi is None else (lo + hi) / 2
            if ref is not None and abs(ref / s - 1) <= NEAR:
                cand.append((abs(ref / s - 1), m))
        rows = []
        for _, m in sorted(cand, key=lambda x: x[0])[:MAXM]:
            for t in _trades(m["ticker"], int(op.timestamp()) + WINDOW[0], int(op.timestamp()) + WINDOW[1]):
                rows.append({"event": ev, "close": close.isoformat(), "open": op.isoformat(), "ticker": m["ticker"],
                             "floor": m.get("floor_strike"), "cap": m.get("cap_strike"), "result": m.get("result"),
                             "ts": t["created_time"], "taker": t.get("taker_side"),
                             "yes": float(t.get("yes_price_dollars") or np.nan), "no": float(t.get("no_price_dollars") or np.nan),
                             "count": float(t.get("count_fp") or t.get("count") or 0)})
        return rows

    hours = pd.date_range(start + timedelta(hours=1), end, freq="1h", tz="UTC").to_pydatetime()
    with ThreadPoolExecutor(6) as ex:
        rows = [r for rs in ex.map(one, hours) for r in rs]
    os.makedirs(a.out, exist_ok=True)
    pd.DataFrame(rows).to_parquet(os.path.join(a.out, "trades.parquet"))
    print(f"{a.series} {a.start}: {len(rows)} trades in {len({r['event'] for r in rows})} events", flush=True)


def evaluate(a):
    T = pd.concat([pd.read_parquet(f) for f in sorted(glob.glob(os.path.join(a.chunks, "*", "trades.parquet")))],
                  ignore_index=True)
    first = pd.to_datetime(T.close, utc=True).min()
    spot = coinbase(a.product, (first - pd.Timedelta(days=200)).to_pydatetime(), datetime.now(timezone.utc))
    W, minute = hourly(spot)
    S = sigmas(W)
    B = brackets(T, minute)
    B["sig_raw"] = S.ppc.reindex(B.win).values
    B = B[np.isfinite(B.sig_raw)].copy()
    B["day"] = B.close.dt.strftime("%Y-%m-%d")
    B["year"] = B.close.dt.year
    tr = (W.index < first) & S.ppc.notna()
    k_fixed = float(np.median(np.abs(W.ret[tr]) / S.ppc[tr]))
    z = np.sort((W.ret[tr] / (k_fixed * S.ppc[tr])).values)
    k_roll = (np.abs(W.ret) / S.ppc).shift(1).rolling(24 * 30, min_periods=24 * 7).median().reindex(B.win).values
    k_roll = np.where(np.isfinite(k_roll), k_roll, k_fixed)
    L = [f"# {a.series}: model vs Kalshi's traded prices, {B.close.min():%Y-%m} to {B.close.max():%Y-%m}", "",
         f"{B.event.nunique()} hourly events, {len(B)} markets near the money that traded 10-20 min after the open.", ""]

    # (1) accuracy: model probability vs the price of the first trade in the window, on the same markets
    X = B.assign(s0=B.s0_yes.fillna(B.s0_no), left=B.left_yes.fillna(B.left_no))
    p = np.clip(research.probs(X, z, k_roll), 1e-3, 1 - 1e-3)
    first_px = np.where(np.isfinite(B.ask), B.ask, 1 - B.no_ask)            # yes-equivalent price of a real trade
    q = np.clip(first_px, 1e-3, 1 - 1e-3)
    ok = np.isfinite(p) & np.isfinite(q)
    y = B.y.values
    ll = lambda pr: -(y * np.log(pr) + (1 - y) * np.log(1 - pr))
    A = pd.DataFrame({"year": B.year.values, "model": ll(p), "market": ll(q), "mb": (p - y) ** 2, "kb": (q - y) ** 2})[ok]
    acc = A.groupby("year").agg(markets=("model", "size"), model_logloss=("model", "mean"), market_logloss=("market", "mean"),
                                model_brier=("mb", "mean"), market_brier=("kb", "mean"))
    acc["more_accurate"] = np.where(acc.model_logloss < acc.market_logloss, "model", "market")
    blend = np.clip(0.5 * p + 0.5 * q, 1e-3, 1 - 1e-3)
    L += ["## 1. Who gives better probabilities: the model or the traded price? (lower is better)", "",
          acc.round(4).to_markdown(), "",
          f"Averaging the two (half model, half market): log loss {ll(blend)[ok].mean():.4f} vs market {A.market.mean():.4f} "
          "- if lower, the model adds information the market lacks.", ""]

    # (2) rules: frozen ones + walk-forward self-tuning over 18 configs
    def run(k, filt, margin):
        py = research.probs(B.assign(s0=B.s0_yes, left=B.left_yes), z, k)
        pn = research.probs(B.assign(s0=B.s0_no, left=B.left_no), z, k)
        ay = an = np.ones(len(B), bool)
        if filt == "shrink50":
            py, pn = B.mkt.values + 0.5 * (py - B.mkt.values), B.mkt.values + 0.5 * (pn - B.mkt.values)
        if filt == "volview":
            err = np.stack([np.where(ok, (research.probs(X, z, k, m) - B.mkt.values) ** 2, 0) for m in research.MULTS], 1)
            best = pd.DataFrame(err, index=B.index).groupby(B.event).sum().idxmin(axis=1).map(lambda j: research.MULTS[j])
            mm = B.event.map(best).values
            centre = np.where(B.floor.isna(), B.cap, np.where(B.cap.isna(), B.floor, (B.floor + B.cap) / 2))
            outer = np.abs(np.log(centre) - X.s0.values) / (k * B.sig_raw.values * X.left.values) > 1.0
            more, less = mm < 1 / 1.2, mm > 1.2
            ay, an = (more & outer) | (less & ~outer), (more & ~outer) | (less & outer)
        ask, nask = B.ask.values, B.no_ask.values
        by = np.isfinite(ask) & np.isfinite(py) & ay & (100 * (py - ask) - fee_c(ask, 100) > margin)
        bn = np.isfinite(nask) & np.isfinite(pn) & an & (100 * ((1 - pn) - nask) - fee_c(nask, 100) > margin)
        return pd.DataFrame({"day": np.r_[B.day.values[by], B.day.values[bn]],
                             "pnl_c": np.r_[(100 * y - 100 * ask - fee_c(ask, 100))[by],
                                            (100 * (1 - y) - 100 * nask - fee_c(nask, 100))[bn]],
                             "size": np.r_[B.n_yes.values[by], B.n_no.values[bn]]})

    configs = {(s, f, m): run(np.full(len(B), k_fixed) if s == "fixed" else k_roll, f, m)
               for s, f, m in itertools.product(("fixed", "rolling"), ("none", "volview", "shrink50"), (2, 5, 10))}
    days = sorted(B.day.unique())
    daily = pd.DataFrame({c: D.groupby("day").pnl_c.sum() for c, D in configs.items()}).reindex(days).fillna(0)
    wf = []
    for i, d in enumerate(days[30:], 30):
        c = daily.iloc[i - 30:i].sum().idxmax()
        D = configs[c]
        wf.append(D[D.day == d])
    rules = {"forward (rolling, volview, 5c)": configs[("rolling", "volview", 5)],
             "sweep (fixed, shrink50, 2c)": configs[("fixed", "shrink50", 2)],
             "base (fixed, none, 5c)": configs[("fixed", "none", 5)],
             "walk-forward self-tuning": pd.concat(wf, ignore_index=True) if wf else pd.DataFrame(columns=["day", "pnl_c"])}

    def summ(D):
        d = D.groupby("day").pnl_c.sum()
        t = d.mean() / (d.std(ddof=1) / np.sqrt(len(d))) if len(d) > 2 and d.std() > 0 else np.nan
        cap = np.minimum(D["size"].fillna(0), 100) if "size" in D else 0
        return {"bets": len(D), "c_per_bet": D.pnl_c.mean() if len(D) else np.nan, "dollars_100": D.pnl_c.sum(),
                "dollars_at_traded_size": float((D.pnl_c * cap).sum() / 100), "day_t": t}
    rows = []
    for name, D in rules.items():
        clean = D[~D.day.between("2026-08-01", "2026-09-30")]
        rows.append({"rule": name, **summ(D), **{f"excl_AugSep26_{k}": v for k, v in summ(clean).items()}})
    by_year = pd.DataFrame({name: D.assign(y=D.day.str[:4]).groupby("y").pnl_c.sum()  # cents per contract x 100 contracts = dollars
                            for name, D in rules.items()})
    L += ["## 2. Betting rules (real traded prices, Kalshi fees, 100 contracts per bet)", "",
          pd.DataFrame(rows).round(2).to_markdown(index=False), "",
          "Dollars by year (100 contracts per bet):", "", by_year.round(0).to_markdown(), ""]
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    open(a.out, "w").write("\n".join(L))
    print("\n".join(L))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["collect", "evaluate"])
    ap.add_argument("--series", required=True)
    ap.add_argument("--product", required=True)
    ap.add_argument("--start")
    ap.add_argument("--end")
    ap.add_argument("--out", default="chunk")
    ap.add_argument("--chunks", default="chunks")
    a = ap.parse_args()
    collect(a) if a.cmd == "collect" else evaluate(a)


if __name__ == "__main__":
    main()
