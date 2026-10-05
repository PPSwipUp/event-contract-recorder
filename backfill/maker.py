"""Market-making version of the range bot: rest orders and let takers who overpay (per the model) trade against us.

For every real taker trade in the database (BTC + ETH hourly ranges, 10-20 min after the open, Nov 2024 - Sep 2026):
  taker bought YES at y  -> we sold it to them = we hold NO bought at 1-y   (our edge = y - p_model)
  taker bought NO  at 1-y -> we sold NO        = we hold YES bought at y    (our edge = p_model - y)
We only take the trade if our edge after the maker fee beats the margin, and we get FILL of the trade's size
(queue position unknown -> 25% and 50% shown), max 100 contracts per trade.
Model = the same frozen vol model (fixed scale, PPC sigma, empirical z, spot one complete minute before the trade).
Maker fee assumed charged on every fill: ceil(0.0175 * n * p * (1-p)) (Kalshi's maker schedule; conservative).
Pre-declared: margin picked on TRAIN (2024-11..2025-12), run once on HOLDOUT (2026-01..09, 28 Sep excluded).
  python backfill/maker.py
"""
from __future__ import annotations

import glob
import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd

import research
from backtest import hourly, sigmas
from collect import coinbase

PAIRS = {"KXBTC": "BTC-USD", "KXETH": "ETH-USD"}
TRAIN, HOLD = ("2024-11-01", "2026-01-01"), ("2026-01-01", "2026-10-01")
EXCLUDE = {"2026-09-28"}


def maker_fee_c(p, n):
    return np.ceil(1.75 * n * p * (1 - p)) / n


def series_trades(series, product, chunks="data_local/chunks"):
    T = pd.concat([pd.read_parquet(f) for f in sorted(glob.glob(f"{chunks}/db-{series}-*/trades.parquet"))],
                  ignore_index=True)
    T["t"] = pd.to_datetime(T.ts, utc=True, format="ISO8601")
    T["close"] = pd.to_datetime(T.close, utc=True)
    T = T[T.result.isin(["yes", "no"])].copy()
    first = T.close.min()
    spot = coinbase(product, (first - pd.Timedelta(days=200)).to_pydatetime(), datetime.now(timezone.utc))
    W, minute = hourly(spot)
    S = sigmas(W)
    tr = (W.index < first) & S.ppc.notna()
    k = float(np.median(np.abs(W.ret[tr]) / S.ppc[tr]))
    z = np.sort((W.ret[tr] / (k * S.ppc[tr])).values)
    T["s0"] = minute.reindex(T.t.dt.floor("1min") - pd.Timedelta(minutes=1)).values
    T["left"] = np.sqrt(np.clip((T.close - T.t).dt.total_seconds().values / 3600, 0.01, 1))
    T["sig_raw"] = S.ppc.reindex(T.close - pd.Timedelta(hours=1)).values
    T["floor"] = pd.to_numeric(T["floor"], errors="coerce")
    T["cap"] = pd.to_numeric(T["cap"], errors="coerce")
    T = T[np.isfinite(T.s0) & np.isfinite(T.sig_raw)].copy()
    T["p_yes"] = research.probs(T, z, np.full(len(T), k))
    T["series"] = series
    return T


def main():
    cache = "data_local/maker_trades.parquet"
    if os.path.exists(cache):
        T = pd.read_parquet(cache)
    else:
        T = pd.concat([series_trades(s, p) for s, p in PAIRS.items()], ignore_index=True)
        T.to_parquet(cache)
    T["day"] = T.close.dt.strftime("%Y-%m-%d")
    T = T[~T.day.isin(EXCLUDE)]
    y = T.yes.values
    won_yes = (T.result == "yes").astype(float).values
    # our side is the opposite of the taker's
    T["our_px"] = np.where(T.taker == "yes", 1 - y, y)
    T["our_p"] = np.where(T.taker == "yes", 1 - T.p_yes, T.p_yes)
    T["won"] = np.where(T.taker == "yes", 1 - won_yes, won_yes)
    T = T[(T.our_px > 0) & (T.our_px < 1)].copy()

    def run(margin, fill, s, e, cap=100):
        n = np.minimum(T["count"].values * fill, cap)
        fee = maker_fee_c(T.our_px.values, np.maximum(n, 1))
        edge = 100 * (T.our_p - T.our_px) - fee
        pnl = 100 * T.won - 100 * T.our_px - fee
        m = (edge > margin) & (T.day >= s) & (T.day < e) & (n >= 1)
        B = T[m].assign(n=n[m], pnl_c=pnl[m], dollars=pnl[m] * n[m] / 100)
        d = B.groupby("day").dollars.sum()
        days = pd.date_range(s, pd.Timestamp(e) - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        alld = pd.Series(0.0, index=days).add(d, fill_value=0)
        eq = alld.cumsum()
        mo = alld.groupby(alld.index.str[:7]).sum()
        t = d.mean() / d.std() * np.sqrt(len(d)) if len(d) > 2 and d.std() > 0 else np.nan
        return {"fills": len(B), "contracts": round(B.n.sum()), "c_per_contract": round((B.pnl_c * B.n).sum() / max(1, B.n.sum()), 2),
                "per_month_$": round(alld.sum() / max(1, len(mo))), "max_dd_$": round((eq.cummax() - eq).max()),
                "day_t": round(t, 2), "months_pos": f"{(mo > 0).sum()}/{len(mo)}",
                "sharpe": round(alld.mean() / alld.std() * np.sqrt(365), 2) if alld.std() > 0 else np.nan}

    L = ["# Market-making range bot (BTC + ETH hourly ranges): sell to takers who overpay per the model", "",
         f"Taker trades: {len(T)}", ""]
    G = pd.DataFrame([{"margin_c": mg, **{f"train_{a}": b for a, b in run(mg, 0.25, *TRAIN).items()}} for mg in (2, 5, 8, 12, 20)])
    best = int(G[G.train_fills >= 300].sort_values("train_day_t", ascending=False).margin_c.iloc[0])
    L += ["## Margin picked on TRAIN (25% fill)", "", G.to_markdown(index=False), "", f"Chosen {best}c", "",
          "## HOLDOUT 2026 (run once)", "",
          pd.DataFrame([{"fill": f, "cap": c, **run(best, f, *HOLD, cap=c)} for f in (0.25, 0.5) for c in (25, 100)]).to_markdown(index=False), "",
          "Placebo (take the taker's side instead, same trades): "
          + str({"per_month_$": None}) , ""]
    # placebo: same selected trades but we join the taker (buy their side at their price, paying the taker fee)
    sel = T[(100 * (T.our_p - T.our_px) - maker_fee_c(T.our_px.values, 25) > best) & (T.day >= HOLD[0])]
    pl = (100 * (1 - sel.won) - 100 * (1 - sel.our_px) - np.ceil(7 * 25 * sel.our_px * (1 - sel.our_px)) / 25)
    L[-2] = f"Placebo (join the taker on the same holdout trades): {pl.mean():.2f}c per contract over {len(sel)} trades"
    open("../results/MAKER.md", "w").write("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    main()
