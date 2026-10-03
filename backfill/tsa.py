"""Kalshi weekly TSA screenings (KXTSAW: Mon-Sun daily average above X) vs a nowcast, on real trades.  2022 .. 2026-09.

Decision window 10:00-12:00 ET on day t of the market's life.  Known: TSA daily counts up to t-2 (conservative; TSA
posts with a lag).  Unknown days d of the target week: n(d-364) (same weekday last year) x median ratio
n/n(-364) over the last 14 known days.  Error model: the same prediction made for every past week with the same
number of unknown days, relative error of the week average; P(above) = share of past errors putting it above.
Entry/sizing/fee as gas.py.  Margin picked on 2023-2025, run once on 2026.
  python backfill/tsa.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from backtest import fee_c
from gas import CAP, run

D = "data_local/nowcast"
TRAIN, HOLD = ("2023-01-01", "2026-01-01"), ("2026-01-01", "2026-10-01")


def nowcast(n, t, sunday):
    """predicted average for the Mon-Sun week ending `sunday`, as of day t"""
    days = pd.date_range(sunday - pd.Timedelta(days=6), sunday)
    known_to = t - pd.Timedelta(days=2)
    rec = n[(n.index > known_to - pd.Timedelta(days=14)) & (n.index <= known_to)]
    ly = n.reindex(rec.index - pd.Timedelta(days=364)).values
    ratio = np.nanmedian(rec.values / ly)
    vals = [n[d] if d <= known_to and d in n.index else n.get(d - pd.Timedelta(days=364), np.nan) * ratio for d in days]
    return float(np.mean(vals)), int(sum(d > known_to for d in days))


def errors(n):
    """relative error of the week-average nowcast, per (sunday, n_unknown), for every past week"""
    rows = []
    for sun in pd.date_range("2022-01-09", n.index.max(), freq="W-SUN"):
        if sun not in n.index:
            continue
        actual = n[sun - pd.Timedelta(days=6):sun].mean()
        for back in range(0, 9):
            t = sun + pd.Timedelta(days=1) - pd.Timedelta(days=back)
            pred, k = nowcast(n, t, sun)
            if np.isfinite(pred):
                rows.append({"sunday": sun, "k": k, "err": actual / pred - 1})
    return pd.DataFrame(rows)


def entries(n, Err, mode="model"):
    M = pd.read_parquet(f"{D}/KXTSAW_markets.parquet")
    M = M[(M.strike_type == "greater") & M.result.isin(["yes", "no"])].copy()
    M["sunday"] = pd.to_datetime(M.close, utc=True).dt.tz_convert("America/New_York").dt.normalize().dt.tz_localize(None)
    M["sunday"] = M.sunday.where(M.sunday.dt.dayofweek == 6, M.sunday - pd.Timedelta(days=1))
    T = pd.read_parquet(f"{D}/KXTSAW_trades.parquet")
    T["t"] = pd.to_datetime(T.ts, format="ISO8601", utc=True).dt.tz_convert("America/New_York")
    T = T[(T.t.dt.hour >= 10) & (T.t.dt.hour < 12)].merge(M[["ticker", "sunday", "floor", "result"]], on="ticker")
    T["dday"] = T.t.dt.normalize().dt.tz_localize(None)
    T = T[T.sunday.dt.dayofweek == 6].sort_values("t")
    T["px"] = np.where(T.taker == "yes", T.yes, 1 - T.yes)
    k = ["ticker", "dday", "taker"]
    first = T.groupby(k).head(1)
    J = first[k + ["t", "px"]].merge(T[k + ["t", "px", "count"]], on=k, suffixes=("", "_o"))
    av = J[(J.t_o > J.t) & (J.px_o <= J.px + 1e-9)].groupby(k)["count"].sum()
    E = first.join(av.rename("avail"), on=k)
    E["avail"] = E.avail.fillna(0)
    ps, cache = [], {}
    for r in E.itertuples():
        key = (r.dday, r.sunday)
        if key not in cache:
            pred, kk = nowcast(n, r.dday, r.sunday)
            past = Err[(Err.k == kk) & (Err.sunday + pd.Timedelta(days=2) <= r.dday)].err.tail(104).values
            if mode == "zero":                       # placebo: last year's same week, scaled by nothing
                pred = n.reindex(pd.date_range(r.sunday - pd.Timedelta(days=370), r.sunday - pd.Timedelta(days=364))).mean()
            cache[key] = (pred, past)
        pred, past = cache[key]
        ps.append(float((pred * (1 + past) > r.floor).mean()) if len(past) >= 20 and np.isfinite(pred) else np.nan)
    E["p_yes"] = ps
    E["p"] = np.where(E.taker == "yes", E.p_yes, 1 - E.p_yes)
    E["won"] = np.where(E.taker == "yes", E.result == "yes", E.result == "no").astype(float)
    E["fee"] = fee_c(E.px.values, 100)
    E["edge_c"] = 100 * (E.p - E.px) - E.fee
    E["pnl_c"] = 100 * E.won - 100 * E.px - E.fee
    E["dstr"] = E.sunday.dt.strftime("%Y-%m-%d")
    E["window"] = "all"
    return E[np.isfinite(E.p) & (E.px > 0) & (E.px < 1)]


def main():
    n = pd.read_parquet(f"{D}/tsa.parquet").n
    Err = errors(n)
    E = entries(n, Err)
    E["half"] = np.where(E.dstr < HOLD[0], "train", "holdout")
    L = ["# Kalshi weekly TSA screenings (KXTSAW): nowcast vs real trades", "", f"Entries: {len(E)}", "",
         "## Accuracy (Brier)", "",
         E.groupby("half").apply(lambda x: pd.Series({"n": len(x), "model": ((x.p - x.won) ** 2).mean(),
                                                      "traded_price": ((x.px - x.won) ** 2).mean()})).round(4).to_markdown(), ""]
    G = pd.DataFrame([{"margin_c": m, **run(E, m, ("all",), *TRAIN)} for m in (3, 5, 8, 12)])
    best = G[G.bets >= 30].sort_values("day_t", ascending=False).iloc[0]
    L += ["## Picked on 2023-2025", "", G.to_markdown(index=False), "", f"Chosen: margin {best.margin_c}c", ""]
    rows = [{"bot": "model", **run(E, best.margin_c, ("all",), *HOLD)},
            {"bot": "placebo: last year's week, unscaled", **run(entries(n, Err, "zero"), best.margin_c, ("all",), *HOLD)}]
    L += ["## Holdout 2026 (run once)", "", pd.DataFrame(rows).to_markdown(index=False), ""]
    open("../results/TSA.md", "w").write("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    main()
