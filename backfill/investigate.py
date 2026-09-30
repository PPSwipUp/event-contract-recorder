"""Why did the first-minute BTC bets only make money on a few days (and why no bets before July)?

  python backfill/investigate.py --chunks chunks --out results/INVESTIGATE.md
1. Did Kalshi have hourly BTC/ETH range markets in Jan-Jun, and do their prices exist?
2. For every first-minute bet: how much BTC moved in the hour before the market opened (when the prices were set),
   and how big the move in the hour itself was, vs the model's forecast.  Top days vs the rest.
"""
from __future__ import annotations

import argparse
import glob
import os
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from collect import K, event_ticker, get, markets_of
from backtest import hourly, sigmas


def coverage():
    rows = []
    for series in ("KXBTC", "KXETH"):
        for month in range(1, 10):
            close = datetime(2026, month, 15, 16, tzinfo=timezone.utc)          # 12:00 ET on the 15th
            ev = event_ticker(series, close)
            ms = markets_of(series, ev)
            c = int(close.timestamp())
            d = get(f"{K}/series/{series}/events/{ev}/candlesticks", period_interval=1, start_ts=c - 3600, end_ts=c - 3300)
            n = sum(1 for x in (d or {}).get("market_candlesticks", []) if x)
            first = get(f"{K}/series/{series}/events/{ev}/candlesticks", period_interval=60, start_ts=c - 86400 * 2, end_ts=c)
            n60 = sum(1 for x in (first or {}).get("market_candlesticks", []) if x)
            rows.append({"series": series, "event": ev, "markets": len(ms),
                         "open_time": ms[0].get("open_time") if ms else None,
                         "markets_with_1min_prices_in_first_5min": n, "markets_with_any_hourly_prices": n60})
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", default="chunks")
    ap.add_argument("--out", default="results/INVESTIGATE.md")
    a = ap.parse_args()
    L = ["# Investigation", "", "## 1. Kalshi hourly range markets by month (the 15th, 12pm ET)", ""]
    L += [coverage().to_markdown(index=False), ""]

    P = pd.concat([pd.read_parquet(f) for f in glob.glob(os.path.join(a.chunks, "*", "picks_filled.parquet"))], ignore_index=True)
    P = P[(P.series == "KXBTC") & (P.lag_min == 1)].copy()
    P["close"] = pd.to_datetime(P.close, utc=True)
    P["day"] = P.close.dt.strftime("%Y-%m-%d")
    P["dollars"] = np.where(P.filled_contracts > 0, P.pnl_c * np.minimum(P.filled_contracts, 100) / 100, 0.0)

    # BTC minutes around the bets, and the model's hourly forecasts learned continuously up to each bet
    from collect import coinbase
    start = P.close.min() - timedelta(days=200)
    spot = coinbase("BTC-USD", start.to_pydatetime(), P.close.max().to_pydatetime() + timedelta(hours=1))
    W, minute = hourly(spot)
    S = sigmas(W)
    win = P.close - pd.Timedelta(hours=1)
    opened = pd.to_datetime(P.open_time, utc=True, errors="coerce").fillna(win)
    at_open = minute.reindex(opened.dt.floor("1min")).values
    hour_before = minute.reindex((opened - pd.Timedelta(hours=1)).dt.floor("1min")).values
    P["move_before_open_pct"] = 100 * (at_open - hour_before)                    # log % move while the book was set
    P["move_in_hour_pct"] = 100 * W.ret.reindex(win).values
    P["forecast_vol_pct"] = 100 * S.ppc.reindex(win).values
    P["actual_vol_pct"] = 100 * W.rv.reindex(win).values
    P["forecast_error_ratio"] = P.actual_vol_pct / P.forecast_vol_pct

    D = P.groupby("day").agg(bets=("pnl_c", "size"), dollars=("dollars", "sum"), cents_per_bet=("pnl_c", "mean"),
                             abs_move_before_open=("move_before_open_pct", lambda x: np.nanmean(np.abs(x))),
                             abs_move_in_hour=("move_in_hour_pct", lambda x: np.nanmean(np.abs(x))),
                             vol_actual_over_forecast=("forecast_error_ratio", "median")).sort_values("dollars", ascending=False)
    L += ["## 2. First-minute BTC bets: the 10 best days and the 10 worst", "",
          D.head(10).round(3).to_markdown(), "", D.tail(10).round(3).to_markdown(), ""]

    P["big_move_before"] = np.abs(P.move_before_open_pct) > np.nanpercentile(np.abs(W.ret) * 100, 80)
    G = P.groupby("big_move_before").agg(bets=("pnl_c", "size"), cents_per_bet=("pnl_c", "mean"),
                                         se=("pnl_c", lambda x: x.std() / np.sqrt(len(x))), dollars=("dollars", "sum"))
    L += ["## 3. Does the profit come from BTC having moved just before the market opened?", "",
          "big_move_before = BTC moved more in the hour before opening than in 80% of all hours.", "",
          G.round(3).to_markdown(), "",
          f"Correlation of each bet's profit with the size of the move before the open: "
          f"{np.corrcoef(P.pnl_c, np.abs(P.move_before_open_pct.fillna(0)))[0, 1]:.3f}", ""]

    top = set(D.head(5).index)
    P["top5"] = P.day.isin(top)
    F = P.groupby("top5").agg(bets=("pnl_c", "size"), vol_actual_over_forecast=("forecast_error_ratio", "median"),
                              abs_move_in_hour=("move_in_hour_pct", lambda x: np.nanmean(np.abs(x))))
    L += ["## 4. Was the volatility model worse or better on the top days? (it updates every hour, prequentially)", "",
          "vol_actual_over_forecast = realised hourly vol / the model's forecast made the hour before (1 = spot on).", "",
          F.round(3).to_markdown(), ""]
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    open(a.out, "w").write("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    main()
