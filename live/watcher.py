"""Live, read-only signal watcher for Kalshi hourly BTC range markets.  It NEVER places orders.

Before each hourly event opens, the bracket strikes are already known: the volatility model's forecast for the
coming hour is ready, so at the open the only work left is  P(bracket) = F(ln(cap/S)/sig) - F(ln(floor/S)/sig)
with the live BTC price S - microseconds.  Two live connections:
  Coinbase WebSocket  BTC-USD ticker (the live price)
  Kalshi WebSocket    market_lifecycle_v2 (markets opening) + orderbook_delta (every change to the book)
Whenever the best ask for YES (or NO) is below the model's price by more than fee + margin, a signal is printed
and appended to signals.jsonl, with how many milliseconds after the market opened it was seen.

Needs a Kalshi API key (read access is enough):
  export KALSHI_KEY_ID=...                     # the key's id
  export KALSHI_KEY_FILE=~/.kalshi/key.pem     # the private key file Kalshi gave you (keep it private)
  python live/watcher.py [--series KXBTC] [--margin 5]
Run it on a server in AWS us-east-2 (Ohio), where Kalshi's exchange is, for the lowest latency.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import math
import os
import time
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import requests
import websockets
from ppc import Forecaster

REST = "https://api.elections.kalshi.com/trade-api/v2"
WS = "wss://api.elections.kalshi.com/trade-api/ws/v2"
CB_WS = "wss://ws-feed.exchange.coinbase.com"
PRODUCT = {"KXBTC": "BTC-USD", "KXETH": "ETH-USD"}


# ------------------------------------------------------------------ volatility model
class VolModel:
    """ppc forecast of next-hour realised vol from 1-minute Coinbase prices (same recipe as the backtest)"""

    def __init__(self, product, days=120):
        self.product = product
        m = self._minutes(datetime.now(timezone.utc) - timedelta(days=days), datetime.now(timezone.utc))
        W = self._hours(m)
        self.f = Forecaster(horizons=(1,), season=[24, 168], transform=None, fast=True)
        P = self.f.fit_predict(pd.DataFrame({"y": np.log(W.rv.clip(lower=1e-6)).values}), target="y")
        sig = np.exp(pd.Series(P.auto_h1.values, index=W.index).shift(1))
        ok = sig.notna() & (sig > 0)
        self.k = float(np.median(np.abs(W.ret[ok]) / sig[ok]))
        self.z = np.sort((W.ret[ok] / (self.k * sig[ok])).values)   # empirical shape of standardised moves
        self.next_sig = float(np.exp(P.auto_h1.values[-1]))          # forecast for the hour after the last full one
        self.last_hour = W.index[-1]

    def _minutes(self, start, end):
        out, t = [], start
        while t < end:
            u = min(end, t + timedelta(minutes=300))
            r = requests.get(f"https://api.exchange.coinbase.com/products/{self.product}/candles", timeout=30,
                             params={"granularity": 60, "start": t.isoformat(), "end": u.isoformat()})
            if r.status_code == 429:
                time.sleep(1)
                continue
            out += r.json()
            t = u
            time.sleep(0.12)
        d = pd.DataFrame(out, columns=["ts", "l", "h", "o", "c", "v"]).drop_duplicates("ts").sort_values("ts")
        return pd.Series(np.log(d.c.values), index=pd.to_datetime(d.ts, unit="s", utc=True))

    @staticmethod
    def _hours(s):
        s = s.reindex(pd.date_range(s.index[0], s.index[-1], freq="1min", tz="UTC")).ffill()
        g = s.index.floor("1h")
        W = pd.DataFrame({"open": s.groupby(g).first(), "close": s.groupby(g).last(),
                          "rv": np.sqrt((s.diff() ** 2).groupby(g).sum()), "n": s.groupby(g).count()})
        W = W[W.n >= 55]                                            # completed hours only
        W["ret"] = W.close - W.open
        return W

    def roll(self):
        """after each hour completes: learn it and forecast the next one"""
        now = datetime.now(timezone.utc)
        m = self._minutes(self.last_hour.to_pydatetime(), now)
        W = self._hours(m)
        W = W[W.index > self.last_hour]
        if len(W):
            P = self.f.update(pd.DataFrame({"y": np.log(W.rv.clip(lower=1e-6)).values}))
            self.next_sig = float(np.exp(P.auto_h1.values[-1]))
            self.last_hour = W.index[-1]

    def sigma(self, seconds_left):
        return self.k * self.next_sig * math.sqrt(max(seconds_left, 60) / 3600)

    def cdf(self, x):
        return np.searchsorted(self.z, x) / len(self.z)


def bracket_prob(model, spot, floor, cap, seconds_left):
    sig = model.sigma(seconds_left)
    hi = 1.0 if cap is None else model.cdf(math.log(cap / spot) / sig)
    lo = 0.0 if floor is None else model.cdf(math.log(floor / spot) / sig)
    return max(0.0, hi - lo)


def fee_c(p, n=100):
    return math.ceil(7 * n * p * (1 - p)) / n                        # Kalshi taker fee, cents per contract


# ------------------------------------------------------------------ Kalshi auth + books
def auth_headers(path="/trade-api/ws/v2", method="GET"):
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    key = serialization.load_pem_private_key(open(os.path.expanduser(os.environ["KALSHI_KEY_FILE"]), "rb").read(), None)
    ts = str(int(time.time() * 1000))
    sig = key.sign((ts + method + path).encode(), padding.PSS(mgf=padding.MGF1(hashes.SHA256()),
                                                              salt_length=padding.PSS.DIGEST_LENGTH), hashes.SHA256())
    return {"KALSHI-ACCESS-KEY": os.environ["KALSHI_KEY_ID"], "KALSHI-ACCESS-SIGNATURE": base64.b64encode(sig).decode(),
            "KALSHI-ACCESS-TIMESTAMP": ts}


def _px(v):
    """price in dollars from either cents (int) or a dollar string"""
    return float(v) / 100 if isinstance(v, int) else float(v)


class Book:
    """yes and no bids for one market; the YES ask is 1 - best NO bid (and vice versa)"""

    def __init__(self):
        self.yes, self.no = {}, {}

    def snapshot(self, m):
        for side in ("yes", "no"):
            lv = m.get(f"{side}_dollars") or m.get(side) or []
            setattr(self, side, {_px(p): float(q) for p, q in lv})

    def delta(self, m):
        side = getattr(self, m["side"])
        p = _px(m.get("price_dollars", m.get("price")))
        side[p] = side.get(p, 0.0) + float(m.get("delta_fp", m.get("delta")))
        if side[p] <= 0:
            del side[p]

    def best(self):
        """(yes ask, size at it), (no ask, size at it)"""
        by = max(self.yes) if self.yes else None
        bn = max(self.no) if self.no else None
        return ((1 - bn, self.no[bn]) if bn is not None else (None, 0)), ((1 - by, self.yes[by]) if by is not None else (None, 0))


# ------------------------------------------------------------------ the watcher
class Watcher:
    def __init__(self, series, margin, out):
        self.series, self.margin, self.out = series, margin, out
        self.spot = None
        self.markets = {}              # ticker -> dict(floor, cap, close_ts, open_ts)
        self.books = {}
        self.fired = set()
        print(f"training the volatility model on {PRODUCT[series]} ...", flush=True)
        self.model = VolModel(PRODUCT[series])
        print(f"ready: next-hour vol {self.model.next_sig:.5f}", flush=True)

    def load_upcoming(self):
        """strikes of every open or soon-to-open market in the series (REST, before the open)"""
        n = 0
        for status in ("unopened", "open"):
            cursor = None
            while True:
                p = {"series_ticker": self.series, "status": status, "limit": 1000}
                if cursor:
                    p["cursor"] = cursor
                d = requests.get(f"{REST}/markets", params=p, timeout=30).json()
                for m in d.get("markets", []):
                    self.markets[m["ticker"]] = {
                        "floor": m.get("floor_strike"), "cap": m.get("cap_strike"),
                        "close_ts": pd.Timestamp(m["close_time"]).timestamp(), "open_ts": pd.Timestamp(m["open_time"]).timestamp()}
                    n += 1
                cursor = d.get("cursor")
                if not cursor or not d.get("markets"):
                    break
        return n

    def check(self, ticker, recv_ms):
        m, b = self.markets.get(ticker), self.books.get(ticker)
        if not m or not b or self.spot is None:
            return
        left = m["close_ts"] - time.time()
        if left <= 0:
            return
        p = bracket_prob(self.model, self.spot, m["floor"], m["cap"], left)
        (ya, ys), (na, ns) = b.best()
        for side, ask, size, fair in (("yes", ya, ys, p), ("no", na, ns, 1 - p)):
            if ask is None or not 0 < ask < 1:
                continue
            edge = 100 * (fair - ask) - fee_c(ask)
            if edge > self.margin and (ticker, side, ask) not in self.fired:
                self.fired.add((ticker, side, ask))
                sig = {"t": datetime.now(timezone.utc).isoformat(timespec="milliseconds"), "ticker": ticker, "side": side,
                       "ask": ask, "size": size, "model": round(fair, 4), "edge_c": round(edge, 2), "spot": self.spot,
                       "ms_after_open": round(recv_ms - 1000 * m["open_ts"]), "compute_ms": round(time.time() * 1000 - recv_ms, 3)}
                print("SIGNAL", json.dumps(sig), flush=True)
                with open(self.out, "a") as fh:
                    fh.write(json.dumps(sig) + "\n")

    async def coinbase(self):
        while True:
            try:
                async with websockets.connect(CB_WS, ping_interval=20) as ws:
                    await ws.send(json.dumps({"type": "subscribe", "product_ids": [PRODUCT[self.series]], "channels": ["ticker"]}))
                    async for raw in ws:
                        msg = json.loads(raw)
                        if msg.get("type") == "ticker":
                            self.spot = float(msg["price"])
            except Exception as err:
                print("coinbase reconnect:", err, flush=True)
                await asyncio.sleep(1)

    async def kalshi(self):
        while True:
            try:
                n = self.load_upcoming()
                async with websockets.connect(WS, additional_headers=auth_headers(), ping_interval=10) as ws:
                    await ws.send(json.dumps({"id": 1, "cmd": "subscribe", "params": {"channels": ["market_lifecycle_v2"]}}))
                    await ws.send(json.dumps({"id": 2, "cmd": "subscribe", "params": {
                        "channels": ["orderbook_delta"], "market_tickers": list(self.markets)}}))
                    print(f"kalshi: watching {n} markets", flush=True)
                    nid = 3
                    async for raw in ws:
                        recv_ms = time.time() * 1000
                        msg = json.loads(raw)
                        typ, body = msg.get("type"), msg.get("msg", {})
                        t = body.get("market_ticker")
                        if typ == "orderbook_snapshot":
                            self.books.setdefault(t, Book()).snapshot(body)
                            self.check(t, recv_ms)
                        elif typ == "orderbook_delta":
                            self.books.setdefault(t, Book()).delta(body)
                            self.check(t, recv_ms)
                        elif typ == "market_lifecycle_v2" and t and t.startswith(self.series + "-") and t not in self.markets:
                            # a new market was created: fetch its strikes and start watching its book right away
                            self.load_upcoming()
                            await ws.send(json.dumps({"id": nid, "cmd": "subscribe", "params": {
                                "channels": ["orderbook_delta"], "market_tickers": [t]}}))
                            nid += 1
            except Exception as err:
                print("kalshi reconnect:", err, flush=True)
                await asyncio.sleep(2)

    async def hourly(self):
        while True:
            now = time.time()
            await asyncio.sleep(3600 - now % 3600 + 20)                 # 20 s after each hour
            await asyncio.to_thread(self.model.roll)
            done = [t for t, m in self.markets.items() if m["close_ts"] < time.time()]
            for t in done:
                self.markets.pop(t, None)
                self.books.pop(t, None)
            print(f"{datetime.now(timezone.utc):%H:%M} next-hour vol {self.model.next_sig:.5f}; watching {len(self.markets)}", flush=True)

    async def run(self):
        await asyncio.gather(self.coinbase(), self.kalshi(), self.hourly())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", default="KXBTC", choices=list(PRODUCT))
    ap.add_argument("--margin", type=float, default=5.0, help="cents of edge after fees before signalling")
    ap.add_argument("--out", default="signals.jsonl")
    a = ap.parse_args()
    asyncio.run(Watcher(a.series, a.margin, a.out).run())


if __name__ == "__main__":
    main()
