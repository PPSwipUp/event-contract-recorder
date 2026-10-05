"""Reduce the range bot's drawdown, and test whether its edge is real.  BTC + ETH hourly ranges, database chunks.

Pre-declared:
  TRAIN   = 2024-11-01 .. 2025-12-31  (choose risk controls here only)
  HOLDOUT = 2026-01-01 .. 2026-09-30, 28 Sep excluded  (the chosen controls are run once, untouched)
Base signal: fixed vol scale, model vs real traded price, > 5c edge after fees (the database's best rule).
Risk controls (all known at the moment of the bet):
  per_event  max bets per hourly event (1, 2, all)            - bets in one hour share one price move
  size       contracts per bet (25, 50, 100), never above the volume others actually traded at our price
  crowd      skip if the trade that showed us the price was bigger than N contracts (none, 50, 200)
  calm       skip hours whose previous hour moved > X times the model's forecast (none, 2, 1.5)
  stop       stop for the day after losing $D (none, 100, 200)
  margin     edge needed (5, 8, 12 c)
Choice = best TRAIN Calmar (profit / max drawdown) with >= 300 bets.
Reality checks on the chosen bot: opposite-side placebo, stale-price model (5 min old), +1c/+2c slippage,
weekly block-bootstrap 90% interval, quarter-by-quarter.

  python backfill/improve.py --chunks chunks --out results/IMPROVE.md
"""
from __future__ import annotations

import argparse
import glob
import itertools
import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd

import research
from backtest import fee_c, hourly, sigmas
from collect import coinbase
from sim import available
from tradebt import brackets

PAIRS = {"KXBTC": "BTC-USD", "KXETH": "ETH-USD"}
TRAIN, HOLD = ("2024-11-01", "2026-01-01"), ("2026-01-01", "2026-10-01")
EXCLUDE = {"2026-09-28"}


def load(series, product, chunks, stale_min=0):
    T = pd.concat([pd.read_parquet(f) for f in sorted(glob.glob(os.path.join(chunks, f"db-{series}-*", "trades.parquet")))],
                  ignore_index=True)
    first = pd.to_datetime(T.close, utc=True).min()
    spot = coinbase(product, (first - pd.Timedelta(days=200)).to_pydatetime(), datetime.now(timezone.utc))
    W, minute = hourly(spot)
    S = sigmas(W)
    B = brackets(T, minute)
    if stale_min:                                           # placebo: the model sees a price `stale_min` minutes old
        for side, tcol in (("yes", "t_yes"), ("no", "t_no")):
            B[f"s0_{side}"] = minute.reindex(B[tcol].dt.floor("1min") - pd.Timedelta(minutes=1 + stale_min)).values
    B["sig_raw"] = S.ppc.reindex(B.win).values
    B["prev_ratio"] = (W.rv / S.ppc).shift(1).reindex(B.win).values     # last hour's move vs its forecast
    B = B[np.isfinite(B.sig_raw)].copy()
    B["day"] = B.close.dt.strftime("%Y-%m-%d")
    B = B[~B.day.isin(EXCLUDE)].reset_index(drop=True)
    B["avail_y"], B["avail_n"] = available(T, B)
    tr = (W.index < first) & S.ppc.notna()
    k = float(np.median(np.abs(W.ret[tr]) / S.ppc[tr]))
    z = np.sort((W.ret[tr] / (k * S.ppc[tr])).values)
    py = research.probs(B.assign(s0=B.s0_yes, left=B.left_yes), z, np.full(len(B), k))
    pn = research.probs(B.assign(s0=B.s0_no, left=B.left_no), z, np.full(len(B), k))
    rows = []
    for side, p, px, t, n, av, win in (("yes", py, B.ask, B.t_yes, B.n_yes, B.avail_y, B.y),
                                        ("no", 1 - pn, B.no_ask, B.t_no, B.n_no, B.avail_n, 1 - B.y)):
        fee = fee_c(px.values, 100)
        rows.append(pd.DataFrame({"series": series, "event": B.event, "day": B.day, "t": t, "side": side,
                                  "edge_c": 100 * (p - px.values) - fee, "pnl_c": 100 * win - 100 * px.values - fee,
                                  "cost_c": 100 * px.values + fee, "px": px.values, "entry_size": n, "avail": av,
                                  "prev_ratio": B.prev_ratio, "won": win}))
    C = pd.concat(rows, ignore_index=True)
    return C[np.isfinite(C.edge_c) & np.isfinite(C.pnl_c)]


def run(C, per_event, size, crowd, calm, stop, margin, slip=0.0, flip=False):
    D = C[C.edge_c > margin]
    if crowd:
        D = D[D.entry_size.fillna(0) <= crowd]
    if calm:
        D = D[~(D.prev_ratio > calm)]
    D = D.sort_values("t")
    if per_event:
        D = D.sort_values(["event", "edge_c"], ascending=[True, False]).groupby("event").head(per_event).sort_values("t")
    D = D[D.avail > 0].copy()
    D["n"] = np.minimum(D.avail, size)
    # flip = buy the opposite contract at (1 - our price), same fee formula (it's symmetric in p)
    pnl = (-(100 * D.won - 100 * D.px) - (D.cost_c - 100 * D.px)) if flip else D.pnl_c
    D["dollars"] = (pnl - slip) * D.n / 100
    if stop:
        D["cum"] = D.groupby("day").dollars.cumsum()
        prev = D.groupby("day").cum.shift(1).fillna(0)
        D = D[prev > -stop]                                         # bets after the day's loss passed the stop are skipped
    return D


