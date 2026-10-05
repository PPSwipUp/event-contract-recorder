"""Kalshi S&P 500 daily ranges (KXINX) vs same-day SPX options (SPXW, PM-settled on the official close) - READ ONLY.

A Kalshi range [L, U) pays $1 if the close lands inside.  With 5-point SPX strikes it is boxed in by two call-spread
packages (per $1 of payoff; one SPX spread 5 wide = $500, so 1 package unit = 500 Kalshi contracts):
  super = CS(L-5, L) - CS(U, U+5)   pays >= the range in every outcome
  sub   = CS(L, L+5) - CS(U-5, U)   pays <= the range in every outcome
Locked-in trades (every leg at the price you'd actually pay: Kalshi ask/bid, option bid/ask, all fees):
  BUY_YES:  Kalshi YES at ask  + sell `sub` at its bid      profit if sell price > YES cost
  BUY_NO:   Kalshi NO at 1-bid + buy `super` at its ask     profit if the two cost < $1
Also logs the options' mid-price probability next to Kalshi's mid (relative value, not riskless).

Option quotes: Cboe's free delayed chain (bid/ask/size, ~15 min old).  Kalshi prices are taken from its 1-minute
candles at the SAME timestamp, so both sides describe the same moment.  Never places orders.
  python live/spxscan.py --every 300 --until 20:15          # snapshot every 5 min until 20:15 UTC
"""
from __future__ import annotations

import argparse
import json
import math
import os
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import requests

K = "https://api.elections.kalshi.com/trade-api/v2"
ET = ZoneInfo("America/New_York")
MON = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
CBOE = "https://cdn.cboe.com/api/global/delayed_quotes/options/_SPX.json"
OPT_FEE_C = 1.0                       # $ per option contract (broker index fee + exchange/regulatory, rounded up)
UNIT = 500                            # Kalshi contracts per 1-lot of 5-wide SPX spreads
HERE = os.path.dirname(os.path.abspath(__file__))


def kget(path, **params):
    """Kalshi GET with back-off on rate limits / server errors"""
    for attempt in range(10):
        r = requests.get(f"{K}{path}", params=params, timeout=30)
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(min(30, 2 ** attempt))
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError(f"gave up on {path}")


def kalshi_fee_c(p):                  # taker fee per contract on a 500-lot, cents (0.07 schedule; conservative)
    return math.ceil(7 * UNIT * p * (1 - p)) / UNIT


def cboe_calls(day):
    """({strike: (bid, ask, bid_size, ask_size)}, quote time UTC) for SPXW calls expiring `day`"""
    d = requests.get(CBOE, headers={"User-Agent": "Mozilla/5.0"}, timeout=60).json()
    pre = f"SPXW{day:%y%m%d}C"
    out = {}
    for o in d["data"]["options"]:
        if o["option"].startswith(pre):
            out[int(o["option"][len(pre):]) / 1000] = (o["bid"], o["ask"], o["bid_size"], o["ask_size"])
    return out, datetime.fromisoformat(d["timestamp"]).replace(tzinfo=timezone.utc)


def kalshi_at(ev, ts):
    """{ticker: (yes_bid, yes_ask)} from Kalshi 1-minute candles at the option quote time (same moment)"""
    t = int(ts.timestamp()) // 60 * 60
    d = kget(f"/series/KXINX/events/{ev}/candlesticks", period_interval=1, start_ts=t - 1800, end_ts=t)
    out = {}
    for tk, cs in zip(d.get("market_tickers", []), d.get("market_candlesticks", [])):
        cs = [x for x in cs if x["end_period_ts"] <= t and x["yes_ask"].get("close_dollars") is not None]
        if cs:
            x = cs[-1]
            out[tk] = (float(x["yes_bid"]["close_dollars"] or 0), float(x["yes_ask"]["close_dollars"] or 1))
    return out


