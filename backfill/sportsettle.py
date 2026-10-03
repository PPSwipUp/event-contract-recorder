"""Settlement lag on Polymarket SPORTS game markets (moneyline / match winner), last ~120 days.

A game's result is known at the final whistle but the market trades until Polymarket settles it (closedTime).  There
is no recorded end-of-game time, so 'known' is defined conservatively:
  cutoff = gameStartTime + 5 h (covers overtime / extra innings for nearly all games), AND the eventual winner has
  already traded at >= 99c before the trade in question.
Measured on every taker trade after the cutoff and before closedTime:
  risk    any market where, after the cutoff, a token traded >= 99c and then LOST (delays, reversals, disputes)
  taker   someone bought the winning token at p -> 1 - p - fee (sports taker fee rate 0.05)
  maker   someone sold the winning token into a bid at p -> 1 - p
  lock-up time from trade to closedTime
  python backfill/sportsettle.py
"""
from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from pmtouchdata import jget

D = "data_local/sportsettle"
TAGS = ["nfl", "mlb", "nba", "nhl", "epl", "soccer", "ncaaf", "tennis"]
DAYS = 120
FEE = 0.05


def games():
    since = (datetime.now(timezone.utc) - timedelta(days=DAYS)).isoformat()
    rows = {}
    for tag in TAGS:
        off = 0
        while off < 2500:
            evs = jget("https://gamma-api.polymarket.com/events", tag_slug=tag, closed="true", limit=100, offset=off,
                       order="endDate", ascending="false", end_date_min=since)
            if not isinstance(evs, list) or not evs:
                break
            off += 100
            for e in evs:
                for m in e.get("markets") or []:
                    if m.get("sportsMarketType") not in ("moneyline", None) or not m.get("gameStartTime") or not m.get("closedTime"):
                        continue
                    res = json.loads(m.get("outcomePrices") or "[]")
                    outs = json.loads(m.get("outcomes") or "[]")
                    if len(res) != 2 or sorted(res) != ["0", "1"]:
                        continue
                    rows[m["conditionId"]] = {"cid": m["conditionId"], "tag": tag, "question": m["question"],
                                              "start": m["gameStartTime"], "closed": m["closedTime"].replace(" ", "T").replace("+00", "Z"),
                                              "winner": outs[res.index("1")], "volume": float(m.get("volume") or 0)}
        print(tag, len(rows), flush=True)
    return pd.DataFrame(rows.values())


def trades_after(cid, start_ts):
    out, end = {}, None
    while True:
        j = jget("https://data-api.polymarket.com/trades", market=cid, limit=1000, takerOnly="true",
                 **({"end": end} if end else {}))
        new = 0
        for t in j:
            key = (t["transactionHash"], t["asset"], t["side"], t["size"], t["price"])
            if key not in out and t["timestamp"] >= start_ts:
                new += 1
                out[key] = {"cid": cid, "ts": t["timestamp"], "side": t["side"], "outcome": t["outcome"],
                            "price": float(t["price"]), "size": float(t["size"])}
        if len(j) < 1000 or not new or min(t["timestamp"] for t in j) < start_ts:
            return list(out.values())
        end = min(t["timestamp"] for t in j)


def main():
    os.makedirs(D, exist_ok=True)
    if not os.path.exists(f"{D}/games.parquet"):
        games().to_parquet(f"{D}/games.parquet")
    G = pd.read_parquet(f"{D}/games.parquet")
    G = G[G.volume > 1000]
    G["start_t"] = pd.to_datetime(G.start, utc=True, format="mixed")
    G["closed_t"] = pd.to_datetime(G.closed, utc=True, format="mixed")
    if not os.path.exists(f"{D}/trades.parquet"):
        with ThreadPoolExecutor(6) as ex:                              # trades from 1 h after the start (enough to see 99c prints)
            res = list(ex.map(lambda r: trades_after(r.cid, int((r.start_t + pd.Timedelta(hours=1)).timestamp())), G.itertuples()))
        pd.DataFrame([t for r in res for t in r]).to_parquet(f"{D}/trades.parquet")
    T = pd.read_parquet(f"{D}/trades.parquet").merge(G, on="cid")
    T["t"] = pd.to_datetime(T.ts, unit="s", utc=True)
    T = T.sort_values("t")
    T["on_winner"] = T.outcome == T.winner
    T["cutoff"] = T.start_t + pd.Timedelta(hours=5)
    # the winner has printed >= 99c before this trade
    T["w99"] = (T.on_winner & (T.price >= 0.99)).astype(int)
    T["seen99"] = T.groupby("cid").w99.cumsum().shift(fill_value=0) > 0
    P = T[(T.t >= T.cutoff) & (T.t < T.closed_t)]
    lost99 = P[(~P.on_winner) & (P.price >= 0.99)].cid.nunique()          # the 99c side after the cutoff LOST
    Q = P[P.seen99]
    taker = Q[Q.on_winner & (Q.side == "BUY")].copy()
    maker = Q[Q.on_winner & (Q.side == "SELL")].copy()
    taker["profit_$"] = taker["size"] * (1 - taker.price - FEE * taker.price * (1 - taker.price))
    maker["profit_$"] = maker["size"] * (1 - maker.price)
    days = max(1, (G.closed_t.max() - G.closed_t.min()).days)
    L = ["# Settlement lag on Polymarket sports game markets", "",
         f"Games (volume > $1k): {G.cid.nunique()} over ~{days} days; trades after start+5h and before settlement: {len(P)}",
         f"Median time from start+5h to settlement: {((G.closed_t - G.start_t).dt.total_seconds() / 3600 - 5).median():.1f} h", "",
         f"RISK: markets where a token traded >= 99c after the cutoff and then LOST: {lost99}", ""]
    for name, X in (("TAKER: buy the known winner", taker), ("MAKER: resting bid on the known winner", maker)):
        X["lock_h"] = (X.closed_t - X.t).dt.total_seconds() / 3600
        L += [f"## {name}", "", f"trades {len(X)}, shares {X['size'].sum():,.0f}, profit ${X['profit_$'].sum():,.0f} = "
              f"${X['profit_$'].sum() / days:,.1f}/day; median lock-up {X.lock_h.median():.1f} h", "",
              X.groupby(pd.cut(X.price, [0, 0.9, 0.97, 0.99, 0.995, 0.999, 1.0])).agg(
                  n=("size", "size"), shares=("size", "sum"), profit=("profit_$", "sum")).round(0).to_markdown(), "",
              X.groupby("tag").agg(n=("size", "size"), profit=("profit_$", "sum"), med_px=("price", "median")).round(3).to_markdown(), "",
              X.groupby(X.t.dt.strftime("%Y-%m"))["profit_$"].sum().round(0).to_frame().T.to_markdown(), ""]
    open("../results/SPORT_SETTLE.md", "w").write("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    main()
