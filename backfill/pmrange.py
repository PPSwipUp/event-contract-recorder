"""Polymarket daily BTC/ETH price-range markets ("Bitcoin price on <date>?": less than / between / greater than, on the
Binance 1-min close at 12:00 ET) vs the frozen vol model, i.e. the range bot's idea on a daily horizon, other venue.
Model, entries, sizing, fee and placebo exactly as pmabove.py; P(bracket) = P(below hi) - P(below lo).
Margin picked on 2025-09..2026-01, run once on 2026-02..10.
  python backfill/pmrange.py            (downloads to data_local/pmrange on first run)
"""
from __future__ import annotations

import json
import os
import re
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

from backtest import hourly, sigmas
from dvol import spot
from pmtouch import PRODUCT, fee_c, run
from pmtouchdata import jget, trades

D = "data_local/pmrange"
SERIES = {"bitcoin": "bitcoin-neg-risk-weekly", "ethereum": "ethereum-neg-risk-weekly"}
TRAIN, HOLD = ("2025-09-01", "2026-02-01"), ("2026-02-01", "2026-10-03")


def bounds(q):
    xs = [float(x.replace(",", "").upper().replace("K", "")) * (1000 if "k" in x.lower() else 1)
          for x in re.findall(r"\$([\d,\.]+[kK]?)", q)]
    ql = q.lower()
    if "between" in ql and len(xs) == 2:
        return xs[0], xs[1]
    if ("less" in ql or "below" in ql) and xs:
        return np.nan, xs[0]
    if ("greater" in ql or "above" in ql) and xs:
        return xs[0], np.nan
    return None


def download():
    os.makedirs(D, exist_ok=True)
    rows = []
    for asset, ser in SERIES.items():
        off = 0
        while True:
            evs = jget("https://gamma-api.polymarket.com/events", series_slug=ser, closed="true", limit=100, offset=off)
            if not evs:
                break
            off += 100
            for e in evs:
                for m in e["markets"]:
                    b = bounds(m["question"])
                    if b is None:
                        continue
                    res = json.loads(m.get("outcomePrices") or "[]")
                    rows.append({"asset": asset, "cid": m["conditionId"], "lo": b[0], "hi": b[1], "end": e["endDate"],
                                 "result": None if not res else ("yes" if float(res[0]) > 0.5 else "no"),
                                 "volume": float(m.get("volume") or 0)})
        print(asset, sum(r["asset"] == asset for r in rows), "markets", flush=True)
    M = pd.DataFrame(rows).drop_duplicates("cid")
    M.to_parquet(f"{D}/markets.parquet")
    with ThreadPoolExecutor(6) as ex:
        res = list(ex.map(trades, M[M.volume > 0].cid))
    pd.DataFrame([t for r in res for t in r]).to_parquet(f"{D}/trades.parquet")


