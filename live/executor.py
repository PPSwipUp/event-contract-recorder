"""Order executor for the range bot's signals.  DRY RUN BY DEFAULT: it only logs the orders it would send.

Follows a signals file written by live/watcher.py (one JSON per line: ticker, side, ask, size, edge_c, t) and turns
each fresh signal into ONE immediate-or-cancel limit order at the signalled ask (never worse), via Kalshi's V2
order endpoint.  Risk limits, all checked before every order:
  --max-contracts   contracts per order (default 100, the size the forward test assumes)
  --per-event       orders per hourly event (default 3)
  --daily-budget    $ at risk per UTC day = sum of (price + fee) x filled contracts (default $150); counts fills only
  --max-age         ignore signals older than this many seconds (default 2)
  one order per (ticker, side): no doubling up
  kill switch: if the file live/STOP exists, nothing is sent (touch live/STOP to halt instantly)
Daily spend is persisted in executor_state.json so a restart can't reset the budget.

Live mode needs ALL of:  --live  and  KALSHI_KEY_ID + KALSHI_KEY_FILE in the environment (a key with trade access).
  python live/executor.py --signals signals.jsonl                 # dry run (default)
  python live/executor.py --signals signals.jsonl --live          # sends real orders - you run this, not Claude
"""
from __future__ import annotations

import argparse
import json
import math
import os
import time
import uuid
from datetime import datetime, timezone

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
REST = "https://api.elections.kalshi.com/trade-api/v2"
ORDER_PATH = "/trade-api/v2/portfolio/events/orders"


def fee_c(p, n):
    return math.ceil(7 * n * p * (1 - p)) / n


def order_body(sig, count):
    """V2 order: side 'bid' = long YES, 'ask' = long NO; price is always on the YES scale"""
    if sig["side"] == "yes":
        side, price = "bid", sig["ask"]
    else:
        side, price = "ask", 1 - sig["ask"]                      # paying NO at a  ==  selling YES at 1 - a
    return {"ticker": sig["ticker"], "client_order_id": str(uuid.uuid4()), "side": side, "count": f"{count:.2f}",
            "price": f"{price:.4f}", "time_in_force": "immediate_or_cancel", "self_trade_prevention_type": "taker_at_cross",
            "cancel_order_on_pause": True}


class Executor:
    def __init__(self, a):
        self.a = a
        self.state_path = os.path.join(HERE, "executor_state.json")
        self.log_path = os.path.join(HERE, "executor.jsonl")
        try:
            self.state = json.load(open(self.state_path))
        except (OSError, ValueError):
            self.state = {}
        self.done, self.per_event = set(), {}

    def day(self):
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def spent(self):
        return self.state.get(self.day(), 0.0)

    def log(self, rec):
        rec["logged"] = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
        print(json.dumps(rec), flush=True)
        with open(self.log_path, "a") as f:
            f.write(json.dumps(rec) + "\n")

    def refuse(self, sig):
        """reason not to trade this signal, or None"""
        if os.path.exists(os.path.join(HERE, "STOP")):
            return "kill switch (live/STOP exists)"
        age = time.time() - datetime.fromisoformat(sig["t"]).timestamp()
        if age > self.a.max_age:
            return f"stale signal ({age:.1f}s)"
        if (sig["ticker"], sig["side"]) in self.done:
            return "already traded this market/side"
        event = sig["ticker"].rsplit("-", 1)[0]
        if self.per_event.get(event, 0) >= self.a.per_event:
            return "per-event limit"
        if not 0 < sig["ask"] < 1:
            return "bad price"
        return None

    def handle(self, sig):
        why = self.refuse(sig)
        if why:
            self.log({"signal": sig, "action": "skip", "why": why})
            return
        count = int(min(self.a.max_contracts, math.floor(sig.get("size") or 0)))
        unit = sig["ask"] + fee_c(sig["ask"], max(count, 1)) / 100
        room = self.a.daily_budget - self.spent()
        count = min(count, int(room // unit)) if unit > 0 else 0
        if count < 1:
            self.log({"signal": sig, "action": "skip", "why": f"daily budget (spent ${self.spent():.2f})"})
            return
        body = order_body(sig, count)
        event = sig["ticker"].rsplit("-", 1)[0]
        self.done.add((sig["ticker"], sig["side"]))
        self.per_event[event] = self.per_event.get(event, 0) + 1
        if not self.a.live:
            filled = count                                           # dry run assumes a full fill for budgeting
            self.log({"signal": sig, "action": "DRY-RUN order", "body": body})
        else:
            from watcher import auth_headers                         # same RSA-PSS signing as the watcher
            r = requests.post(REST + ORDER_PATH.split("/trade-api/v2")[1], json=body, timeout=10,
                              headers=auth_headers(ORDER_PATH, "POST"))
            resp = r.json() if r.content else {}
            filled = float(resp.get("fill_count") or 0) if r.status_code in (200, 201) else 0
            self.log({"signal": sig, "action": "LIVE order", "body": body, "status": r.status_code, "response": resp})
        self.state[self.day()] = self.spent() + filled * unit
        json.dump(self.state, open(self.state_path, "w"))

    def follow(self):
        path = self.a.signals
        while not os.path.exists(path):
            time.sleep(0.5)
        with open(path) as f:
            f.seek(0, os.SEEK_END)                                   # only signals that arrive from now on
            while True:
                line = f.readline()
                if not line:
                    time.sleep(0.05)
                    continue
                try:
                    self.handle(json.loads(line))
                except Exception as err:                             # one bad line must not kill the executor
                    self.log({"action": "error", "line": line.strip()[:300], "error": repr(err)[:300]})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--signals", default="signals.jsonl")
    ap.add_argument("--live", action="store_true", help="send real orders (needs KALSHI_KEY_ID / KALSHI_KEY_FILE)")
    ap.add_argument("--max-contracts", type=int, default=100)
    ap.add_argument("--per-event", type=int, default=3)
    ap.add_argument("--daily-budget", type=float, default=150.0)
    ap.add_argument("--max-age", type=float, default=2.0)
    a = ap.parse_args()
    if a.live:
        missing = [k for k in ("KALSHI_KEY_ID", "KALSHI_KEY_FILE") if not os.environ.get(k)]
        if missing:
            raise SystemExit(f"--live needs {', '.join(missing)} in the environment")
        print("*** LIVE MODE: real orders will be sent.  touch live/STOP to halt. ***", flush=True)
    else:
        print("dry run: orders are only logged to live/executor.jsonl", flush=True)
    Executor(a).follow()


if __name__ == "__main__":
    main()
