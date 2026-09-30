"""Backtest the volatility model against Kalshi's REAL hourly BTC/ETH range prices.

Decision one hour before settlement (the start of the hour being predicted):
  model price of each bracket = P(price ends inside it), from a volatility forecast for the coming hour
  buy YES at the ask   if model - ask - fee > margin
  buy NO  at 1 - bid   if bid - model - fee > margin
  settle with Kalshi's own result.  1 contract per trade; fees = Kalshi taker fee ceil(7% * P * (1-P)).

Volatility estimators (all use only data before the decision):
  ppc   ppc-forecaster (auto) on log hourly realised vol, seasons 1 day + 1 week
  last  the previous hour's realised vol            (placebo: a trivial rule)
  day   mean realised vol over the previous 24 hours (placebo)
If a placebo does as well as ppc, the profit isn't the model's.

  python backfill/backtest.py --data backfill/out
"""
from __future__ import annotations

import argparse
import math
import os

import numpy as np
import pandas as pd
from ppc import Forecaster

PAIRS = {"KXBTC": "BTC-USD", "KXETH": "ETH-USD"}
MARGINS = [2, 5, 10]


def hourly(spot):
    s = pd.Series(np.log(spot.c.values), index=pd.to_datetime(spot.ts, unit="s", utc=True))
    s = s[~s.index.duplicated()].sort_index()
    s = s.reindex(pd.date_range(s.index[0], s.index[-1], freq="1min", tz="UTC")).ffill()
    r = s.diff()
    g = s.index.floor("1h")
    W = pd.DataFrame({"open": s.groupby(g).first(), "close": s.groupby(g).last(),
                      "rv": np.sqrt((r ** 2).groupby(g).sum())})
    W["ret"] = W.close - W.open
    return W.dropna(), s


def sigmas(W):
    lrv = np.log(W.rv.clip(lower=1e-6))
    f = Forecaster(horizons=(1,), season=[24, 168], transform=None, fast=True)
    P = f.fit_predict(pd.DataFrame({"y": lrv.values}), target="y")
    out = pd.DataFrame(index=W.index)
    out["ppc"] = np.exp(pd.Series(P.auto_h1.values, index=W.index).shift(1))
    out["last"] = W.rv.shift(1)
    out["day"] = W.rv.shift(1).rolling(24, min_periods=12).mean()
    return out


def fee_c(p, n=1):
    """Kalshi taker fee in cents per contract for an order of n contracts at price p (dollars)"""
    return np.ceil(7 * n * p * (1 - p)) / n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="backfill/out")
    a = ap.parse_args()
    lines = ["# Volatility model vs Kalshi's real hourly range prices", ""]
    for series, product in PAIRS.items():
        B = pd.read_parquet(os.path.join(a.data, f"{series}.parquet"))
        spot = pd.read_parquet(os.path.join(a.data, f"{product}.parquet"))
        W, minute = hourly(spot)
        S = sigmas(W)
        B["close"] = pd.to_datetime(B.close, utc=True)
        B["win"] = B.close - pd.Timedelta(hours=1)                   # the hour being predicted
        B = B[B.win.isin(W.index)].copy()
        test_start = B.win.min()
        train = W.index < test_start
        for c in ("bid", "ask", "floor", "cap"):
            B[c] = pd.to_numeric(B[c], errors="coerce")
        B["y"] = (B.result == "yes").astype(float)
        B = B[B.result.isin(["yes", "no"])]
        B["quote_ts"] = pd.to_numeric(B.quote_ts, errors="coerce")
        qt = pd.to_datetime(B.quote_ts, unit="s", utc=True)
        # spot at the quote's minute (candle end = start of the next minute); time left until settlement
        s0 = minute.reindex(qt - pd.Timedelta(minutes=1)).values
        left = np.sqrt(np.clip((B.close - qt).dt.total_seconds().values / 3600, 0.01, 1))
        lines += [f"## {series}", "",
                  f"{B.event.nunique()} hourly events, {len(B)} brackets, {B.win.min():%Y-%m-%d} to {B.win.max():%Y-%m-%d}; "
                  f"vol model trained from {W.index[0]:%Y-%m-%d}.", ""]
        quoted = B.bid.notna() & B.ask.notna()
        lines += [f"Brackets with a live quote 1 h before: {quoted.mean():.0%}. "
                  f"Median spread {((B.ask - B.bid)[quoted] * 100).median():.0f}c.", ""]
        res = []
        for est in ("ppc", "last", "day"):
            sig_tr, r_tr = S[est][train].values, W.ret[train].values
            ok = np.isfinite(sig_tr) & (sig_tr > 0)
            k = np.median(np.abs(r_tr[ok]) / sig_tr[ok])
            z = np.sort(r_tr[ok] / (k * sig_tr[ok]))
            sig = k * S[est].reindex(B.win).values * left

            def cdf(K):
                x = (np.log(K) - s0) / sig
                return np.where(np.isnan(K), np.nan, np.searchsorted(z, np.nan_to_num(x)) / len(z))
            hi = np.where(B.cap.isna(), 1.0, cdf(B.cap.values))
            lo = np.where(B.floor.isna(), 0.0, cdf(B.floor.values))
            p = np.clip(hi - lo, 0, 1)
            y, bid, ask = B.y.values, B.bid.values, B.ask.values
            q = quoted.values & np.isfinite(p) & np.isfinite(sig)
            mid = (bid + ask) / 2
            brier_m = np.mean((p[q] - y[q]) ** 2)
            brier_mkt = np.mean((mid[q] - y[q]) ** 2)
            for m in MARGINS:
                for n in (1, 100):
                    fy, fn = fee_c(ask, n), fee_c(1 - bid, n)
                    buy_y = q & (ask > 0) & (ask < 1) & (100 * (p - ask) - fy > m)
                    buy_n = q & (bid > 0) & (bid < 1) & (100 * (bid - p) - fn > m)
                    pnl = np.r_[(100 * y - 100 * ask - fy)[buy_y], (100 * (1 - y) - 100 * (1 - bid) - fn)[buy_n]]
                    cost = np.r_[100 * ask[buy_y], 100 * (1 - bid[buy_n])]
                    res.append({"vol": est, "margin_c": m, "order_size": n, "trades": len(pnl),
                                "cents_per_trade": pnl.mean() if len(pnl) else np.nan,
                                "se": pnl.std() / math.sqrt(len(pnl)) if len(pnl) > 1 else np.nan,
                                "return_on_cost": pnl.sum() / cost.sum() if len(pnl) else np.nan,
                                "model_brier": brier_m, "market_brier": brier_mkt})
        R = pd.DataFrame(res)
        lines += ["Accuracy of the probabilities (Brier score, lower is better) on quoted brackets: "
                  + ", ".join(f"{e} {R[R.vol == e].model_brier.iloc[0]:.4f}" for e in ("ppc", "last", "day"))
                  + f", **market {R.market_brier.iloc[0]:.4f}**", ""]
        lines += [R.drop(columns=["model_brier", "market_brier"]).round(3).to_markdown(index=False), ""]
        print(f"{series} done", flush=True)
    text = "\n".join(lines)
    open(os.path.join(a.data, "RESULTS.md"), "w").write(text)
    print(text)


if __name__ == "__main__":
    main()
