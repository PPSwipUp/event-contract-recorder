"""Could the model's bets actually have been filled?

For every bet the backtest picked (ppc, 5c margin), look at Kalshi's real trade tape for that bracket from the
quote minute to 2 minutes after it.  A bet counts as fillable if someone actually bought the same side at a price
no worse than ours in that window; the contracts they got show how much size was really there.

  python backfill/fillcheck.py --data out
"""
from __future__ import annotations

import argparse
import os
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

from collect import K, get


AFTER = (5, 15, 30, 60)          # seconds after the market opens


def _tape(ticker, t0, t1):
    for base in (f"{K}/markets/trades", f"{K}/historical/trades"):       # recent, then archived trades
        d = get(base, ticker=ticker, min_ts=t0, max_ts=t1, limit=1000)
        if d and d.get("trades"):
            return d["trades"]
    return []


def trades(row):
    """contracts others really bought on our side at our price or better: in the 2 minutes from our quote, and
    (for the speed question) how much of that was still happening 5/15/30/60 s after the market opened"""
    q0 = int(row.quote_ts) - 60                      # candle end = end of the quote minute
    op = pd.Timestamp(row.open_time).timestamp() if isinstance(row.open_time, str) and row.open_time else q0 - 60
    tape = _tape(row.ticker, int(min(op, q0)), q0 + 180)
    got, any_trades, late = 0.0, len(tape), {t: 0.0 for t in AFTER}
    for t in tape:
        px = float(t.get("yes_price_dollars" if row.side == "yes" else "no_price_dollars") or 1)
        if t.get("taker_side") != row.side or px > row.price + 1e-9:
            continue
        n = float(t.get("count_fp") or t.get("count") or 0)
        ts = pd.Timestamp(t["created_time"]).timestamp()
        if q0 <= ts <= q0 + 180:
            got += n
        for s_ in AFTER:
            if ts >= op + s_:
                late[s_] += n
    return got, any_trades, late


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="out")
    a = ap.parse_args()
    P = pd.read_parquet(os.path.join(a.data, "picks.parquet"))
    P = P[P.quote_ts.notna()].reset_index(drop=True)
    if "open_time" not in P:
        P["open_time"] = None
    with ThreadPoolExecutor(4) as ex:
        out = list(ex.map(trades, P.itertuples()))
    P["filled_contracts"] = [o[0] for o in out]
    P["tape_trades"] = [o[1] for o in out]
    for s_ in AFTER:
        P[f"avail_after_{s_}s"] = [o[2][s_] for o in out]
    P.to_parquet(os.path.join(a.data, "picks_filled.parquet"))
    lines = ["", "## Fill check: could the model's bets (5c margin) have been bought?", "",
             "Fillable = someone else really bought the same side at our price or better within 2 minutes.", ""]
    rows = []
    for (series, lag), g in P.groupby(["series", "lag_min"]):
        f = g[g.filled_contracts > 0]
        cap = np.minimum(f.filled_contracts, 100)            # at most what actually traded, 100 max
        rows.append({"series": series, "min_after_open": lag, "bets": len(g), "fillable": len(f),
                     "share_fillable": len(f) / len(g) if len(g) else np.nan,
                     "median_contracts": f.filled_contracts.median() if len(f) else 0,
                     "cents_per_bet_all": g.pnl_c.mean(), "cents_per_bet_fillable": f.pnl_c.mean() if len(f) else np.nan,
                     "dollars_if_filled_at_real_size": float((f.pnl_c * cap).sum() / 100),
                     "bets_with_any_tape": int((g.tape_trades > 0).sum()),
                     **{f"still_fillable_{s_}s": float((g[f"avail_after_{s_}s"] > 0).mean()) for s_ in AFTER}})
    lines += [pd.DataFrame(rows).round(3).to_markdown(index=False), ""]
    text = "\n".join(lines)
    with open(os.path.join(a.data, "RESULTS.md"), "a") as fh:
        fh.write(text)
    print(text)


if __name__ == "__main__":
    main()