def score(D, start, end):
    D = D[(D.day >= start) & (D.day < end)]
    days = pd.Series(0.0, index=pd.date_range(start, pd.Timestamp(end) - pd.Timedelta(days=1), freq="D").strftime("%Y-%m-%d"))
    daily = days.add(D.groupby("day").dollars.sum(), fill_value=0)
    eq = daily.cumsum()
    mdd = float((eq.cummax() - eq).max())
    tot = float(daily.sum())
    m = daily.groupby(daily.index.str[:7]).sum()
    return {"bets": len(D), "total_$": tot, "per_month_$": tot / max(1, len(daily) / 30.4), "max_dd_$": mdd,
            "calmar": tot / mdd if mdd > 0 else np.nan, "sharpe": daily.mean() / daily.std() * np.sqrt(365) if daily.std() > 0 else np.nan,
            "months_pos": f"{int((m > 0).sum())}/{len(m)}", "worst_month_$": float(m.min()) if len(m) else 0.0}


def bootstrap(D, start, end, n=2000, seed=0):
    D = D[(D.day >= start) & (D.day < end)]
    wk = D.groupby(pd.to_datetime(D.day).dt.strftime("%G-%V")).dollars.sum()
    r = np.random.default_rng(seed)
    sims = [r.choice(wk.values, len(wk), replace=True).sum() for _ in range(n)]
    return np.percentile(sims, [5, 50, 95]), float((np.array(sims) <= 0).mean())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", default="chunks")
    ap.add_argument("--out", default="results/IMPROVE.md")
    a = ap.parse_args()
    C = pd.concat([load(s, p, a.chunks) for s, p in PAIRS.items()], ignore_index=True)
    grid = list(itertools.product((1, 2, 0), (25, 50, 100), (0, 50, 200), (0, 2.0, 1.5), (0, 100, 200), (5, 8, 12)))
    rows = []
    for g in grid:
        D = run(C, *g)
        tr = score(D, *TRAIN)
        rows.append({"per_event": g[0] or "all", "size": g[1], "crowd": g[2] or "none", "calm": g[3] or "none",
                     "stop_$": g[4] or "none", "margin": g[5], **{f"train_{k}": v for k, v in tr.items()}, "_g": g})
    G = pd.DataFrame(rows)
    ok = G[G.train_bets >= 300].sort_values("train_calmar", ascending=False)
    best = ok.iloc[0]
    base_g = (0, 100, 0, 0, 0, 5)
    L = ["# Improving the range bot (BTC + ETH hourly ranges)", "",
         f"{len(grid)} risk-control combinations scored on TRAIN (Nov 2024 - Dec 2025); the best TRAIN Calmar is then "
         "run once on HOLDOUT (Jan - Sep 2026, 28 Sep excluded).", "",
         "## Top 10 on TRAIN", "",
         ok.drop(columns="_g").head(10).round(2).to_markdown(index=False), ""]
    rows = []
    for name, g in (("current bot (no controls)", base_g), ("chosen controls", best._g)):
        D = run(C, *g)
        rows.append({"bot": name, **{f"train_{k}": v for k, v in score(D, *TRAIN).items()},
                     **{f"hold_{k}": v for k, v in score(D, *HOLD).items()}})
    L += ["## Chosen controls vs current bot", "",
          f"Chosen: per_event={best.per_event}, size={best['size']}, crowd={best.crowd}, calm={best.calm}, "
          f"stop={best['stop_$']}, margin={best.margin}", "", pd.DataFrame(rows).round(2).to_markdown(index=False), ""]

    # reality checks on the chosen bot, whole period and holdout
    whole = (TRAIN[0], HOLD[1])
    chk = []
    for name, D in (("chosen bot", run(C, *best._g)),
                    ("placebo: opposite side of every bet", run(C, *best._g, flip=True)),
                    ("+1c slippage per contract", run(C, *best._g, slip=1.0)),
                    ("+2c slippage per contract", run(C, *best._g, slip=2.0))):
        chk.append({"check": name, **{f"all_{k}": v for k, v in score(D, *whole).items() if k in ("bets", "total_$", "sharpe", "max_dd_$")},
                    **{f"hold_{k}": v for k, v in score(D, *HOLD).items() if k in ("total_$", "sharpe")}})
    Cs = pd.concat([load(s, p, a.chunks, stale_min=5) for s, p in PAIRS.items()], ignore_index=True)
    D = run(Cs, *best._g)
    chk.append({"check": "placebo: model given a 5-minute-old price", **{f"all_{k}": v for k, v in score(D, *whole).items() if k in ("bets", "total_$", "sharpe", "max_dd_$")},
                **{f"hold_{k}": v for k, v in score(D, *HOLD).items() if k in ("total_$", "sharpe")}})
    Dc = run(C, *best._g)
    (lo, med, hi), p0 = bootstrap(Dc, *HOLD)
    q = Dc.groupby(pd.to_datetime(Dc.day).dt.to_period("Q").astype(str)).dollars.sum()
    L += ["## Is it real?", "", pd.DataFrame(chk).round(2).to_markdown(index=False), "",
          f"Holdout weekly block bootstrap: 90% interval for total profit ${lo:.0f} to ${hi:.0f} (median ${med:.0f}); "
          f"share of resamples at or below zero: {p0:.1%}.", "",
          "Profit by quarter (chosen bot): " + ", ".join(f"{k} ${v:.0f}" for k, v in q.items()), ""]
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    open(a.out, "w").write("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    main()
