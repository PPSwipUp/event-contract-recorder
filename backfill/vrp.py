"""Crypto volatility risk premium: does selling 30-day implied volatility (Deribit DVOL) and delta-hedging pay?

Proxy for a delta-hedged short ATM straddle / short variance swap, entered each day:
  sell 30-day vol at DVOL (annualised), realise the next 30 days of hourly Coinbase returns.
  P&L per $1 of vega notional (vol points) = (IV^2 - RV^2) / (2 * IV)   [variance-swap approximation]
Costs: option spread + fees + hedging, taken as a flat C vol points per trade (shown for 0, 1, 2, 3).
Pre-declared: no parameters to fit; 2025 is reported as 'train', 2026 (to the latest full 30-day window) as holdout.
Overlapping windows -> statistics on NON-overlapping monthly entries (1st of each month), plus the daily average.
Worst months shown: this trade earns small amounts most of the time and loses big in crashes.
  python backfill/vrp.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from backtest import hourly
from dvol import spot

H = 24 * 30


def run(cur, product):
    D = pd.read_parquet("data_local/dvol.parquet")
    iv = D[D.cur == cur].set_index("t").dvol.sort_index() / 100
    W, _ = hourly(spot(product))
    r = W.ret
    rv_fwd = np.sqrt((r ** 2).rolling(H).sum().shift(-H) * (8760 / H))     # realised vol over the NEXT 30 days
    X = pd.DataFrame({"iv": iv.reindex(W.index, method="ffill"), "rv": rv_fwd}).dropna()
    X = X[X.index >= "2025-01-01"]
    X["pnl"] = 100 * (X.iv ** 2 - X.rv ** 2) / (2 * X.iv)                  # vol points
    daily = X[X.index.hour == 0]
    monthly = daily[daily.index.day == 1]
    rows = []
    for name, s, e in (("2025", "2025-01-01", "2026-01-01"), ("2026", "2026-01-01", "2027-01-01")):
        m = monthly[(monthly.index >= s) & (monthly.index < e)]
        d = daily[(daily.index >= s) & (daily.index < e)]
        for cost in (0, 1, 2, 3):
            p = m.pnl - cost
            rows.append({"asset": cur, "period": name, "cost_volpts": cost, "months": len(m),
                         "mean_iv": round(100 * m.iv.mean(), 1), "mean_rv": round(100 * m.rv.mean(), 1),
                         "mean_pnl_volpts": round(p.mean(), 2), "worst_month": round(p.min(), 2),
                         "months_pos": f"{(p > 0).sum()}/{len(p)}",
                         "t_monthly": round(p.mean() / p.std() * np.sqrt(len(p)), 2) if len(p) > 2 and p.std() > 0 else np.nan,
                         "daily_mean": round((d.pnl - cost).mean(), 2)})
    return pd.DataFrame(rows), monthly


def main():
    out, months = [], []
    for cur, product in (("BTC", "BTC-USD"), ("ETH", "ETH-USD")):
        R, M = run(cur, product)
        out.append(R)
        months.append(M.assign(asset=cur))
    R = pd.concat(out)
    M = pd.concat(months)
    L = ["# Crypto volatility risk premium (sell 30-day Deribit implied vol, delta-hedged; variance-swap proxy)", "",
         "P&L in vol points per $1 vega per month; cost = spread + fees + hedging in vol points.", "",
         R.to_markdown(index=False), "",
         "## Every monthly entry (P&L before costs)", "",
         M.assign(iv=lambda x: (100 * x.iv).round(1), rv=lambda x: (100 * x.rv).round(1), pnl=lambda x: x.pnl.round(2))
          [["asset", "iv", "rv", "pnl"]].to_markdown(), ""]
    open("../results/VRP.md", "w").write("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    main()