def entries(asset, stale_days=0):
    M = pd.read_parquet(f"{D}/markets.parquet")
    M = M[(M.asset == asset) & M.result.isin(["yes", "no"])].copy()
    M["end_t"] = pd.to_datetime(M.end, format="ISO8601", utc=True)
    T = pd.read_parquet(f"{D}/trades.parquet").merge(M, on="cid")
    T["t"] = pd.to_datetime(T.ts, unit="s", utc=True)
    T = T[T.t < T.end_t - pd.Timedelta(minutes=2)]
    buy_yes = ((T.side == "BUY") & (T.outcome == "Yes")) | ((T.side == "SELL") & (T.outcome == "No"))
    T["taker"] = np.where(buy_yes, "yes", "no")
    T["px"] = np.where(T.side == "BUY", T.price, 1 - T.price)
    T["day"] = T.t.dt.strftime("%Y-%m-%d")
    T = T[(T.px > 0.005) & (T.px < 0.995)].sort_values("t")
    k_ = ["cid", "taker", "day"]
    E = T.groupby(k_).head(1).copy()
    J = E[k_ + ["t", "px"]].merge(T[k_ + ["t", "px", "size"]], on=k_, suffixes=("", "_o"))
    av = J[(J.t_o > J.t) & (J.px_o <= J.px + 1e-9)].groupby(k_)["size"].sum()
    E = E.join(av.rename("avail"), on=k_)
    E["avail"] = E.avail.fillna(0)

    W, minute = hourly(spot(PRODUCT[asset]))
    S = sigmas(W)
    tr = (W.index < pd.Timestamp("2025-07-01", tz="UTC")) & S.ppc.notna()
    k = float(np.median(np.abs(W.ret[tr]) / S.ppc[tr]))
    z = np.sort((W.ret[tr] / (k * S.ppc[tr])).values)
    sig7 = S.ppc.rolling(24 * 7, min_periods=24).mean()
    t_known = E.t.dt.floor("1min") - pd.Timedelta(minutes=1) - pd.Timedelta(days=stale_days)
    E["s0"] = minute.reindex(t_known).values
    hours = (E.end_t - E.t).dt.total_seconds() / 3600
    sig = k * sig7.reindex(t_known.dt.floor("1h")).values * np.sqrt(np.clip(hours.values, 0.02, None))

    def below(x):
        out = np.searchsorted(z, np.nan_to_num((np.log(x) - E.s0.values) / sig)) / len(z)
        return out
    p_hi = np.where(np.isfinite(E.hi), below(E.hi.fillna(1).values), 1.0)
    p_lo = np.where(np.isfinite(E.lo), below(E.lo.fillna(1).values), 0.0)
    E["p_yes"] = p_hi - p_lo
    E = E[np.isfinite(E.s0) & np.isfinite(sig)].copy()
    E["p"] = np.where(E.taker == "yes", E.p_yes, 1 - E.p_yes)
    E["won"] = np.where(E.taker == "yes", E.result == "yes", E.result == "no").astype(float)
    E["fee"] = fee_c(E.px.values)
    E["edge_c"] = 100 * (E.p - E.px) - E.fee
    E["pnl_c"] = 100 * E.won - 100 * E.px - E.fee
    E["asset"] = asset
    E["hours_left"] = hours.reindex(E.index)
    return E


def main():
    if not os.path.exists(f"{D}/trades.parquet"):
        download()
    E = pd.concat([entries(a) for a in PRODUCT], ignore_index=True)
    E["half"] = np.where(E.day < HOLD[0], "train", "holdout")
    L = ["# Polymarket daily BTC/ETH price-range markets vs the frozen vol model", "", f"Entries: {len(E)}", "",
         "## Accuracy (Brier)", "",
         E.groupby(["half", "asset"]).apply(lambda x: pd.Series({"n": len(x), "model": ((x.p - x.won) ** 2).mean(),
                                                               "traded_price": ((x.px - x.won) ** 2).mean()})).round(4).to_markdown(), ""]
    G = pd.DataFrame([{"margin_c": m, **run(E, m, *TRAIN)} for m in (3, 5, 8, 12, 20)])
    best = G[G.bets >= 50].sort_values("week_t", ascending=False).iloc[0]
    L += ["## Picked on 2025-09..2026-01", "", G.to_markdown(index=False), "", f"Chosen: margin {best.margin_c}c", ""]
    P = pd.concat([entries(a, stale_days=1) for a in PRODUCT], ignore_index=True)
    rows = [{"bot": "model", **run(E, best.margin_c, *HOLD)},
            {"bot": "model, cap 500", **run(E, best.margin_c, *HOLD, cap=500)},
            {"bot": "placebo: 1-day-stale spot", **run(P, best.margin_c, *HOLD)}]
    L += ["## Holdout 2026-02..10 (run once)", "", pd.DataFrame(rows).to_markdown(index=False), ""]
    B = E[(E.edge_c > best.margin_c) & (E.avail > 0) & (E.day >= HOLD[0])]
    L += ["### holdout by asset / hours left", "",
          B.groupby(["asset", pd.cut(B.hours_left, [0, 1, 6, 24, 200])]).agg(bets=("pnl_c", "size"), c_per_bet=("pnl_c", "mean")).round(2).to_markdown(), ""]
    open("../results/PM_RANGE.md", "w").write("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    main()
