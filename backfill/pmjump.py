"""Can PPC's volatility forecast tell a Polymarket liquidity provider when a price jump is coming?

Markets: the 600 biggest current reward pools, kept if ending > 14 days out (the ones a liquidity provider would quote).
Data: hourly price history (CLOB prices-history), last ~6 months.  Target: the next hour's absolute move |dp|, and
a "jump" = |dp| >= 3c (enough to run through a quote v/3 from mid on a typical 4.5-6.5c max spread).
Forecasts of next-hour |dp| per market, all using only past hours:
  ppc    ppc-forecaster on log(|dp| + 0.1c), season 24h + 1 week
  last   last hour's |dp|                     (placebo)
  day    mean |dp| over the previous 24 hours (placebo)
Scored on the last 30% of each market's hours (earlier hours are warm-up): rank AUC for jumps across all markets,
and the share of jumps caught by pulling quotes in the riskiest 10% of market-hours.  PPC is only worth wiring into
the LP if it clearly beats both placebos out of sample.
  python backfill/pmjump.py
"""
from __future__ import annotations

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import requests
from ppc import Forecaster

import dohfix  # noqa: F401

D = "data_local/pmjump"
S = requests.Session()
JUMP = 0.03


def get(url, **p):
    for attempt in range(5):
        try:
            r = S.get(url, params=p, timeout=30)
            if r.status_code == 200:
                return r.json()
        except requests.RequestException:
            pass
        time.sleep(1 + 2 * attempt)
    return None


def markets():
    out, cur = [], ""
    while True:
        r = get("https://clob.polymarket.com/rewards/markets/current", **({"next_cursor": cur} if cur else {}))
        if not r:
            break
        out += [(float(x.get("total_daily_rate") or 0), x["condition_id"]) for x in r.get("data", [])]
        cur = r.get("next_cursor")
        if not cur or cur == "LTE=" or not r.get("data"):
            break
    return [c for _, c in sorted(out, reverse=True)[:600]]          # the 600 biggest pools


def history(cid):
    m = get("https://gamma-api.polymarket.com/markets", condition_ids=cid)
    if not m:
        return None
    m = m[0]
    end = m.get("endDate")
    if not end or datetime.fromisoformat(end.replace("Z", "+00:00")) < datetime.now(timezone.utc) + timedelta(days=14):
        return None
    tok = json.loads(m["clobTokenIds"])[0]
    now, pts = int(time.time()), {}
    for k in range(6):                                            # 6 x 30-day chunks
        t1 = now - k * 30 * 86400
        h = get("https://clob.polymarket.com/prices-history", market=tok, startTs=t1 - 30 * 86400, endTs=t1, fidelity=60)
        for x in (h or {}).get("history", []):
            pts[int(x["t"])] = float(x["p"])
    if len(pts) < 24 * 45:
        return None
    s = pd.Series(pts).sort_index()
    s.index = pd.to_datetime(s.index, unit="s", utc=True).floor("1h")
    s = s[~s.index.duplicated(keep="last")]
    s = s.reindex(pd.date_range(s.index[0], s.index[-1], freq="1h")).ffill()
    return pd.DataFrame({"cid": cid, "question": m["question"], "t": s.index, "p": s.values})


def forecasts(g):
    a = g.p.diff().abs().fillna(0).values
    y = np.log(a + 0.001)
    f = Forecaster(horizons=(1,), season=[24, 168], transform=None, fast=True)
    P = f.fit_predict(pd.DataFrame({"y": y}), target="y")
    out = g.copy()
    out["move"] = a
    out["next_move"] = pd.Series(a).shift(-1).values
    out["ppc"] = np.exp(P.auto_h1.values)                         # forecast of the NEXT hour, made at this hour
    out["last"] = a
    out["day"] = pd.Series(a).rolling(24, min_periods=6).mean().values
    n = len(out)
    out["test"] = np.arange(n) >= int(0.7 * n)
    return out.dropna(subset=["next_move"])


def auc(score, label):
    r = pd.Series(score).rank().values
    pos = label.astype(bool)
    n1, n0 = pos.sum(), (~pos).sum()
    return (r[pos].sum() - n1 * (n1 + 1) / 2) / (n1 * n0) if n1 and n0 else np.nan


def main():
    os.makedirs(D, exist_ok=True)
    path = f"{D}/history.parquet"
    if not os.path.exists(path):
        ids = markets()
        print(len(ids), "rewarded markets", flush=True)
        with ThreadPoolExecutor(6) as ex:
            H = [h for h in ex.map(history, ids) if h is not None]
        pd.concat(H, ignore_index=True).to_parquet(path)
    H = pd.read_parquet(path)
    print(H.cid.nunique(), "markets", len(H), "market-hours", flush=True)
    F = pd.concat([forecasts(g.reset_index(drop=True)) for _, g in H.groupby("cid")], ignore_index=True)
    T = F[F.test & F[["ppc", "last", "day"]].notna().all(axis=1)].copy()
    T["jump"] = T.next_move >= JUMP
    L = ["# Does PPC predict Polymarket price jumps (liquidity-provider risk)?", "",
         f"{T.cid.nunique()} markets, {len(T)} test market-hours, jumps (next-hour |dp| >= 3c): {T.jump.sum()} "
         f"({100 * T.jump.mean():.2f}%)", "", "| forecast | jump AUC | jumps caught by pulling riskiest 10% | "
         "log-move MSE |", "|---|---|---|---|"]
    for c in ("ppc", "last", "day"):
        cut = T[c].quantile(0.9)
        caught = T.loc[T[c] >= cut, "jump"].sum() / max(1, T.jump.sum())
        mse = ((np.log(T.next_move + 0.001) - np.log(T[c] + 0.001)) ** 2).mean()
        L.append(f"| {c} | {auc(T[c].values, T.jump.values):.3f} | {100 * caught:.1f}% | {mse:.3f} |")
    # per-market ranking: does PPC pick out the jumpy MARKETS (for market selection)?
    by = T.groupby("cid").agg(ppc=("ppc", "mean"), day=("day", "mean"), jumps=("jump", "mean"))
    L += ["", f"Market-level: Spearman(mean forecast, jump rate) ppc {by.ppc.corr(by.jumps, method='spearman'):.3f}, "
          f"day {by.day.corr(by.jumps, method='spearman'):.3f}", ""]
    open("../results/PM_JUMP.md", "w").write("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    main()
