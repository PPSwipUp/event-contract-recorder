"""Polymarket weekly/monthly "What price will Bitcoin/Ethereum hit?" vs the frozen touch model (same as touch.py).

YES if any Binance 1-min high (reach) / low (dip) touches the strike inside the window.  Model, for a market not yet
touched: P(touch) = min(1, 2 * P(end beyond strike)) with the empirical shape z of hourly returns and
sigma = k * (7-day mean PPC hourly forecast) * sqrt(hours left); k, z from hourly data before 2025-07 (before any of
these markets).  Spot = Coinbase 1-min high/low, up to one minute before the trade; touched markets are skipped.
Entries: first real taker trade per market/side/UTC day; size = later same-side taker volume at that price or better
that day (max 100 shares); Polymarket taker fee taken as 0.07*p*(1-p) per share (conservative).
Pre-declared: margin picked on 2025-07..12, run once on 2026-01..09.  Placebo: model fed a 7-day-stale spot.
  python backfill/pmtouch.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from backtest import hourly, sigmas
from dvol import spot

D = "data_local/pmtouch"
TRAIN, HOLD = ("2025-07-01", "2026-01-01"), ("2026-01-01", "2026-10-02")
CAP = 100
PRODUCT = {"bitcoin": "BTC-USD", "ethereum": "ETH-USD"}


def fee_c(p):
    return 100 * 0.07 * p * (1 - p)


def entries(asset, stale_days=0):
    M = pd.read_parquet(f"{D}/markets.parquet")
    M = M[M.series.str.startswith(asset) & M.result.isin(["yes", "no"])].copy()
    M["end_t"] = pd.to_datetime(M.end, format="ISO8601", utc=True)
    weekly = M.series.str.endswith("weekly")
    first_of_month = (M.end_t - pd.Timedelta(days=1)).dt.to_period("M").dt.start_time.dt.tz_localize("UTC") + pd.Timedelta(hours=4)
    M["start_t"] = np.where(weekly, M.end_t - pd.Timedelta(days=7), first_of_month)
    M["start_t"] = pd.to_datetime(M.start_t, utc=True)
    T = pd.read_parquet(f"{D}/trades.parquet").merge(M, on="cid")
    T["t"] = pd.to_datetime(T.ts, unit="s", utc=True)
    T = T[(T.t >= T.start_t) & (T.t < T.end_t)]
    buy_yes = ((T.side == "BUY") & (T.outcome == "Yes")) | ((T.side == "SELL") & (T.outcome == "No"))
    T["taker"] = np.where(buy_yes, "yes", "no")
    T["px"] = np.where((T.side == "BUY"), T.price, 1 - T.price)
    T["day"] = T.t.dt.strftime("%Y-%m-%d")
    T = T[(T.px > 0.005) & (T.px < 0.995)].sort_values("t")
    k_ = ["cid", "taker", "day"]
    E = T.groupby(k_).head(1).copy()
    J = E[k_ + ["t", "px"]].merge(T[k_ + ["t", "px", "size"]], on=k_, suffixes=("", "_o"))
    av = J[(J.t_o > J.t) & (J.px_o <= J.px + 1e-9)].groupby(k_)["size"].sum()
    E = E.join(av.rename("avail"), on=k_)
    E["avail"] = E.avail.fillna(0)

    sp = spot(PRODUCT[asset])
    W, minute = hourly(sp)
    S = sigmas(W)
    tr = (W.index < pd.Timestamp("2025-07-01", tz="UTC")) & S.ppc.notna()
    k = float(np.median(np.abs(W.ret[tr]) / S.ppc[tr]))
    z = np.sort((W.ret[tr] / (k * S.ppc[tr])).values)
    sig7 = S.ppc.rolling(24 * 7, min_periods=24).mean()
    hi = pd.Series(np.log(sp.h.values), index=pd.to_datetime(sp.ts, unit="s", utc=True)).sort_index()
    lo = pd.Series(np.log(sp.l.values), index=hi.index).sort_index()
    hi, lo = hi[~hi.index.duplicated()], lo[~lo.index.duplicated()]

    t_known = E.t.dt.floor("1min") - pd.Timedelta(minutes=1) - pd.Timedelta(days=stale_days)
    E["s0"] = minute.reindex(t_known).values
    E["hi"] = [hi.loc[a:b].max() for a, b in zip(E.start_t, E.t.dt.floor("1min") - pd.Timedelta(minutes=1))]
    E["lo"] = [lo.loc[a:b].min() for a, b in zip(E.start_t, E.t.dt.floor("1min") - pd.Timedelta(minutes=1))]
    hours = (E.end_t - E.t).dt.total_seconds() / 3600
    sig = k * sig7.reindex(t_known.dt.floor("1h")).values * np.sqrt(np.clip(hours.values, 0.1, None))
    x = (np.log(E.strike.values) - E.s0.values) / sig
    p_above = 1 - np.searchsorted(z, np.nan_to_num(x)) / len(z)
    p_below = np.searchsorted(z, np.nan_to_num(x)) / len(z)
    E["p_yes"] = np.where(E.kind == "max", np.minimum(1, 2 * p_above), np.minimum(1, 2 * p_below))
    lk = np.log(E.strike.values)
    already = np.where(E.kind == "max", E.hi >= lk, E.lo <= lk)
    E = E[~already & np.isfinite(E.s0) & np.isfinite(sig)].copy()
    E["p"] = np.where(E.taker == "yes", E.p_yes, 1 - E.p_yes)
    E["won"] = np.where(E.taker == "yes", E.result == "yes", E.result == "no").astype(float)
    E["fee"] = fee_c(E.px.values)
    E["edge_c"] = 100 * (E.p - E.px) - E.fee
    E["pnl_c"] = 100 * E.won - 100 * E.px - E.fee
    E["asset"] = asset
    return E


def run(E, margin, s, e, cap=CAP):
    B = E[(E.edge_c > margin) & (E.avail > 0) & (E.day >= s) & (E.day < e)].copy()
    B["n"] = np.minimum(B.avail, cap)
    B["dollars"] = B.pnl_c * B.n / 100
    days = pd.date_range(s, pd.Timestamp(e) - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    d = pd.Series(0.0, index=days).add(B.groupby("day").dollars.sum(), fill_value=0)
    eq = pd.concat([pd.Series([0.0]), d.cumsum()], ignore_index=True)
    mo = d.groupby(d.index.str[:7]).sum()
    wk = d.groupby(pd.to_datetime(d.index).to_period("W")).sum()
    return {"bets": len(B), "c_per_bet": round(B.pnl_c.mean(), 2) if len(B) else np.nan,
            "avg_shares": round(B.n.mean(), 1) if len(B) else 0, "total_$": round(d.sum()),
            "per_month_$": round(d.sum() / max(1, len(mo))), "max_dd_$": round((eq.cummax() - eq).max()),
            "week_t": round(wk.mean() / wk.std() * np.sqrt(len(wk)), 2) if wk.std() > 0 else np.nan,
            "months_pos": f"{(mo > 0).sum()}/{len(mo)}"}


def main():
    E = pd.concat([entries(a) for a in PRODUCT], ignore_index=True)
    E["half"] = np.where(E.day < HOLD[0], "train", "holdout")
    L = ["# Polymarket BTC/ETH weekly+monthly hit-price markets vs the frozen touch model", "",
         f"Entries (first taker trade per market/side/day, strike not yet touched): {len(E)}", "", "## Accuracy (Brier)", "",
         E.groupby(["half", "asset"]).apply(lambda x: pd.Series({"n": len(x), "model": ((x.p - x.won) ** 2).mean(),
                                                               "traded_price": ((x.px - x.won) ** 2).mean()})).round(4).to_markdown(), ""]
    G = pd.DataFrame([{"margin_c": m, **run(E, m, *TRAIN)} for m in (3, 5, 8, 12, 20)])
    best = G[G.bets >= 50].sort_values("week_t", ascending=False).iloc[0]
    L += ["## Picked on 2025-07..12", "", G.to_markdown(index=False), "", f"Chosen: margin {best.margin_c}c", ""]
    P = pd.concat([entries(a, stale_days=7) for a in PRODUCT], ignore_index=True)
    rows = [{"bot": "model", **run(E, best.margin_c, *HOLD)},
            {"bot": "model, cap 500", **run(E, best.margin_c, *HOLD, cap=500)},
            {"bot": "placebo: 7-day-stale spot", **run(P, best.margin_c, *HOLD)}]
    L += ["## Holdout 2026-01..09 (run once)", "", pd.DataFrame(rows).to_markdown(index=False), ""]
    B = E[(E.edge_c > best.margin_c) & (E.avail > 0) & (E.day >= HOLD[0])]
    L += ["### holdout by asset / kind / side", "",
          B.groupby(["asset", "kind", "taker"]).agg(bets=("pnl_c", "size"), c_per_bet=("pnl_c", "mean")).round(2).to_markdown(), ""]
    open("../results/PM_TOUCH.md", "w").write("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    main()
