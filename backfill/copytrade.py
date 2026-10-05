"""Can you make money copying Polymarket's best traders?  Out-of-sample test on public wallet data.

Universe: top 500 wallets by all-time VOLUME (less survivorship than picking by profit) + top 200 by all-time PROFIT.
Data: each wallet's BUY trades (activity API) in A = 2026-01-01..05-01 and B = 2026-05-01..10-01 (up to 3,000 per
wallet per period, newest first), and every traded market's result (closed markets only; open ones are dropped).
Copy rule: buy what they buy, at THEIR price (zero delay = the most generous possible copy), hold to resolution,
Polymarket taker fee rate*p*(1-p) from the market's schedule.  Equal $100 per copied trade.
Pre-registered: pick the 20 wallets with the best copy return on A (>= 50 resolved buys in >= 10 markets), copy them on
B.  Also: does a wallet's A return predict its B return at all (rank correlation over all wallets)?
If even zero-delay copying fails on B, delayed (realistic) copying cannot work.
  python backfill/copytrade.py
"""
from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
import requests

import dohfix  # noqa: F401
from pmtouchdata import jget

D = "data_local/copytrade"
A, B = (1767225600, 1777593600), (1777593600, 1790812800)       # 2026-01-01, 05-01, 10-01 (UTC)
CAP, TOP = 3000, 20
S = requests.Session()


def wallets():
    out = {}
    for order, n in (("VOL", 500), ("PNL", 200)):
        for off in range(0, n, 50):
            for x in jget("https://data-api.polymarket.com/v1/leaderboard", timePeriod="all", orderBy=order, limit=50, offset=off) or []:
                out.setdefault(x["proxyWallet"], {"wallet": x["proxyWallet"], "lb_pnl": x["pnl"], "lb_vol": x["vol"], "source": order})
    return pd.DataFrame(out.values())


def buys(w, t0, t1):
    rows, end = {}, t1
    while len(rows) < CAP:
        j = jget("https://data-api.polymarket.com/activity", user=w, type="TRADE", limit=500, start=t0, end=end) or []
        new = 0
        for t in j:
            if t.get("side") != "BUY":
                continue
            k = (t["transactionHash"], t["asset"], t["size"])
            if k not in rows:
                new += 1
                rows[k] = {"wallet": w, "ts": t["timestamp"], "cid": t["conditionId"], "asset": t["asset"],
                           "oi": t.get("outcomeIndex"), "price": float(t["price"]), "usdc": float(t.get("usdcSize") or 0)}
        if len(j) < 500 or not new:
            break
        end = min(t["timestamp"] for t in j)
    return list(rows.values())


def results(cids):
    out = {}
    cids = list(cids)
    for i in range(0, len(cids), 100):
        r = S.get("https://gamma-api.polymarket.com/markets", timeout=120,
                  params=[("condition_ids", c) for c in cids[i:i + 100]] + [("closed", "true"), ("limit", 100)])
        for m in (r.json() if r.status_code == 200 else []):
            try:
                px = [float(x) for x in json.loads(m.get("outcomePrices") or "[]")]
            except ValueError:
                continue
            if px and max(px) == 1.0:                                 # cleanly resolved (no 50/50 or open)
                fs = m.get("feeSchedule") or {}
                out[m["conditionId"]] = (px, float(fs.get("rate") or 0) if m.get("feesEnabled") else 0.0, m.get("category"))
    return out


def score(T):
    g = T.groupby("wallet")
    return pd.DataFrame({"n": g.size(), "markets": g.cid.nunique(), "roi_c": g.pnl_c.mean()})


