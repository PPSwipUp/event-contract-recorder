"""Polymarket "What price will Bitcoin/Ethereum hit <week|month>?" markets: strikes, direction, window, result, and
every taker trade (data-api).  Read-only public endpoints.
  python backfill/pmtouchdata.py
"""
from __future__ import annotations

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import requests

import dohfix  # noqa: F401

OUT = "data_local/pmtouch"
SERIES = ["bitcoin-hit-price-weekly", "ethereum-hit-price-weekly", "bitcoin-hit-price-monthly", "ethereum-hit-price-monthly"]
S = requests.Session()


def jget(url, **params):
    for attempt in range(8):
        try:
            r = S.get(url, params=params, timeout=30)
            if r.status_code == 200:
                return r.json()
        except requests.RequestException:
            pass
        time.sleep(2 ** attempt)
    raise RuntimeError(url)


def strike(q):
    x = q.split("$")[1].split(" ")[0].replace(",", "").rstrip("?").upper()
    return float(x[:-1]) * 1000 if x.endswith("K") else float(x[:-1]) * 1e6 if x.endswith("M") else float(x)


def markets():
    rows = []
    for ser in SERIES:
        off = 0
        while True:
            evs = jget("https://gamma-api.polymarket.com/events", series_slug=ser, closed="true", limit=100, offset=off)
            if not evs:
                break
            off += 100
            for e in evs:
                if "before" in e["slug"]:                      # yearly event filed under the monthly series
                    continue
                for m in e["markets"]:
                    q = m["question"]
                    if "$" not in q:
                        continue
                    res = json.loads(m.get("outcomePrices") or "[]")
                    rows.append({"series": ser, "event": e["slug"], "cid": m["conditionId"], "question": q,
                                 "kind": "min" if any(w in q.lower() for w in ("dip", "drop", "fall")) else "max",
                                 "strike": strike(q),
                                 "start": m.get("startDate") or e.get("startDate"), "end": m.get("endDate") or e.get("endDate"),
                                 "result": None if not res else ("yes" if float(res[0]) > 0.5 else "no"),
                                 "volume": float(m.get("volume") or 0)})
    return pd.DataFrame(rows)


def trades(cid):
    out, off = [], 0
    while True:
        j = jget("https://data-api.polymarket.com/trades", market=cid, limit=1000, offset=off, takerOnly="true")
        out += [{"cid": cid, "ts": t["timestamp"], "side": t["side"], "outcome": t["outcome"], "price": float(t["price"]),
                 "size": float(t["size"])} for t in j]
        if len(j) < 1000:
            return out
        off += 1000


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    if not os.path.exists(f"{OUT}/markets.parquet"):
        markets().to_parquet(f"{OUT}/markets.parquet")
    M = pd.read_parquet(f"{OUT}/markets.parquet")
    print(len(M), "markets", M.groupby("series").event.nunique().to_dict(), M.kind.value_counts().to_dict(), flush=True)
    with ThreadPoolExecutor(6) as ex:
        res = list(ex.map(trades, M[M.volume > 0].cid))
    T = pd.DataFrame([t for r in res for t in r])
    T.to_parquet(f"{OUT}/trades.parquet")
    print(len(T), "trades", flush=True)
