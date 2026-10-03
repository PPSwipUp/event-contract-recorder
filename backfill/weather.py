"""Kalshi daily-high temperature markets vs a forecast + observation model (6 cities, 2025-01 .. 2026-09).

At decision hour h (10:00 or 14:00 local) on day D, known: Open-Meteo hourly forecast issued the day before (f1),
station readings so far (running max), and every PAST day's official high.  Model for the official high H:
  mu = max(obs_max_so_far, forecast max over the remaining hours + city bias)
  bias and the error distribution of H - mu come only from the previous 120 days of the same city and decision hour
  H is an integer and can't end below what was already observed; P(bracket) = share of past errors landing in it.
Entries: per market, side and window, the first real taker trade (price we could have paid), sized to what other
takers bought at that price or better later in the window (max 100), Kalshi taker fee.
Pre-declared: margin (3/5/8/12c) and window (10h, 14h, both) picked on 2025; run once on 2026-01..09.
Placebo: the model fed the forecast issued 2 days before and no observations (should be worse, not better).
  python backfill/weather.py
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from backtest import fee_c
from weatherdata import CITIES, OUT

TRAIN, HOLD = ("2025-01-01", "2026-01-01"), ("2026-01-01", "2026-10-01")
LOOKBACK, MIN_PAST, CAP = 120, 45, 100


def features(series, placebo=False):
    tz = CITIES[series][4]
    tr = pd.read_parquet(f"{OUT}/{series}_truth.parquet").set_index("day").high
    fc = pd.read_parquet(f"{OUT}/{series}_fc.parquet")
    ob = pd.read_parquet(f"{OUT}/{series}_obs.parquet")
    fc["day"], fc["hour"] = fc.time.dt.strftime("%Y-%m-%d"), fc.time.dt.hour
    ob["day"], ob["hour"] = ob.valid.dt.strftime("%Y-%m-%d"), ob.valid.dt.hour
    rows = []
    for h in (10, 14):
        col = "f2" if placebo else "f1"
        rem = fc[fc.hour >= h].groupby("day")[col].max()
        so_far = ob[ob.hour < h].groupby("day").tmpf.max()
        F = pd.DataFrame({"rem": rem, "obs": np.nan if placebo else so_far}).reindex(tr.index)
        F["H"] = tr
        F["window"] = h
        rows.append(F)
    F = pd.concat(rows).reset_index().rename(columns={"index": "day"})
    return F.dropna(subset=["rem", "H"]).sort_values(["window", "day"])


def distributions(F):
    """per (day, window): bias-corrected mu and the past errors H - mu (only days before)"""
    out = {}
    for h, G in F.groupby("window"):
        G = G.reset_index(drop=True)
        for i in range(len(G)):
            past = G.iloc[max(0, i - LOOKBACK):i]
            if len(past) < MIN_PAST:
                continue
            bias = (past.H - past.rem).median()
            def mu_of(r):
                return np.fmax(r.obs, r.rem + bias) if np.isfinite(r.obs) else r.rem + bias
            err = (past.H - past.apply(mu_of, axis=1)).values
            r = G.iloc[i]
            out[(r.day, h)] = (mu_of(r), err, r.obs)
    return out


def p_bracket(mu, err, obs, floor, cap, stype):
    H = np.round(mu + err)
    if np.isfinite(obs):
        H = np.maximum(H, np.ceil(obs))                       # the official high can't be below what was seen
    if stype == "greater":
        return float((H > floor).mean())
    if stype == "less":
        return float((H < cap).mean())
    return float(((H >= floor) & (H <= cap)).mean())


def entries(series, D):
    M = pd.read_parquet(f"{OUT}/{series}_markets.parquet")
    T = pd.read_parquet(f"{OUT}/{series}_trades.parquet")
    if M.empty or T.empty:
        return pd.DataFrame()
    T["t"] = pd.to_datetime(T.ts, format="ISO8601", utc=True)
    T["px"] = np.where(T.taker == "yes", T.yes, 1 - T.yes)
    T = T.sort_values("t").merge(M[["ticker", "day", "floor", "cap", "strike_type", "result"]], on="ticker")
    T = T[T.result.isin(["yes", "no"])]
    first = T.groupby(["ticker", "window", "taker"]).head(1)
    J = first[["ticker", "window", "taker", "t", "px"]].merge(T[["ticker", "window", "taker", "t", "px", "count"]],
                                                               on=["ticker", "window", "taker"], suffixes=("", "_o"))
    av = J[(J.t_o > J.t) & (J.px_o <= J.px + 1e-9)].groupby(["ticker", "window", "taker"])["count"].sum()
    E = first.join(av.rename("avail"), on=["ticker", "window", "taker"])
    E["avail"] = E.avail.fillna(0)
    ps = []
    for r in E.itertuples():
        d = D.get((r.day, r.window))
        ps.append(np.nan if d is None else p_bracket(d[0], d[1], d[2], r.floor, r.cap, r.strike_type))
    E["p_yes"] = ps
    E["p"] = np.where(E.taker == "yes", E.p_yes, 1 - E.p_yes)
    E["won"] = np.where(E.taker == "yes", E.result == "yes", E.result == "no").astype(float)
    E["fee"] = fee_c(E.px.values, 100)
    E["edge_c"] = 100 * (E.p - E.px) - E.fee
    E["pnl_c"] = 100 * E.won - 100 * E.px - E.fee
    E["series"] = series
    return E[np.isfinite(E.p) & (E.px > 0) & (E.px < 1)]


def run(E, margin, windows, s, e):
    B = E[(E.edge_c > margin) & (E.avail > 0) & E.window.isin(windows) & (E.day >= s) & (E.day < e)].copy()
    B["n"] = np.minimum(B.avail, CAP)
    B["dollars"] = B.pnl_c * B.n / 100
    days = pd.date_range(s, pd.Timestamp(e) - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    d = pd.Series(0.0, index=days).add(B.groupby("day").dollars.sum(), fill_value=0)
    eq = pd.concat([pd.Series([0.0]), d.cumsum()], ignore_index=True)
    mo = d.groupby(d.index.str[:7]).sum()
    return {"bets": len(B), "c_per_bet": round(B.pnl_c.mean(), 2) if len(B) else np.nan,
            "avg_contracts": round(B.n.mean(), 1) if len(B) else 0, "total_$": round(d.sum()),
            "per_month_$": round(d.sum() / max(1, len(mo))), "max_dd_$": round((eq.cummax() - eq).max()),
            "day_t": round(d.mean() / d.std() * np.sqrt(len(d)), 2) if d.std() > 0 else np.nan,
            "months_pos": f"{(mo > 0).sum()}/{len(mo)}"}


def build(placebo=False):
    parts = []
    for series in CITIES:
        if not os.path.exists(f"{OUT}/{series}_trades.parquet"):
            continue
        D = distributions(features(series, placebo))
        parts.append(entries(series, D))
    return pd.concat(parts, ignore_index=True)


def main():
    E = build()
    L = [f"# Kalshi daily-high temperature: forecast + observation model vs real trades ({E.series.nunique()} cities)", "",
         f"Entries: {len(E)} (first real trade per market/side/window)", "",
         "## Accuracy (Brier, lower is better)", ""]
    E["year"] = E.day.str[:4]
    L += [E.groupby(["year", "window"]).apply(lambda x: pd.Series({
        "n": len(x), "model": ((x.p - x.won) ** 2).mean(), "traded_price": ((x.px - x.won) ** 2).mean()})).round(4).to_markdown(), ""]
    grid = [(m, w) for m in (3, 5, 8, 12) for w in ((10,), (14,), (10, 14))]
    G = pd.DataFrame([{"margin_c": m, "windows": "+".join(map(str, w)), **run(E, m, w, *TRAIN)} for m, w in grid])
    ok = G[G.bets >= 100]
    best = ok.sort_values("day_t", ascending=False).iloc[0]
    bw = tuple(int(x) for x in best.windows.split("+"))
    L += ["## Picked on 2025", "", G.to_markdown(index=False), "", f"Chosen: margin {best.margin_c}c, windows {best.windows}", ""]
    P = build(placebo=True)
    rows = [{"bot": "model (chosen on 2025)", **run(E, best.margin_c, bw, *HOLD)},
            {"bot": "placebo: 2-day-old forecast, no observations", **run(P, best.margin_c, bw, *HOLD)}]
    L += ["## 2026 holdout (run once)", "", pd.DataFrame(rows).to_markdown(index=False), ""]
    B = E[(E.edge_c > best.margin_c) & (E.avail > 0) & E.window.isin(bw) & (E.day >= HOLD[0])]
    L += ["### holdout by city", "", B.groupby("series").agg(bets=("pnl_c", "size"), c_per_bet=("pnl_c", "mean")).round(2).to_markdown(), ""]
    os.makedirs("../results", exist_ok=True)
    open("../results/WEATHER.md", "w").write("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    main()
