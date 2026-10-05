"""Full simulation on the whole database (all four hourly crypto markets, Nov 2024 - Sep 2026), 28 Sep 2026 removed,
with a proper volume check.

Volume check: a bet is only as big as the contracts OTHER traders actually bought on the same side, at our price or
better, from our entry until the end of the 10-20 min window (capped at 100). If nobody else traded there, the bet
is skipped. Real liquidity may have been larger (resting orders that nobody took), so this is conservative.

Strategies: base (fixed scale, no filter, >5c) and the walk-forward self-tuning bot (best of 18 configs over the past
30 days, past data only).  Stats per market and combined: bets, win rate, c/bet, $, daily Sharpe, max drawdown,
best/worst day and month, % positive months, and compounding from $1,000.

  python backfill/sim.py --chunks chunks --out results/SIM.md
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
from tradebt import brackets

PAIRS = {"KXBTC": "BTC-USD", "KXETH": "ETH-USD", "KXBTCD": "BTC-USD", "KXETHD": "ETH-USD"}
EXCLUDE = {"2026-09-28"}
CAP = 100


def available(T, B):
    """per bracket and side: contracts others bought on that side at our price or better after our entry"""
    T = T.copy()
    T["t"] = pd.to_datetime(T.ts, utc=True, format="ISO8601")
    out = {}
    for side, px_col, entry_px, entry_t in (("yes", "yes", "ask", "t_yes"), ("no", "no", "no_ask", "t_no")):
        E = B[["ticker", entry_px, entry_t]].dropna()
        M = T[T.taker == side].merge(E, on="ticker")
        ok = (M[px_col] <= M[entry_px] + 1e-9) & (M.t >= M[entry_t])
        out[side] = M[ok].groupby("ticker")["count"].sum()
    return B.ticker.map(out["yes"]).fillna(0).values, B.ticker.map(out["no"]).fillna(0).values


def bets_for(B, z, k, filt, margin, X, avail_y, avail_n):
    py = research.probs(B.assign(s0=B.s0_yes, left=B.left_yes), z, k)
    pn = research.probs(B.assign(s0=B.s0_no, left=B.left_no), z, k)
    ay = an = np.ones(len(B), bool)
    if filt == "shrink50":
        py, pn = B.mkt.values + 0.5 * (py - B.mkt.values), B.mkt.values + 0.5 * (pn - B.mkt.values)
    if filt == "volview":
        ok = np.isfinite(X.s0) & np.isfinite(X.mkt)
        err = np.stack([np.where(ok, (research.probs(X, z, k, m) - B.mkt.values) ** 2, 0) for m in research.MULTS], 1)
        best = pd.DataFrame(err, index=B.index).groupby(B.event).sum().idxmin(axis=1).map(lambda j: research.MULTS[j])
        mm = B.event.map(best).values
        centre = np.where(B.floor.isna(), B.cap, np.where(B.cap.isna(), B.floor, (B.floor + B.cap) / 2))
        outer = np.abs(np.log(centre) - X.s0.values) / (k * B.sig_raw.values * X.left.values) > 1.0
        more, less = mm < 1 / 1.2, mm > 1.2
        ay, an = (more & outer) | (less & ~outer), (more & ~outer) | (less & outer)
    ask, nask, y = B.ask.values, B.no_ask.values, B.y.values
    by = np.isfinite(ask) & np.isfinite(py) & ay & (100 * (py - ask) - fee_c(ask, 100) > margin)
    bn = np.isfinite(nask) & np.isfinite(pn) & an & (100 * ((1 - pn) - nask) - fee_c(nask, 100) > margin)
    return pd.DataFrame({
        "day": np.r_[B.day.values[by], B.day.values[bn]],
        "pnl_c": np.r_[(100 * y - 100 * ask - fee_c(ask, 100))[by], (100 * (1 - y) - 100 * nask - fee_c(nask, 100))[bn]],
        "cost_c": np.r_[(100 * ask + fee_c(ask, 100))[by], (100 * nask + fee_c(nask, 100))[bn]],
        "avail": np.r_[avail_y[by], avail_n[bn]],
        "won": np.r_[y[by], 1 - y[bn]]})


def series_bets(series, product, chunks):
    files = sorted(glob.glob(os.path.join(chunks, f"db-{series}-*", "trades.parquet")))
    T = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    first = pd.to_datetime(T.close, utc=True).min()
    spot = coinbase(product, (first - pd.Timedelta(days=200)).to_pydatetime(), datetime.now(timezone.utc))
    W, minute = hourly(spot)
    S = sigmas(W)
    B = brackets(T, minute)
    B["sig_raw"] = S.ppc.reindex(B.win).values
    B = B[np.isfinite(B.sig_raw)].copy()
    B["day"] = B.close.dt.strftime("%Y-%m-%d")
    B = B[~B.day.isin(EXCLUDE)].reset_index(drop=True)
    avail_y, avail_n = available(T, B)
    tr = (W.index < first) & S.ppc.notna()
    k_fixed = float(np.median(np.abs(W.ret[tr]) / S.ppc[tr]))
    z = np.sort((W.ret[tr] / (k_fixed * S.ppc[tr])).values)
    k_roll = (np.abs(W.ret) / S.ppc).shift(1).rolling(24 * 30, min_periods=24 * 7).median().reindex(B.win).values
    k_roll = np.where(np.isfinite(k_roll), k_roll, k_fixed)
    X = B.assign(s0=B.s0_yes.fillna(B.s0_no), left=B.left_yes.fillna(B.left_no))
    configs = {(s, f, m): bets_for(B, z, np.full(len(B), k_fixed) if s == "fixed" else k_roll, f, m, X, avail_y, avail_n)
               for s, f, m in itertools.product(("fixed", "rolling"), ("none", "volview", "shrink50"), (2, 5, 10))}
    # the walk-forward bot scores configs by what they would have earned at fillable size
    days = sorted(B.day.unique())
    daily = pd.DataFrame({c: (D.pnl_c * np.minimum(D.avail, CAP) / 100).groupby(D.day).sum() for c, D in configs.items()}
                         ).reindex(days).fillna(0)
    wf = [configs[daily.iloc[i - 30:i].sum().idxmax()].pipe(lambda D, d=d: D[D.day == d]) for i, d in enumerate(days) if i >= 30]
    return {"base": configs[("fixed", "none", 5)],
            "self-tuning": pd.concat(wf, ignore_index=True) if wf else configs[("fixed", "none", 5)].iloc[:0]}


def stats(D, label):
    f = D[D.avail > 0]
    n = np.minimum(f.avail, CAP)
    dollars = f.pnl_c * n / 100
    day = dollars.groupby(f.day).sum()
    alldays = pd.Series(0.0, index=pd.date_range(D.day.min(), D.day.max(), freq="D").strftime("%Y-%m-%d")).add(day, fill_value=0)
    eq = alldays.cumsum()
    dd = float((eq.cummax() - eq).max())
    month = dollars.groupby(f.day.str[:7]).sum()
    sharpe = alldays.mean() / alldays.std() * np.sqrt(365) if alldays.std() > 0 else np.nan
    return {"strategy": label, "signals": len(D), "fillable": len(f), "fill_rate": len(f) / max(1, len(D)),
            "median_contracts": float(n.median()) if len(f) else 0, "win_rate": float(f.won.mean()) if len(f) else np.nan,
            "c_per_bet": float(f.pnl_c.mean()) if len(f) else np.nan, "total_$": float(dollars.sum()),
            "$_per_month": float(dollars.sum()) / max(1, len(alldays) / 30.4), "daily_sharpe_ann": sharpe,
            "max_drawdown_$": dd, "worst_day_$": float(alldays.min()), "best_day_$": float(alldays.max()),
            "months_positive": f"{int((month > 0).sum())}/{len(month)}", "worst_month_$": float(month.min()) if len(month) else 0}


def compound(D, start=1000.0, frac=0.02):
    """2% of the bankroll per bet, never more contracts than were fillable"""
    f = D[D.avail > 0].sort_values("day")
    bank, peak, mdd = start, start, 0.0
    for d, g in f.groupby("day"):
        n = np.minimum(bank * frac * 100 / g.cost_c.values, np.minimum(g.avail.values, CAP))
        bank = max(bank + float((n * g.pnl_c.values).sum() / 100), 0)
        peak = max(peak, bank)
        mdd = max(mdd, 1 - bank / peak)
    yrs = (pd.Timestamp(f.day.max()) - pd.Timestamp(f.day.min())).days / 365 if len(f) else 1
    return bank, (bank / start) ** (1 / yrs) - 1 if bank > 0 and yrs > 0 else -1, mdd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", default="chunks")
    ap.add_argument("--out", default="results/SIM.md")
    a = ap.parse_args()
    rows, comp, allb = [], [], {"base": [], "self-tuning": []}
    for series, product in PAIRS.items():
        res = series_bets(series, product, a.chunks)
        for strat, D in res.items():
            rows.append(stats(D, f"{series} {strat}"))
            allb[strat].append(D)
            fb, cg, md = compound(D)
            comp.append({"strategy": f"{series} {strat}", "final_$": fb, "CAGR": cg, "max_drawdown": md})
        print(series, "done", flush=True)
    for strat, parts in allb.items():
        D = pd.concat(parts, ignore_index=True)
        rows.append(stats(D, f"ALL FOUR {strat}"))
        fb, cg, md = compound(D)
        comp.append({"strategy": f"ALL FOUR {strat}", "final_$": fb, "CAGR": cg, "max_drawdown": md})
        for rng in (("KXBTC", "KXETH"),):
            Dr = pd.concat([allb[strat][list(PAIRS).index(s)] for s in rng], ignore_index=True)
            rows.append(stats(Dr, f"RANGES ONLY {strat}"))
            fb, cg, md = compound(Dr)
            comp.append({"strategy": f"RANGES ONLY {strat}", "final_$": fb, "CAGR": cg, "max_drawdown": md})
    L = ["# Full simulation, Nov 2024 - Sep 2026, 28 Sep 2026 excluded, volume-checked", "",
         "Each bet is only as big as what other traders actually bought on the same side at our price or better after "
         "our entry (max 100 contracts); bets with no such volume are skipped. Real fees, Kalshi's own results.", "",
         pd.DataFrame(rows).round(3).to_markdown(index=False), "",
         "## Compounding from $1,000 (2% of bankroll per bet, never more than the fillable volume)", "",
         pd.DataFrame(comp).round(3).to_markdown(index=False)]
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    open(a.out, "w").write("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    main()