def main():
    os.makedirs(D, exist_ok=True)
    if not os.path.exists(f"{D}/wallets.parquet"):
        wallets().to_parquet(f"{D}/wallets.parquet")
    Wl = pd.read_parquet(f"{D}/wallets.parquet")
    print(len(Wl), "wallets", flush=True)
    if not os.path.exists(f"{D}/buys.parquet"):
        with ThreadPoolExecutor(6) as ex:
            res = list(ex.map(lambda w: buys(w, *A) + buys(w, *B), Wl.wallet))
        pd.DataFrame([t for r in res for t in r]).to_parquet(f"{D}/buys.parquet")
    T = pd.read_parquet(f"{D}/buys.parquet")
    print(len(T), "buys", T.cid.nunique(), "markets", flush=True)
    if not os.path.exists(f"{D}/results.json"):
        json.dump(results(T.cid.unique()), open(f"{D}/results.json", "w"))
    R = json.load(open(f"{D}/results.json"))
    T = T[T.cid.isin(R) & T.oi.notna() & (T.price > 0) & (T.price < 1)].copy()
    T["payoff"] = [R[c][0][int(o)] if int(o) < len(R[c][0]) else np.nan for c, o in zip(T.cid, T.oi)]
    T["rate"] = [R[c][1] for c in T.cid]
    T["category"] = [R[c][2] for c in T.cid]
    T = T.dropna(subset=["payoff"])
    T["pnl_c"] = 100 * (T.payoff - T.price) / T.price - 100 * T.rate * (1 - T.price)   # % return per $ copied
    T["period"] = np.where(T.ts < A[1], "A", "B")
    SA, SB = score(T[T.period == "A"]), score(T[T.period == "B"])
    elig = SA[(SA.n >= 50) & (SA.markets >= 10)]
    pick = elig.sort_values("roi_c", ascending=False).head(TOP).index
    both = elig.join(SB, rsuffix="_B", how="inner")
    both = both[both.n_B >= 50]
    rho = both.roi_c.rank().corr(both.roi_c_B.rank())
    TB = T[(T.period == "B") & T.wallet.isin(pick)].copy()
    TB["day"] = pd.to_datetime(TB.ts, unit="s").dt.strftime("%Y-%m-%d")
    wk = TB.groupby(pd.to_datetime(TB.day).dt.to_period("W")).pnl_c.sum()          # $ on $100 per trade
    allB = T[(T.period == "B") & T.wallet.isin(elig.index)]
    L = ["# Copy-trading Polymarket's top wallets: out-of-sample test", "",
         f"Universe {len(Wl)} wallets (top 500 by volume + top 200 by profit); resolved buys: {len(T):,}", "",
         f"Eligible on A (>= 50 resolved buys, >= 10 markets): {len(elig)}; with >= 50 buys in B too: {len(both)}", "",
         f"Persistence: rank correlation of copy return A vs B = {rho:.3f}", "",
         "## Top 20 picked on A (Jan-Apr 2026), copied on B (May-Sep 2026) at THEIR price (zero delay)", "",
         f"- On A (in-sample): mean return per copied trade {SA.loc[pick].roi_c.mean():.1f}% "
         f"(median wallet {SA.loc[pick].roi_c.median():.1f}%)",
         f"- On B (out-of-sample): {len(TB):,} trades, mean return per copied trade {TB.pnl_c.mean():.2f}%, "
         f"$100/trade -> total ${TB.pnl_c.sum():,.0f}, weekly t {wk.mean() / wk.std() * np.sqrt(len(wk)):.2f}, "
         f"positive weeks {(wk > 0).mean():.0%}",
         f"- Benchmark: copying ALL eligible wallets on B: mean {allB.pnl_c.mean():.2f}% per trade over {len(allB):,} trades", "",
         "Per picked wallet:", "", SA.loc[pick].join(SB, rsuffix="_B").round(2).to_markdown(), "",
         "B returns of the picked wallets by category:", "",
         TB.groupby("category").pnl_c.agg(["size", "mean"]).round(2).sort_values("size", ascending=False).head(12).to_markdown(), "",
         "B returns by entry price:", "",
         TB.groupby(pd.cut(TB.price, [0, 0.1, 0.3, 0.5, 0.7, 0.9, 0.97, 1])).pnl_c.agg(["size", "mean"]).round(2).to_markdown(), ""]
    open("../results/COPYTRADE.md", "w").write("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    main()
