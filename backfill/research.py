"""Try a few PRE-DECLARED fixes to the range bot, honestly.

Data: the Aug-Sep 2026 backfill (every bracket's real bid/ask 1/5/15 min after the open, Kalshi results).
Rules decided before looking at results:
  - every variant is scored on AUGUST to pick a winner, then reported on SEPTEMBER untouched,
    and on September without 28 Sep (the single day that made almost all the earlier profit)
  - evidence is counted per DAY (bets on one day share the same BTC moves), not per bet
Variants:
  base      the current bot: model price vs ask/bid, 5c margin after fees
  rollk     same, but the vol scale is re-fitted every day on the trailing 30 days (not fixed once)
  shrink    the model's price pulled halfway to the market mid; bet only where it still beats the price
  volview   work out the volatility the market's prices imply each hour; if the model expects MORE movement,
            only buy outer brackets (YES) / sell inner ones (NO), if LESS only the opposite; need a 20% gap
  rollk+volview
  python backfill/research.py --data out --out results/RESEARCH.md
"""
from __future__ import annotations

import argparse
import os

import numpy as np
import pandas as pd

from backtest import PAIRS, fee_c, hourly, sigmas

MARGIN = 5.0
MULTS = np.exp(np.linspace(np.log(0.3), np.log(3.0), 31))     # candidate market-implied vol / model vol


def prep(data, series, product):
    B = pd.read_parquet(os.path.join(data, f"{series}.parquet"))
    W, minute = hourly(pd.read_parquet(os.path.join(data, f"{product}.parquet")))
    S = sigmas(W)
    B["close"] = pd.to_datetime(B.close, utc=True)
    B["win"] = B.close - pd.Timedelta(hours=1)
    B = B[B.win.isin(W.index) & B.result.isin(["yes", "no"])].copy()
    for c in ("bid", "ask", "floor", "cap", "quote_ts"):
        B[c] = pd.to_numeric(B[c], errors="coerce")
    B = B[B.bid.notna() & (B.ask > 0) & (B.ask < 1)].copy()
    B["y"] = (B.result == "yes").astype(float)
    qt = pd.to_datetime(B.quote_ts, unit="s", utc=True)
    B["s0"] = minute.reindex(qt - pd.Timedelta(minutes=1)).values
    B["left"] = np.sqrt(np.clip((B.close - qt).dt.total_seconds().values / 3600, 0.01, 1))
    B["sig_raw"] = S.ppc.reindex(B.win).values
    B = B[np.isfinite(B.s0) & np.isfinite(B.sig_raw)].copy()
    test_start = B.win.min()
    # fixed scale (as the bot does now): fitted once on everything before the test period
    tr = (W.index < test_start) & S.ppc.notna()
    k_fixed = float(np.median(np.abs(W.ret[tr]) / S.ppc[tr]))
    z = np.sort((W.ret[tr] / (k_fixed * S.ppc[tr])).values)
    # rolling scale: median |move| / forecast over the trailing 30 days, known at the start of each hour
    ratio = (np.abs(W.ret) / S.ppc).shift(1)
    k_roll = ratio.rolling(24 * 30, min_periods=24 * 7).median()
    B["k_fixed"] = k_fixed
    B["k_roll"] = k_roll.reindex(B.win).values
    return B, z


def probs(B, z, k, mult=1.0):
    sig = k * B.sig_raw.values * B.left.values * mult
    def cdf(K):
        x = (np.log(K) - B.s0.values) / sig                  # s0 is already a log price
        return np.searchsorted(z, np.nan_to_num(x)) / len(z)
    hi = np.where(B.cap.isna(), 1.0, cdf(B.cap.values))
    lo = np.where(B.floor.isna(), 0.0, cdf(B.floor.values))
    return np.clip(hi - lo, 0, 1)


def implied_mult(B, z, k):
    """per (event, lag): the vol multiplier whose bracket prices best match the market mids"""
    mid = ((B.bid + B.ask) / 2).values
    err = np.stack([(probs(B, z, k, m) - mid) ** 2 for m in MULTS], 1)
    E = pd.DataFrame(err, index=B.index)
    key = [B.event, B.lag_min]
    best = E.groupby(key).sum().idxmin(axis=1).map(lambda j: MULTS[j])
    return pd.Series(best.reindex(pd.MultiIndex.from_arrays(key)).values, index=B.index)


