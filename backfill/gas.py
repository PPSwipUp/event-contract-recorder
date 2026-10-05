"""Kalshi daily AAA national gas price (KXAAAGASD) vs a nowcast model, on real trades.  2026-03 .. 2026-10.

Market for day D trades 08:00-24:00 ET on D-1 and settles on AAA's average for D.  At decision time on D-1 we know
AAA for D-1 and earlier, and the gasoline ETF (UGA) close up to D-2 (morning window) or D-1 (evening window).
Model: next daily change (cents) = linear fit on the last 3 changes + UGA 1/5/10-day log returns, refit every day on
past days only (min 45); P(above strike) = share of past residuals that would put AAA above the strike.
Entries: per market, side and window, the first real taker trade, sized to later same-side volume at that price or
better in the window (max 100), Kalshi taker fee.  Margin and window picked on 2026-04..06, run once on 07..10.
Placebo: same pipeline with the change model replaced by zero change (random-walk), and a shuffled-feature model.
  python backfill/gas.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from backtest import fee_c

D = "data_local/nowcast"
TRAIN, HOLD = ("2026-04-01", "2026-07-01"), ("2026-07-01", "2026-10-04")
MIN_PAST, CAP = 45, 100
WINDOWS = {"am": (8, 10), "pm": (17, 19)}         # ET hours on D-1


def series():
    M = pd.read_parquet(f"{D}/KXAAAGASD_markets.parquet")
    M = M[M.event.str.match(r"KXAAAGASD-\d\d[A-Z]{3}\d\d$")].copy()
    M["day"] = pd.to_datetime(M.event.str[-7:], format="%y%b%d")
    v = M.groupby("day").value.first().sort_index()
    v = v[v.index >= "2026-03-01"]
    U = pd.read_parquet(f"{D}/UGA_daily.parquet")
    u = np.log(U.set_index(pd.to_datetime(U.day)).c).reindex(pd.date_range("2026-01-01", "2026-10-05")).ffill()
    return M, v, u


def predictions(v, u, mode="model", seed=0):
    """per (target day D, window): (AAA on D-1, predicted change in cents, past residuals)"""
    d = v.diff() * 100
    out = {}
    for w, lag in (("am", 2), ("pm", 1)):                # UGA known through D-2 (am) or D-1 (pm)
        F = pd.DataFrame({"y": d, "d0": d.shift(1), "d1": d.shift(2), "d2": d.shift(3),
                          "u1": (u.diff(1) * 100).shift(lag).reindex(d.index),
                          "u5": (u.diff(5) * 100).shift(lag).reindex(d.index),
                          "u10": (u.diff(10) * 100).shift(lag).reindex(d.index)}).dropna()
        cols = ["d0", "d1", "d2", "u1", "u5", "u10"]
        if mode == "shuffled":
            rng = np.random.default_rng(seed)
            F[cols] = F[cols].values[rng.permutation(len(F))]
        for i in range(MIN_PAST, len(F)):
            past, r = F.iloc[:i], F.iloc[i]
            if mode == "zero":
                pred, res = 0.0, past.y.values
            else:
                A = np.c_[np.ones(len(past)), past[cols]]
                b = np.linalg.lstsq(A, past.y, rcond=None)[0]
                pred = float(np.r_[1, r[cols].values] @ b)
                res = past.y.values - A @ b
            day = F.index[i]
            out[(day, w)] = (v.loc[day - pd.Timedelta(days=1)], pred, res)
    return out


def entries(M, P):
    T = pd.read_parquet(f"{D}/KXAAAGASD_trades.parquet")
    T["t"] = pd.to_datetime(T.ts, format="ISO8601", utc=True).dt.tz_convert("America/New_York")
    T = T.merge(M[["ticker", "day", "floor", "cap", "strike_type", "result"]], on="ticker")
    T = T[T.result.isin(["yes", "no"]) & (T.strike_type == "greater")]
    T["px"] = np.where(T.taker == "yes", T.yes, 1 - T.yes)
    prev = (T.day - pd.Timedelta(days=1)).dt.date
    T["window"] = None
    for w, (h0, h1) in WINDOWS.items():
        T.loc[(T.t.dt.date == prev) & (T.t.dt.hour >= h0) & (T.t.dt.hour < h1), "window"] = w
    T = T.dropna(subset=["window"]).sort_values("t")
    k = ["ticker", "window", "taker"]
    first = T.groupby(k).head(1)
    J = first[k + ["t", "px"]].merge(T[k + ["t", "px", "count"]], on=k, suffixes=("", "_o"))
    av = J[(J.t_o > J.t) & (J.px_o <= J.px + 1e-9)].groupby(k)["count"].sum()
    E = first.join(av.rename("avail"), on=k)
    E["avail"] = E.avail.fillna(0)
    ps = []
    for r in E.itertuples():
        x = P.get((r.day, r.window))
        ps.append(np.nan if x is None else float((x[0] + (x[1] + x[2]) / 100 > r.floor).mean()))
    E["p_yes"] = ps
    E["p"] = np.where(E.taker == "yes", E.p_yes, 1 - E.p_yes)
    E["won"] = np.where(E.taker == "yes", E.result == "yes", E.result == "no").astype(float)
    E["fee"] = fee_c(E.px.values, 100)
    E["edge_c"] = 100 * (E.p - E.px) - E.fee
    E["pnl_c"] = 100 * E.won - 100 * E.px - E.fee
    E["dstr"] = E.day.dt.strftime("%Y-%m-%d")
    return E[np.isfinite(E.p) & (E.px > 0) & (E.px < 1)]


def run(E, margin, windows, s, e):
    B = E[(E.edge_c > margin) & (E.avail > 0) & E.window.isin(windows) & (E.dstr >= s) & (E.dstr < e)].copy()
    B["n"] = np.minimum(B.avail, CAP)
    B["dollars"] = B.pnl_c * B.n / 100
    days = pd.date_range(s, pd.Timestamp(e) - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    d = pd.Series(0.0, index=days).add(B.groupby("dstr").dollars.sum(), fill_value=0)
    eq = pd.concat([pd.Series([0.0]), d.cumsum()], ignore_index=True)
    mo = d.groupby(d.index.str[:7]).sum()
    return {"bets": len(B), "c_per_bet": round(B.pnl_c.mean(), 2) if len(B) else np.nan,
            "avg_contracts": round(B.n.mean(), 1) if len(B) else 0, "total_$": round(d.sum()),
            "per_month_$": round(d.sum() / max(1, len(mo))), "max_dd_$": round((eq.cummax() - eq).max()),
            "day_t": round(d.mean() / d.std() * np.sqrt(len(d)), 2) if d.std() > 0 else np.nan,
            "months_pos": f"{(mo > 0).sum()}/{len(mo)}"}


def main():
    M, v, u = series()
    E = entries(M, predictions(v, u))
    L = ["# Kalshi daily AAA gas (KXAAAGASD): nowcast model vs real trades", "",
         f"Entries: {len(E)} (first real trade per market/side/window)", "", "## Accuracy (Brier)", ""]
    E["half"] = np.where(E.dstr < HOLD[0], "train", "holdout")
    L += [E.groupby(["half", "window"]).apply(lambda x: pd.Series({
        "n": len(x), "model": ((x.p - x.won) ** 2).mean(), "traded_price": ((x.px - x.won) ** 2).mean()})).round(4).to_markdown(), ""]
    grid = [(m, w) for m in (3, 5, 8, 12) for w in (("am",), ("pm",), ("am", "pm"))]
    G = pd.DataFrame([{"margin_c": m, "windows": "+".join(w), **run(E, m, w, *TRAIN)} for m, w in grid])
    best = G[G.bets >= 50].sort_values("day_t", ascending=False).iloc[0]
    bw = tuple(best.windows.split("+"))
    L += ["## Picked on Apr-Jun", "", G.to_markdown(index=False), "", f"Chosen: margin {best.margin_c}c, windows {best.windows}", ""]
    rows = [{"bot": "model (chosen on Apr-Jun)", **run(E, best.margin_c, bw, *HOLD)}]
    for name, P in (("placebo: zero-change random walk", predictions(v, u, "zero")),
                    ("placebo: shuffled features", predictions(v, u, "shuffled"))):
        rows.append({"bot": name, **run(entries(M, P), best.margin_c, bw, *HOLD)})
    L += ["## Holdout Jul-Oct (run once)", "", pd.DataFrame(rows).to_markdown(index=False), ""]
    open("../results/GAS.md", "w").write("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    main()