def snapshot(day):
    ev = f"KXINX-{day:%y}{MON[day.month - 1]}{day:%d}H1600"
    ms = kget("/markets", event_ticker=ev, limit=200)["markets"]
    C, qt = cboe_calls(day)
    KQ = kalshi_at(ev, qt)

    def leg(k, side):                                                # option price you'd trade at; None if no market
        b, a = C.get(k, (None, None, 0, 0))[:2]
        return (b if side == "sell" else a) if (b and a) else None

    def mid(k):
        b, a = C.get(k, (None, None, 0, 0))[:2]
        return (b + a) / 2 if (b and a) else None

    def above(k):                                                    # P(close >= k) from mids, centred difference
        m1, m2 = mid(k - 5), mid(k + 5)
        return None if m1 is None or m2 is None else (m1 - m2) / 10

    rows = []
    for m in ms:
        L = round(m["floor_strike"] + 1e-4, 2) if m.get("floor_strike") is not None else None
        U = round(m["cap_strike"] + 1e-4, 2) if m.get("cap_strike") is not None else None
        if m["ticker"] not in KQ:
            continue
        yb, ya = KQ[m["ticker"]]
        try:
            sub = ((leg(L, "sell") - leg(L + 5, "buy")) if L is not None else 5.0) \
                - ((leg(U - 5, "buy") - leg(U, "sell")) if U is not None else 0.0)
            sup = ((leg(L - 5, "buy") - leg(L, "sell")) if L is not None else 5.0) \
                - ((leg(U, "sell") - leg(U + 5, "buy")) if U is not None else 0.0)
        except TypeError:
            sub = sup = None
        opt_fee = OPT_FEE_C * 2 * ((L is not None) + (U is not None)) / UNIT * 100   # cents per $1 payoff
        r = {"quote_time": qt.isoformat(), "ticker": m["ticker"], "L": L, "U": U, "yes_bid": yb, "yes_ask": ya}
        if sub is not None and 0 < ya < 1:
            r["buy_yes_edge_c"] = round(100 * sub / 5 - 100 * ya - kalshi_fee_c(ya) - opt_fee, 2)
        if sup is not None and 0 < yb < 1:
            r["buy_no_edge_c"] = round(100 * yb - kalshi_fee_c(1 - yb) - 100 * sup / 5 - opt_fee, 2)
        pa, pb = (above(L) if L is not None else 1.0), (above(U) if U is not None else 0.0)
        if pa is not None and pb is not None:
            r["options_prob"] = round(pa - pb, 4)
            r["kalshi_mid"] = round((yb + ya) / 2, 4) if 0 < yb and ya < 1 else None
        rows.append(r)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--every", type=int, default=0, help="seconds between snapshots (0 = once)")
    ap.add_argument("--until", default="20:15", help="UTC time to stop")
    ap.add_argument("--day", default=None, help="settlement date YYYY-MM-DD (default: today ET)")
    ap.add_argument("--out", default=os.path.join(HERE, "spxscan.jsonl"))
    a = ap.parse_args()
    while True:
        day = datetime.fromisoformat(a.day) if a.day else datetime.now(ET)
        try:
            rows = snapshot(day)
            with open(a.out, "a") as f:
                for r in rows:
                    f.write(json.dumps(r) + "\n")
            e = [(max(r.get("buy_yes_edge_c", -99), r.get("buy_no_edge_c", -99)), r["ticker"]) for r in rows]
            print(datetime.now(timezone.utc).strftime("%H:%M:%S"), "quotes at", rows[0]["quote_time"] if rows else "-",
                  len(rows), "brackets; best locked edge", max(e) if e else None, flush=True)
        except Exception as ex:                                      # keep logging through API hiccups
            print("error", repr(ex)[:200], flush=True)
        if not a.every or datetime.now(timezone.utc).strftime("%H:%M") >= a.until:
            return
        time.sleep(a.every)


if __name__ == "__main__":
    main()
