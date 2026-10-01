"""Forward test of ONE rule, frozen on 2026-10-01 (chosen on August, untouched on September; see RESEARCH.md):

  ETH hourly ranges, quotes 15 min after the market opens, rolling vol-scale recalibration + volatility view,
  > 5c edge after fees, 100 contracts per bet, Kalshi taker fees, Kalshi's own results.

Each run scores every finished UTC day from START that isn't in the ledger yet, using only data that existed
after the rule was frozen.  Nothing here may change once results come in.

  python backfill/forward.py --ledger results/forward_ledger.csv --out results/FORWARD.md
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

START = "2026-10-01"
SERIES, PRODUCT, LAG = "KXETH", "ETH-USD", 15


def score_day(day):
    d0 = datetime.fromisoformat(day).replace(tzinfo=timezone.utc)
    hours = pd.date_range(d0 + timedelta(hours=1), d0 + timedelta(hours=24), freq="1h", tz="UTC").to_pydatetime()
    with ThreadPoolExecutor(4) as ex:
        rows = [r for rs in ex.map(collect.one_event, [(SERIES, h) for h in hours]) for r in rs]
    with tempfile.TemporaryDirectory() as tmp:
        pd.DataFrame(rows).to_parquet(os.path.join(tmp, f"{SERIES}.parquet"))
        collect.coinbase(PRODUCT, d0 - timedelta(days=200), d0 + timedelta(days=1, hours=2)).to_parquet(
            os.path.join(tmp, f"{PRODUCT}.parquet"))
        B, z = research.prep(tmp, SERIES, PRODUCT)
    B = B[B.lag_min == LAG]
    if not len(B):
        return {"day": day, "events": 0, "bets": 0, "pnl_c": 0.0}
    k = np.where(np.isfinite(B.k_roll), B.k_roll, B.k_fixed)
    p = research.probs(B, z, k)
    m = research.implied_mult(B, z, k).values
    centre = np.where(B.floor.isna(), B.cap, np.where(B.cap.isna(), B.floor, (B.floor + B.cap) / 2))
    outer = np.abs(np.log(centre) - B.s0.values) / (B.k_fixed.values * B.sig_raw.values * B.left.values) > 1.0
    more, less = m < 1 / 1.2, m > 1.2
    T = research.bets(B, p, (more & outer) | (less & ~outer), (more & ~outer) | (less & outer))
    return {"day": day, "events": int(B.event.nunique()), "bets": len(T), "pnl_c": float(T.pnl_c.sum())}


def report(led, out):
    d = led.pnl_c.astype(float)
    n = len(led)
    t = d.mean() / (d.std(ddof=1) / np.sqrt(n)) if n > 2 and d.std() > 0 else float("nan")
    L = ["# Forward test (rule frozen 2026-10-01)", "",
         "ETH hourly ranges, 15 min after open, rolling recalibration + volatility view, >5c edge after fees, "
         "100 contracts per bet. Pre-registered: success = day-level t above 2 after at least 60 days.", "",
         f"Days: {n} · bets: {int(led.bets.sum())} · total at 100 contracts: **${d.sum():.0f}** · "
         f"per bet: {d.sum() / max(1, led.bets.sum()):.1f}c · day-level t: **{t:.2f}** · "
         f"winning days: {(d > 0).sum()} / {(led.bets > 0).sum()} with bets", "",
         led.assign(dollars_100=d).drop(columns="pnl_c").to_markdown(index=False), ""]
    open(out, "w").write("\n".join(L))
    print("\n".join(L[:5]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", default="results/forward_ledger.csv")
    ap.add_argument("--out", default="results/FORWARD.md")
    a = ap.parse_args()
    led = pd.read_csv(a.ledger) if os.path.exists(a.ledger) else pd.DataFrame(columns=["day", "events", "bets", "pnl_c"])
    done = set(led.day.astype(str))
    today = datetime.now(timezone.utc).date()
    days = [d.strftime("%Y-%m-%d") for d in pd.date_range(START, today - timedelta(days=1), freq="1D")]
    for day in [d for d in days if d not in done]:
        r = score_day(day)
        print(r, flush=True)
        led = pd.concat([led, pd.DataFrame([r])], ignore_index=True)
        os.makedirs(os.path.dirname(a.ledger) or ".", exist_ok=True)
        led.to_csv(a.ledger, index=False)                          # saved after every day
    if len(led):
        report(led, a.out)


if __name__ == "__main__":
    main()
