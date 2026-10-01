"""Second forward test, frozen 2026-10-01 after the 2-year database test (results/DB_*.md):

  the plain BASELINE rule on BTC and ETH hourly RANGE markets: quotes 15 min after the open, model with a fixed vol
  scale, no filter, > 5c edge after fees, Kalshi taker fees and results.
(The database chose this rule; it is scored here only on days after it was frozen.)

  python backfill/forward_base.py --ledger results/forward_base_ledger.csv --out results/FORWARD_BASE.md
"""
from __future__ import annotations

import argparse
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

import collect
import research

START = "2026-10-02"                      # the first full day after the rule was frozen
PAIRS = {"KXBTC": "BTC-USD", "KXETH": "ETH-USD"}
LAG = 15


def score_day(series, product, day):
    d0 = datetime.fromisoformat(day).replace(tzinfo=timezone.utc)
    hours = pd.date_range(d0 + timedelta(hours=1), d0 + timedelta(hours=24), freq="1h", tz="UTC").to_pydatetime()
    with ThreadPoolExecutor(4) as ex:
        rows = [r for rs in ex.map(collect.one_event, [(series, h) for h in hours]) for r in rs]
    with tempfile.TemporaryDirectory() as tmp:
        pd.DataFrame(rows).to_parquet(os.path.join(tmp, f"{series}.parquet"))
        collect.coinbase(product, d0 - timedelta(days=200), d0 + timedelta(days=1, hours=2)).to_parquet(
            os.path.join(tmp, f"{product}.parquet"))
        B, z = research.prep(tmp, series, product)
    B = B[B.lag_min == LAG]
    if not len(B):
        return {"day": day, "series": series, "events": 0, "bets": 0, "pnl_c": 0.0}
    T = research.bets(B, research.probs(B, z, B.k_fixed.values))
    return {"day": day, "series": series, "events": int(B.event.nunique()), "bets": len(T), "pnl_c": float(T.pnl_c.sum())}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", default="results/forward_base_ledger.csv")
    ap.add_argument("--out", default="results/FORWARD_BASE.md")
    a = ap.parse_args()
    cols = ["day", "series", "events", "bets", "pnl_c"]
    led = pd.read_csv(a.ledger) if os.path.exists(a.ledger) else pd.DataFrame(columns=cols)
    done = set(zip(led.day.astype(str), led.series.astype(str)))
    today = datetime.now(timezone.utc).date()
    for day in [d.strftime("%Y-%m-%d") for d in pd.date_range(START, today - timedelta(days=1), freq="1D")]:
        for series, product in PAIRS.items():
            if (day, series) in done:
                continue
            r = score_day(series, product, day)
            print(r, flush=True)
            led = pd.concat([led, pd.DataFrame([r])], ignore_index=True)
            os.makedirs(os.path.dirname(a.ledger) or ".", exist_ok=True)
            led.to_csv(a.ledger, index=False)
    if not len(led):
        return
    d = led.groupby("day").pnl_c.sum().astype(float)
    t = d.mean() / (d.std(ddof=1) / np.sqrt(len(d))) if len(d) > 2 and d.std() > 0 else float("nan")
    L = ["# Forward test 2: baseline rule on BTC + ETH hourly ranges (frozen 2026-10-01)", "",
         "Pre-registered: success = day-level t above 2 after at least 60 days.", "",
         f"Days: {len(d)} · bets: {int(led.bets.sum())} · total at 100 contracts: **${d.sum():.0f}** · day-level t: **{t:.2f}**", "",
         led.groupby("series").agg(days=("day", "nunique"), bets=("bets", "sum"), dollars_100=("pnl_c", "sum")).to_markdown(), "",
         led.to_markdown(index=False)]
    open(a.out, "w").write("\n".join(L))
    print("\n".join(L[:5]))


if __name__ == "__main__":
    main()
