"""Paper market-maker for Kalshi hourly BTC/ETH ranges - READ ONLY, never places orders.

Live check of the backtested maker edge with real queues: every few seconds, for the 10 brackets nearest the price,
  model p = volatility model (same as watcher.py) with the live Coinbase price
  sell-YES quote at best ask - 1c   if (quote - p) beats maker fee + MARGIN     (we'd be first in the queue)
  buy-YES  quote at best bid + 1c   if (p - quote) beats maker fee + MARGIN
A quote counts as FILLED only by a real taker trade that arrives > 1 s after we would have posted it, at a price that
would have reached us (taker bought YES at >= our ask, or sold YES at <= our bid).  Max 25 contracts per market and
side per hour.  Fills go to papermaker.jsonl; score them with  python live/paperscore.py
  python live/papermaker.py --hours 24
"""
from __future__ import annotations

import argparse
import json
import math
import os
import time
from datetime import datetime, timedelta, timezone

import requests

from zoneinfo import ZoneInfo

from watcher import VolModel, bracket_prob

ET = ZoneInfo("America/New_York")

K = "https://api.elections.kalshi.com/trade-api/v2"
MON = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
SERIES = {"KXBTC": "BTC-USD", "KXETH": "ETH-USD"}
MARGIN, SIZE, NEAR, MAXM = 8.0, 25, 0.03, 10
HERE = os.path.dirname(os.path.abspath(__file__))
S = requests.Session()


def kget(path, **params):
    for attempt in range(8):
        r = S.get(f"{K}{path}", params=params, timeout=20)
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(min(20, 2 ** attempt))
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError(path)


def maker_fee_c(p, n=SIZE):
    return math.ceil(1.75 * n * p * (1 - p)) / n


def spot(product):
    return float(S.get(f"https://api.exchange.coinbase.com/products/{product}/ticker", timeout=10).json()["price"])


def event(series, close):
    t = close.astimezone(ET)
    return f"{series}-{t:%y}{MON[t.month - 1]}{t:%d%H}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=float, default=24)
    ap.add_argument("--every", type=float, default=3)
    ap.add_argument("--out", default=os.path.join(HERE, "papermaker.jsonl"))
    a = ap.parse_args()
    models = {s: VolModel(p) for s, p in SERIES.items()}
    print("models ready", flush=True)
    stop = time.time() + 3600 * a.hours
    hour, markets, quotes, left = None, {}, {}, {}
    last_trade = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    fills = 0
    while time.time() < stop:
        now = datetime.now(timezone.utc)
        close = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
        try:
            if close != hour:                                     # new hour: learn the last one, load strikes
                if hour is not None:
                    for m in models.values():
                        m.roll()
                hour, quotes, left = close, {}, {}
                markets = {s: kget("/markets", event_ticker=event(s, close), limit=1000).get("markets", []) for s in SERIES}
            secs = (close - now).total_seconds()
            mins_in = 60 - secs / 60
            # 1) fills from real trades since the last poll, against quotes that were live > 1 s before the trade
            got, cur = [], None
            for _ in range(10):                                   # page back to the last trade we saw
                p = {"limit": 1000, "min_ts": int(datetime.fromisoformat(last_trade.replace("Z", "+00:00")).timestamp())}
                if cur:
                    p["cursor"] = cur
                d = kget("/markets/trades", **p)
                got += d.get("trades", [])
                cur = d.get("cursor")
                if not cur or not d.get("trades"):
                    break
            for t in sorted(got, key=lambda x: x["created_time"]):
                if t["created_time"] <= last_trade:
                    continue
                last_trade = t["created_time"]
                tt = datetime.fromisoformat(t["created_time"].replace("Z", "+00:00"))
                y = float(t["yes_price_dollars"])
                for side in ("sell_yes", "buy_yes"):
                    q = quotes.get((t["ticker"], side))
                    if not q or tt.timestamp() < q["t"] + 1:
                        continue
                    hit = (t["taker_side"] == "yes" and y >= q["px"]) if side == "sell_yes" else (t["taker_side"] == "no" and y <= q["px"])
                    rem = left.get((t["ticker"], side), SIZE)
                    if hit and rem > 0:
                        n = min(rem, float(t["count_fp"]))
                        left[(t["ticker"], side)] = rem - n
                        fills += 1
                        rec = {"t": t["created_time"], "ticker": t["ticker"], "we_hold": "no" if side == "sell_yes" else "yes",
                               "yes_px": q["px"], "n": n, "p_yes": q["p"], "mins_in": round(q["mins_in"], 1), "taker_px": y}
                        with open(a.out, "a") as f:
                            f.write(json.dumps(rec) + "\n")
            # 2) refresh quotes from the live books and the model
            new = {}
            for s, prod in SERIES.items():
                px = spot(prod)
                cand = []
                for m in markets.get(s, []):
                    lo, hi = m.get("floor_strike"), m.get("cap_strike")
                    if lo is None or hi is None:
                        continue
                    ref = (lo + hi) / 2
                    if abs(ref / px - 1) <= NEAR:
                        cand.append((abs(ref / px - 1), m))
                cand = [m for _, m in sorted(cand, key=lambda x: x[0])[:MAXM]]
                if not cand:
                    continue
                obs = kget("/markets/orderbooks", tickers=[m["ticker"] for m in cand]).get("orderbooks", [])
                ob = {o["ticker"]: o["orderbook_fp"] for o in obs}
                for m in cand:
                    b = ob.get(m["ticker"], {})
                    yb = max((float(p) for p, q in b.get("yes_dollars") or []), default=None)
                    nb = max((float(p) for p, q in b.get("no_dollars") or []), default=None)
                    ask = round(1 - nb, 2) if nb is not None else None
                    p = bracket_prob(models[s], px, m["floor_strike"], m["cap_strike"], secs)
                    if ask is not None and ask - 0.01 > (yb or 0):
                        qa = round(ask - 0.01, 2)
                        if 100 * (qa - p) - maker_fee_c(qa) > MARGIN:
                            old = quotes.get((m["ticker"], "sell_yes"))
                            new[(m["ticker"], "sell_yes")] = old if old and old["px"] == qa else {"px": qa, "p": p, "t": now.timestamp(), "mins_in": mins_in}
                    if yb is not None and yb + 0.01 < (ask or 1):
                        qb = round(yb + 0.01, 2)
                        if 100 * (p - qb) - maker_fee_c(qb) > MARGIN:
                            old = quotes.get((m["ticker"], "buy_yes"))
                            new[(m["ticker"], "buy_yes")] = old if old and old["px"] == qb else {"px": qb, "p": p, "t": now.timestamp(), "mins_in": mins_in}
            quotes = new
        except Exception as e:
            print(now.strftime("%H:%M:%S"), "error", repr(e)[:150], flush=True)
        if int(time.time()) % 300 < a.every:
            print(now.strftime("%H:%M:%S"), "live quotes", len(quotes), "fills so far", fills, flush=True)
        time.sleep(max(0, a.every - (datetime.now(timezone.utc) - now).total_seconds()))


if __name__ == "__main__":
    main()
