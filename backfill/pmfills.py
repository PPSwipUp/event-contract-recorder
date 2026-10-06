"""Fill-by-fill analysis of the Polymarket paper LP (live/pmlp<tag>_fills.jsonl).

Per fill: mark-out per share vs the market's YES price at +5 min / +1 h / +24 h and at settlement
(buy_yes: later price - our price; sell_yes: our price - later price; positive = good for us), and the market's
trailing-24h jumpiness just before the fill (mean |hourly change|, the "day" predictor of results/PM_JUMP.md)
compared with the frozen calm threshold.  Fills made before per-fill logging (2026-10-05 05:37 UTC) have no
timestamps: they are reconstructed per market from the saved state (buys/sells, net position, cash, mark now).
  python backfill/pmfills.py --tag _tight
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "live"))
import dohfix  # noqa: F401,E402
from pmlp import CLOB, GAMMA, jget, jumpiness  # noqa: E402,F401

LIVE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "live")
THR = float(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "data_local", "pmjump", "calm_threshold.txt")).read())
HORIZONS = {"5m": 300, "1h": 3600, "24h": 86400}


def history(token, a, b, fidelity):
    h = (jget(f"{CLOB}/prices-history", market=token, startTs=a, endTs=b, fidelity=fidelity) or {}).get("history", [])
    return pd.Series({x["t"]: x["p"] for x in h}).sort_index()


def price_at(token, ts):
    s = history(token, ts - 600, ts + 600, 1)
    s = s[s.index <= ts]
    return float(s.iloc[-1]) if len(s) else None


def jump_before(token, ts):
    s = history(token, ts - 25 * 3600, ts, 60)
    p = s.values[-25:]
    return float(abs(pd.Series(p).diff()).iloc[1:].mean()) if len(p) >= 7 else None


def settlement(cid):
    m = (jget(f"{GAMMA}/markets", condition_ids=cid) or [{}])[0]
    if not m.get("closed"):
        return None
    yes = float(json.loads(m["outcomePrices"])[0])
    return yes if yes in (0.0, 1.0) else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="_tight")
    a = ap.parse_args()
    out = [f"# Paper LP fills: pmlp{a.tag}", ""]
    st = json.load(open(os.path.join(LIVE, f"pmlp{a.tag}_state.json")))
    size = None
    fp = os.path.join(LIVE, f"pmlp{a.tag}_fills.jsonl")
    F = pd.read_json(fp, lines=True, dtype={"token": str, "cid": str}) if os.path.exists(fp) and os.path.getsize(fp) else pd.DataFrame()
    now = int(time.time())
    if len(F):
        size = F["size"].iloc[0]
        rows = []
        for f in F.itertuples():
            sgn = 1 if f.side == "buy_yes" else -1
            r = {"time_utc": pd.to_datetime(f.trade_ts, unit="s").strftime("%m-%d %H:%M"), "market": f.question[:40],
                 "side": f.side, "price": f.price, "mid_before": f.mid}
            for k, h in HORIZONS.items():
                px = price_at(f.token, f.trade_ts + h) if f.trade_ts + h <= now else None
                r[f"mo_{k}_c"] = round(100 * sgn * (px - f.price), 2) if px is not None else None
            stl = settlement(f.cid)
            r["mo_settle_c"] = round(100 * sgn * (stl - f.price), 2) if stl is not None else None
            j = jump_before(f.token, f.trade_ts)
            r["jump24h_before"] = round(j, 4) if j is not None else None
            r["jumpy(top decile)"] = j is not None and j >= THR
            rows.append(r)
        R = pd.DataFrame(rows)
        out += [f"## Logged fills ({len(R)})", "", R.to_markdown(index=False), "",
                "Mean mark-out (cents/share, + = good for us): " +
                ", ".join(f"{c} {R[c].mean():+.2f} (n {R[c].notna().sum()})" for c in R.columns if c.startswith("mo_")), ""]
    # markets with fills from before per-fill logging: reconstruct from state
    rows = []
    for m in st["markets"]:
        p = st["pos"][m["cid"]]
        n = p["fills"] - (int((F.cid == m["cid"]).sum()) if len(F) else 0)
        if n <= 0:
            continue
        sz = size or (500 if "tight" in a.tag else 200)
        buys = (n + p["inv"] / sz) / 2
        avg = abs(p["cash"] / p["inv"]) if p["inv"] and buys in (0, n) else None
        stl = settlement(m["cid"])
        mark = stl if stl is not None else p["mid"]
        rows.append({"market": m["question"][:45], "fills": n, "buys": int(buys), "sells": int(n - buys),
                     "net_shares": p["inv"], "avg_price(one-way only)": round(avg, 3) if avg else None,
                     "mark_now": mark, "settled": stl is not None, "pnl_$": round(p["cash"] + p["inv"] * mark, 2),
                     "jump24h_now": round(jumpiness(m["token"]) or 0, 4), "mid_in_0.10-0.90": 0.10 <= (p["mid"] or 0) <= 0.90})
    if rows:
        Q = pd.DataFrame(rows)
        out += ["## Fills before per-fill logging (reconstructed per market from state; no timestamps)", "",
                Q.to_markdown(index=False), "", f"Total marked P&L of these positions: ${Q['pnl_$'].sum():+.2f}", ""]
    open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results", f"PM_FILLS{a.tag.upper()}.md"), "w").write("\n".join(out))
    print("\n".join(out))


if __name__ == "__main__":
    main()