def bets(B, p, allow_yes=None, allow_no=None):
    ask, bid, y = B.ask.values, B.bid.values, B.y.values
    fy, fn = fee_c(ask, 100), fee_c(1 - bid, 100)
    by = (100 * (p - ask) - fy > MARGIN)
    bn = (100 * (bid - p) - fn > MARGIN) & (bid > 0)
    if allow_yes is not None:
        by &= allow_yes
        bn &= allow_no
    out = pd.concat([
        pd.DataFrame({"day": B.close.dt.strftime("%Y-%m-%d").values[by], "lag": B.lag_min.values[by],
                      "pnl_c": (100 * y - 100 * ask - fy)[by]}),
        pd.DataFrame({"day": B.close.dt.strftime("%Y-%m-%d").values[bn], "lag": B.lag_min.values[bn],
                      "pnl_c": (100 * (1 - y) - 100 * (1 - bid) - fn)[bn]})], ignore_index=True)
    return out


def score(T):
    """bets, cents/bet, $ at 100 contracts, and a t-stat over DAYS (each day's total is one observation)"""
    if not len(T):
        return {"bets": 0, "days": 0, "cents_per_bet": np.nan, "dollars_100": 0.0, "t_days": np.nan}
    d = T.groupby("day").pnl_c.sum()
    t = d.mean() / (d.std(ddof=1) / np.sqrt(len(d))) if len(d) > 2 and d.std() > 0 else np.nan
    return {"bets": len(T), "days": len(d), "cents_per_bet": T.pnl_c.mean(), "dollars_100": T.pnl_c.sum(), "t_days": t}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="out")
    ap.add_argument("--out", default="results/RESEARCH.md")
    a = ap.parse_args()
    L = ["# Fixing the range bot: pre-declared variants, chosen on August, tested on September", "",
         "t_days = t-statistic with each DAY as one observation (|t| > 2 is the bar).", ""]
    for series, product in PAIRS.items():
        B, z = prep(a.data, series, product)
        p_fixed = probs(B, z, B.k_fixed.values)
        p_roll = probs(B, z, np.where(np.isfinite(B.k_roll), B.k_roll, B.k_fixed))
        mid = ((B.bid + B.ask) / 2).values
        m_fixed = implied_mult(B, z, B.k_fixed.values).values
        m_roll = implied_mult(B, z, np.where(np.isfinite(B.k_roll), B.k_roll, B.k_fixed)).values
        # outer = bracket centre more than one model sigma from the spot
        centre = np.where(B.floor.isna(), B.cap, np.where(B.cap.isna(), B.floor, (B.floor + B.cap) / 2))
        dist = np.abs(np.log(centre) - B.s0.values) / (B.k_fixed.values * B.sig_raw.values * B.left.values)
        outer = dist > 1.0

        def view(m):            # m = market vol / model vol
            more = m < 1 / 1.2                                   # model expects more movement than the market
            less = m > 1.2
            return (more & outer) | (less & ~outer), (more & ~outer) | (less & outer)
        V = {
            "base": bets(B, p_fixed),
            "rollk": bets(B, p_roll),
            "shrink": bets(B, mid + 0.5 * (p_fixed - mid)),
            "volview": bets(B, p_fixed, *view(m_fixed)),
            "rollk+volview": bets(B, p_roll, *view(m_roll)),
        }
        rows = []
        for name, T in V.items():
            for lag in (1, 5, 15):
                t = T[T.lag == lag]
                aug, sep = t[t.day < "2026-09-01"], t[t.day >= "2026-09-01"]
                rows.append({"variant": name, "min_after_open": lag,
                             **{f"aug_{k}": v for k, v in score(aug).items() if k in ("bets", "cents_per_bet", "t_days")},
                             **{f"sep_{k}": v for k, v in score(sep).items() if k in ("bets", "cents_per_bet", "dollars_100", "t_days")},
                             "sep_excl_28th_$": score(sep[sep.day != "2026-09-28"])["dollars_100"]})
        R = pd.DataFrame(rows)
        best = R.loc[R.aug_t_days.idxmax()] if R.aug_t_days.notna().any() else None
        L += [f"## {series}", "", R.round(2).to_markdown(index=False), ""]
        if best is not None:
            L += [f"**Chosen on August (highest day-level t): {best.variant}, {int(best.min_after_open)} min after open.** "
                  f"September, untouched: {best.sep_bets:.0f} bets, {best.sep_cents_per_bet:.1f}c/bet, "
                  f"${best.sep_dollars_100:.0f} at 100 contracts, day-level t {best.sep_t_days:.2f}; "
                  f"without 28 Sep ${best['sep_excl_28th_$']:.0f}.", ""]
        L += [f"Market-implied vol vs model (median ratio): {np.nanmedian(m_fixed):.2f}; "
              f"the model's own day-to-day scale drift (rolling k / fixed k, median): {np.nanmedian(B.k_roll / B.k_fixed):.2f}", ""]
        print(f"{series} done", flush=True)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    open(a.out, "w").write("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    main()
