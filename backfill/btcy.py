"""Snapshot: Kalshi's FEE-FREE year-end BTC/ETH price brackets (KXBTCY / KXETHY, settle on the BRTI/ETH reference
average at 00:00 EST 1 Jan 2027) vs the probabilities implied by Deribit options (professional market).

Deribit: every option on the 25 Dec 2026 expiry (mark IV per strike, forward = that expiry's underlying price), the
smile interpolated in log-moneyness, extended to Kalshi's settlement time by adding the extra days of variance at the
at-the-money vol.  P(S_T > K) from the smile-consistent digital: N(d2) - vega * dIV/dK (Black-Scholes).
Bracket probability = P(> floor) - P(> cap).  Kalshi: best bid/ask per bracket; no fee on these series.
Risk-neutral vs real-world drift and the volatility risk premium mean a gap is not automatically mispricing; this is a
screen, and the honest verdict needs daily snapshots tracked to settlement.
  python backfill/btcy.py
"""
from __future__ import annotations

import json
import math
import os
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import requests

import dohfix  # noqa: F401

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "live"))
from arbscan import books, kget  # noqa: E402

SETTLE = datetime(2027, 1, 1, 5, tzinfo=timezone.utc)
OUT = "data_local/btcy_snapshots.jsonl"


def ncdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def deribit_digital(cur):
    S = requests.Session()
    summ = S.get("https://www.deribit.com/api/v2/public/get_book_summary_by_currency",
                 params={"currency": cur, "kind": "option"}, timeout=30).json()["result"]
    rows = [x for x in summ if "-25DEC26-" in x["instrument_name"] and x.get("mark_iv")]
    F = float(np.median([x["underlying_price"] for x in rows]))
    sm = {}
    for x in rows:
        k = float(x["instrument_name"].split("-")[2])
        otm = (x["instrument_name"].endswith("-C") and k >= F) or (x["instrument_name"].endswith("-P") and k < F)
        if otm:
            sm[k] = x["mark_iv"] / 100                                     # out-of-the-money side = cleaner IV
    ks = np.array(sorted(sm))
    iv = np.array([sm[k] for k in ks])
    exp = datetime(2026, 12, 25, 8, tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    T1 = (exp - now).total_seconds() / (365 * 86400)
    dT = (SETTLE - exp).total_seconds() / (365 * 86400)
    atm = float(np.interp(0.0, np.log(ks / F), iv))

    def p_above(K):
        x = math.log(K / F)
        lx = np.log(ks / F)
        sig1 = float(np.interp(x, lx, iv))
        h = 0.01
        slope = (float(np.interp(x + h, lx, iv)) - float(np.interp(x - h, lx, iv))) / (2 * h) / K   # dIV/dK
        var = sig1 ** 2 * T1 + atm ** 2 * dT
        T = T1 + dT
        sig = math.sqrt(var / T)
        d1 = (math.log(F / K) + 0.5 * var) / math.sqrt(var)
        d2 = d1 - math.sqrt(var)
        vega = F * math.sqrt(T) * math.exp(-0.5 * d1 * d1) / math.sqrt(2 * math.pi)
        return min(1.0, max(0.0, ncdf(d2) - vega * slope * (T1 / T) * (sig1 / sig)))
    return F, p_above


def main():
    rows = []
    for series, cur in (("KXBTCY", "BTC"), ("KXETHY", "ETH")):
        F, p_above = deribit_digital(cur)
        ms = kget("/markets", series_ticker=series, status="open", limit=200).get("markets", [])
        Q = books([m["ticker"] for m in ms])
        for m in ms:
            lo, hi = m.get("floor_strike"), m.get("cap_strike")
            p = (p_above(lo) if lo else 1.0) - (p_above(hi) if hi else 0.0)
            ya, ys, na, ns = Q.get(m["ticker"], (None, 0, None, 0))
            bid = None if na is None else round(1 - na, 4)
            rows.append({"t": datetime.now(timezone.utc).isoformat(timespec="seconds"), "series": series, "forward": round(F, 2),
                         "ticker": m["ticker"], "lo": lo, "hi": hi, "deribit_p": round(p, 4), "k_bid": bid, "k_ask": ya,
                         "ask_size": ys, "bid_size": ns,
                         "edge_yes_c": None if ya is None else round(100 * (p - ya), 2),
                         "edge_no_c": None if bid is None else round(100 * (bid - p), 2)})
    with open(OUT, "a") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    D = pd.DataFrame(rows)
    print(D[["series", "lo", "hi", "deribit_p", "k_bid", "k_ask", "edge_yes_c", "edge_no_c", "ask_size", "bid_size"]].to_string(index=False))


if __name__ == "__main__":
    main()
