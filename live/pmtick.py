"""Tick-level, read-only recorder of Polymarket's public market stream for the paper-LP markets.

Writes every message (book snapshots, price_change level updates, last_trade_price, tick changes) with the local
receive time in ms to live/pmtick/YYYY-MM-DD.jsonl (one line per event, raw payload kept).  Reconnects with back-off,
so the school Wi-Fi curfew (00:00-06:30) just leaves a gap.  Purpose: replay liquidity-provider quoting at 3 s, 1 s,
0.5 s and 0.1 s reaction times against real order flow to measure fill loss versus speed.
  python live/pmtick.py --hours 168
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import ssl
import time
from datetime import datetime, timezone

import websockets

HERE = os.path.dirname(os.path.abspath(__file__))
WS = "wss://ws-subscriptions-clob.polymarket.com/ws/market"


def tokens():
    st = json.load(open(os.path.join(HERE, "pmlp_state.json")))
    return [m["token"] for m in st["markets"]]


async def record(stop, out_dir):
    ctx = ssl.create_default_context(cafile=os.environ.get("SSL_CERT_FILE")) if os.environ.get("SSL_CERT_FILE") else None
    toks, wait, n = tokens(), 1, 0
    while time.time() < stop:
        try:
            async with websockets.connect(WS, ssl=ctx, ping_interval=10, max_size=2 ** 24) as ws:
                await ws.send(json.dumps({"assets_ids": toks, "type": "market"}))
                print(datetime.now(timezone.utc).strftime("%H:%M:%S"), "connected,", len(toks), "markets", flush=True)
                wait = 1
                while time.time() < stop:
                    raw = await asyncio.wait_for(ws.recv(), 120)
                    rx = int(time.time() * 1000)
                    msgs = json.loads(raw)
                    path = os.path.join(out_dir, datetime.now(timezone.utc).strftime("%Y-%m-%d") + ".jsonl")
                    with open(path, "a") as f:
                        for m in msgs if isinstance(msgs, list) else [msgs]:
                            f.write(json.dumps({"rx": rx, **m}) + "\n")
                            n += 1
                    if n and n % 50000 < (len(msgs) if isinstance(msgs, list) else 1):
                        print(datetime.now(timezone.utc).strftime("%H:%M"), "events", n, flush=True)
        except Exception as err:
            print(datetime.now(timezone.utc).strftime("%H:%M:%S"), "reconnect in", wait, "s:", repr(err)[:120], flush=True)
            await asyncio.sleep(wait)
            wait = min(300, wait * 2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=float, default=168)
    a = ap.parse_args()
    out = os.path.join(HERE, "pmtick")
    os.makedirs(out, exist_ok=True)
    asyncio.run(record(time.time() + 3600 * a.hours, out))


if __name__ == "__main__":
    main()
