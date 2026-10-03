"""Kalshi weekly AAA gas (KXAAAGASW, settles on Monday's AAA average) vs a direct h-day-ahead nowcast, real trades.

Each market trades Mon..Sun before the target Monday D.  Decision window: 10:00-12:00 ET on day t (AAA for t is
known), horizon h = D - t days.  Model: v(t+h) - v(t) (cents) = linear fit on the last 3 daily changes + UGA
1/5/10-day returns through t-1, fit on past days only (min 45 samples) separately per h; P(above strike) from past
residuals.  Entry/sizing/fee as gas.py.  Margin and horizon group picked on 2026-04..06, run once on 07..09.
  python backfill/gasweek.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from backtest import fee_c
from gas import CAP, HOLD, MIN_PAST, TRAIN, run

D = "data_local/nowcast"
GROUPS = {"early": range(4, 8), "late": range(1, 4)}


def daily():
    M = pd.read_parquet(f"{D}/KXAAAGASD_markets.parquet")
    M = M[M.event.str.match(r"KXAAAGASD-\d\d[A-Z]{3}\d\d$")]
    v = M.groupby(pd.to_datetime(M.event.str[-7:], format="%y%b%d")).value.first().sort_index()
    U = pd.read_parquet(f"{D}/UGA_daily.parquet")
    u = np.log(U.set_index(pd.to_datetime(U.day)).c).reindex(pd.date_range("2026-01-01", "2026-10-05")).ffill()
    return v[v.index >= "2026-03-01"], u


def predictions(v, u, mode="model"):
    """per (decision day t, h): (AAA on t, predicted v(t+h)-v(t) in cents, past residuals)"""
    d = v.diff() * 100
    X = pd.DataFrame({"d0": d, "d1": d.shift(1), "d2": d.shift(2),
                      "u1": (u.diff(1) * 100).shift(1).reindex(d.index),
                      "u5": (u.diff(5) * 100).shift(1).reindex(d.index),
                      "u10": (u.diff(10) * 100).shift(1).reindex(d.index)})
    cols = list(X.columns)
    out = {}
    for h in range(1, 8):
        F = X.assign(y=(v.shift(-h) - v) * 100)
        for t in F.dropna(subset=cols).index:
            past = F[(F.index + pd.Timedelta(days=h) <= t)].dropna()   # targets already known at t
            if len(past) < MIN_PAST:
                continue
            if mode == "zero":
                pred, res = 0.0, past.y.values
            else:
                A = np.c_[np.ones(len(past)), past[cols]]
                b = np.linalg.lstsq(A, past.y, rcond=None)[0]
                pred, res = float(np.r_[1, F.loc[t, cols].values] @ b), past.y.values - A @ b
            out[(t, h)] = (v.loc[t], pred, res)
    return out


def entries(P):
    M = pd.read_parquet(f"{D}/KXAAAGASW_markets.parquet")
    M = M[M.event.str.match(r"KXAAAGASW-\d\d[A-Z]{3}\d\d$") & (M.strike_type == "greater")].copy()
    M["day"] = pd.to_datetime(M.event.str[-7:], format="%y%b%d")
    T = pd.read_parquet(f"{D}/KXAAAGASW_trades.parquet")
    T["t"] = pd.to_datetime(T.ts, format="ISO8601", utc=True).dt.tz_convert("America/New_York")
    T = T[(T.t.dt.hour >= 10) & (T.t.dt.hour < 12)]
    T = T.merge(M[["ticker", "day", "floor", "result"]], on="ticker")
    T = T[T.result.isin(["yes", "no"])]
    T["dday"] = pd.to_datetime(T.t.dt.date)
    T["h"] = (T.day - T.dday).dt.days
    T = T[(T.h >= 1) & (T.h <= 7)].sort_values("t")
    T["px"] = np.where(T.taker == "yes", T.yes, 1 - T.yes)
    k = ["ticker", "dday", "taker"]
    first = T.groupby(k).head(1)
    J = first[k + ["t", "px"]].merge(T[k + ["t", "px", "count"]], on=k, suffixes=("", "_o"))
    av = J[(J.t_o > J.t) & (J.px_o <= J.px + 1e-9)].groupby(k)["count"].sum()
    E = first.join(av.rename("avail"), on=k)
    E["avail"] = E.avail.fillna(0)
    ps = []
    for r in E.itertuples():
        x = P.get((r.dday, r.h))
        ps.append(np.nan if x is None else float((x[0] + (x[1] + x[2]) / 100 > r.floor).mean()))
    E["p_yes"] = ps
    E["p"] = np.where(E.taker == "yes", E.p_yes, 1 - E.p_yes)
    E["won"] = np.where(E.taker == "yes", E.result == "yes", E.result == "no").astype(float)
    E["fee"] = fee_c(E.px.values, 100)
    E["edge_c"] = 100 * (E.p - E.px) - E.fee
    E["pnl_c"] = 100 * E.won - 100 * E.px - E.fee
    E["dstr"] = E.day.dt.strftime("%Y-%m-%d")
    E["window"] = np.where(E.h >= 4, "early", "late")
    return E[np.isfinite(E.p) & (E.px > 0) & (E.px < 1)]


def main():
    v, u = daily()
    E = entries(predictions(v, u))
    E["half"] = np.where(E.dstr < HOLD[0], "train", "holdout")
    L = ["# Kalshi weekly AAA gas (KXAAAGASW): h-day nowcast vs real trades", "", f"Entries: {len(E)}", "",
         "## Accuracy (Brier)", "",
         E.groupby(["half", "window"]).apply(lambda x: pd.Series({"n": len(x), "model": ((x.p - x.won) ** 2).mean(),
                                                                   "traded_price": ((x.px - x.won) ** 2).mean()})).round(4).to_markdown(), ""]
    grid = [(m, w) for m in (3, 5, 8, 12) for w in (("early",), ("late",), ("early", "late"))]
    G = pd.DataFrame([{"margin_c": m, "windows": "+".join(w), **run(E, m, w, *TRAIN)} for m, w in grid])
    best = G[G.bets >= 30].sort_values("day_t", ascending=False).iloc[0]
    bw = tuple(best.windows.split("+"))
    L += ["## Picked on Apr-Jun", "", G.to_markdown(index=False), "", f"Chosen: margin {best.margin_c}c, {best.windows}", ""]
    rows = [{"bot": "model", **run(E, best.margin_c, bw, *HOLD)},
            {"bot": "placebo: zero change", **run(entries(predictions(v, u, "zero")), best.margin_c, bw, *HOLD)}]
    L += ["## Holdout Jul-Sep (run once)", "", pd.DataFrame(rows).to_markdown(index=False), ""]
    open("../results/GAS_WEEKLY.md", "w").write("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    main()
