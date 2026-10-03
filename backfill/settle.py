"""Settlement lag on Polymarket's daily BTC/ETH noon markets ("above $K" and price ranges).

The result is fixed by the Binance 1-min candle that opens at 12:00 ET (closes 12:00:59), but the markets keep trading
until Polymarket settles them.  Using every real trade after 12:02 ET (data from pmabove.py / pmrange.py) and the
actual Binance candle, this measures:
  check     does the Binance-implied winner always match Polymarket's result?  (any mismatch = settlement risk)
  taker     someone BOUGHT the winning side after 12:02 at price p   -> we could have been that taker: 1 - p - fee
  maker     someone SOLD the winning side into a bid at p            -> a resting bid at p earns 1 - p (no maker fee)
by how far the close was from the nearest strike (closer = less certain at the time), minutes after noon, and
price bucket.  Capital lock-up = time from the trade to the market's last trade (settlement proxy).
  python backfill/settle.py
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd
import requests

import dohfix  # noqa: F401

D = "data_local"
SYM = {"bitcoin": "BTCUSDT", "ethereum": "ETHUSDT"}


def binance_noon(days):
    p = f"{D}/binance_noon.parquet"
    have = pd.read_parquet(p) if os.path.exists(p) else pd.DataFrame(columns=["asset", "end", "close"])
    rows = []
    for asset, sym in SYM.items():
        for end in sorted(set(days) - set(have[have.asset == asset].end)):
            t = int(pd.Timestamp(end).timestamp() * 1000)                  # endDate = 12:00 ET = candle open
            k = requests.get("https://api.binance.com/api/v3/klines", timeout=20,
                             params={"symbol": sym, "interval": "1m", "startTime": t, "limit": 1}).json()
            if k and int(k[0][0]) == t:
                rows.append({"asset": asset, "end": end, "close": float(k[0][4])})
    out = pd.concat([have, pd.DataFrame(rows)], ignore_index=True)
    out.to_parquet(p)
    return out


def load():
    parts = []
    for name in ("pmabove", "pmrange"):
        M = pd.read_parquet(f"{D}/{name}/markets.parquet")
        if "strike" in M:
            M["lo"], M["hi"] = M.strike, np.nan
        M["kind"] = name
        T = pd.read_parquet(f"{D}/{name}/trades.parquet").merge(M[["cid", "asset", "lo", "hi", "end", "result", "kind"]], on="cid")
        parts.append(T)
    T = pd.concat(parts, ignore_index=True)
    T = T[T.result.isin(["yes", "no"])]
    T["t"] = pd.to_datetime(T.ts, unit="s", utc=True)
    T["end_t"] = pd.to_datetime(T.end, format="ISO8601", utc=True)
    return T


def main():
    T = load()
    B = binance_noon(sorted(T.end.unique()))
    T = T.merge(B, on=["asset", "end"], how="left")
    # Binance-implied YES (above: close > K; range: lo <= close < hi; tails have one side NaN)
    lo_ok = T.lo.isna() | (T.close >= T.lo) if False else (T.lo.isna() | np.where(T.kind == "pmabove", T.close > T.lo, T.close >= T.lo))
    hi_ok = T.hi.isna() | (T.close < T.hi)
    T["implied_yes"] = lo_ok & hi_ok
    dist = np.fmin(np.abs(T.close - T.lo).fillna(np.inf), np.abs(T.close - T.hi).fillna(np.inf)) / T.close
    T["dist_pct"] = 100 * dist
    last = T.groupby("cid").t.transform("max")
    P = T[(T.t >= T.end_t + pd.Timedelta(minutes=2)) & T.close.notna()].copy()
    mk = P.drop_duplicates("cid")
    mism = mk[mk.implied_yes != (mk.result == "yes")]
    win_is_yes = P.result == "yes"
    P["winner_token"] = np.where(win_is_yes, "Yes", "No")
    P["on_winner"] = P.outcome == P.winner_token
    P["px"] = P.price                                                     # price of the token traded
    P["lock_h"] = (last.loc[P.index] - P.t).dt.total_seconds() / 3600
    P["mins"] = (P.t - P.end_t).dt.total_seconds() / 60
    taker = P[P.on_winner & (P.side == "BUY")].copy()
    maker = P[P.on_winner & (P.side == "SELL")].copy()
    taker["profit_$"] = taker["size"] * (1 - taker.px - 0.07 * taker.px * (1 - taker.px))
    maker["profit_$"] = maker["size"] * (1 - maker.px)
    L = ["# Settlement lag: trading after the result is fixed (Polymarket daily BTC/ETH noon markets)", "",
         f"Markets with post-12:02 trades: {mk.cid.nunique()}  ({P.end.str[:10].nunique()} days, "
         f"{P.end.min()[:10]} .. {P.end.max()[:10]})", "",
         f"Check: Binance-implied result vs Polymarket result mismatches: {len(mism)} of {len(mk)}"
         + (f" (closest distance {mism.dist_pct.min():.4f}%)" if len(mism) else ""), ""]
    for name, X in (("TAKER: buy the winner from resting asks", taker), ("MAKER: resting bid on the winner, hit by sellers", maker)):
        X["bucket"] = pd.cut(X.px, [0, 0.9, 0.97, 0.99, 0.995, 0.999, 1.0])
        X["certainty"] = pd.cut(X.dist_pct, [0, 0.05, 0.2, 1, 100])
        days = max(1, X.end.str[:10].nunique())
        L += [f"## {name}", "", f"trades {len(X)}, shares {X['size'].sum():,.0f}, profit ${X['profit_$'].sum():,.0f} "
              f"over {days} days = ${X['profit_$'].sum() / days:,.1f}/day; median lock-up {X.lock_h.median():.1f} h", "",
              "by price paid:", "", X.groupby("bucket").agg(n=("size", "size"), shares=("size", "sum"), profit=("profit_$", "sum")).round(0).to_markdown(), "",
              "by how far Binance closed from the strike (% of price):", "",
              X.groupby("certainty").agg(n=("size", "size"), shares=("size", "sum"), profit=("profit_$", "sum"),
                                         med_px=("px", "median")).round(3).to_markdown(), "",
              "by minutes after noon:", "",
              X.groupby(pd.cut(X.mins, [2, 5, 15, 60, 240, 1e6])).agg(n=("size", "size"), profit=("profit_$", "sum"),
                                                                   med_px=("px", "median")).round(3).to_markdown(), "",
              "by month:", "", X.groupby(X.end.str[:7])["profit_$"].sum().round(0).to_frame().T.to_markdown(), ""]
    open("../results/SETTLE.md", "w").write("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    main()
