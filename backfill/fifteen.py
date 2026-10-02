"""Kalshi 15-minute crypto up/down (KXBTC15M / KXETH15M / KXSOL15M) vs the volatility model, Aug - Sep 2026.

Each market: YES if the index's 60-s average before the close >= the 60-s average before the open (the strike).
At each minute inside the window: model P(up) = 1 - F((ln strike - ln S) / (k * sigma_hour * sqrt(min_left/60))),
S = Coinbase close of the minute BEFORE the quote minute (one minute stale on purpose), sigma_hour = PPC forecast.
Quotes = Kalshi 1-minute candle close bid/ask (exist from ~Aug 2026).  Buy YES at the ask / NO at 1-bid when the
model edge after Kalshi fees beats the margin; 100 contracts (these books trade ~100k contracts a minute).
Pre-declared: margin picked on AUGUST, run once on SEPTEMBER.  Placebo: spot 5 minutes staler.
  python backfill/fifteen.py --series KXBTC15M --product BTC-USD
"""
from __future__ import annotations

import argparse
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from backtest import fee_c, hourly, sigmas
from collect import ET, K, MON, coinbase, get

TRAIN, HOLD = ("2026-08-01", "2026-09-01"), ("2026-09-01", "2026-10-01")
N = 100


def ev_ticker(series, close):
    t = close.astimezone(ET)
    return f"{series}-{t:%y}{MON[t.month - 1]}{t:%d%H%M}"


def one(args):
    series, close = args
    ev = ev_ticker(series, close)
    try:
        ms = (get(f"{K}/markets", event_ticker=ev, limit=5) or {}).get("markets") or \
             (get(f"{K}/historical/markets", event_ticker=ev, limit=5) or {}).get("markets") or []
        if not ms or ms[0].get("result") not in ("yes", "no") or ms[0].get("floor_strike") is None:
            return []
        m = ms[0]
        c = int(close.timestamp())
        d = get(f"{K}/series/{series}/events/{ev}/candlesticks", period_interval=1, start_ts=c - 900, end_ts=c) or {}
    except Exception as e:
        print("skip", ev, repr(e)[:80], flush=True)
        return []
    rows = []
    for cs in d.get("market_candlesticks", [])[:1]:
        for x in cs:
            b, a = x["yes_bid"].get("close_dollars"), x["yes_ask"].get("close_dollars")
            if b is None or a is None:
                continue
            rows.append({"event": ev, "close": close, "ts": x["end_period_ts"], "bid": float(b), "ask": float(a),
                         "vol": float(x.get("volume_fp") or 0), "strike": float(m["floor_strike"]),
                         "y": float(m["result"] == "yes")})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", default="KXBTC15M")
    ap.add_argument("--product", default="BTC-USD")
    a = ap.parse_args()
    cache = f"data_local/fifteen_{a.series}.parquet"
    if os.path.exists(cache):
        Q = pd.read_parquet(cache)
    else:
        t0, t1 = datetime(2026, 8, 1, tzinfo=timezone.utc), datetime(2026, 10, 1, tzinfo=timezone.utc)
        closes = [t0 + timedelta(minutes=15 * i) for i in range(1, int((t1 - t0).total_seconds() // 900) + 1)]
        with ThreadPoolExecutor(4) as ex:
            Q = pd.DataFrame([r for rs in ex.map(one, [(a.series, c) for c in closes]) for r in rs])
        Q.to_parquet(cache)
    print("quotes", len(Q), "events", Q.event.nunique(), flush=True)

    spot = coinbase(a.product, datetime(2026, 1, 1, tzinfo=timezone.utc), datetime(2026, 10, 2, tzinfo=timezone.utc))
    W, minute = hourly(spot)
    S = sigmas(W)
    tr = (W.index < pd.Timestamp(TRAIN[0], tz="UTC")) & S.ppc.notna()
    k = float(np.median(np.abs(W.ret[tr]) / S.ppc[tr]))
    z = np.sort((W.ret[tr] / (k * S.ppc[tr])).values)

    Q["t"] = pd.to_datetime(Q.ts, unit="s", utc=True)
    Q["min_left"] = (pd.to_datetime(Q.close, utc=True) - Q.t).dt.total_seconds() / 60
    Q = Q[(Q.min_left >= 1) & (Q.min_left <= 13)].copy()
    Q["day"] = Q.t.dt.strftime("%Y-%m-%d")
    sig_h = S.ppc.reindex(Q.t.dt.floor("1h")).values

    def evaluate(stale):
        s0 = minute.reindex(Q.t - pd.Timedelta(minutes=1 + stale)).values        # log price, minute ending 1 min before
        sig = k * sig_h * np.sqrt(Q.min_left.values / 60)
        x = (np.log(Q.strike.values) - s0) / sig
        p = 1 - np.searchsorted(z, np.nan_to_num(x)) / len(z)
        ok = np.isfinite(s0) & np.isfinite(sig) & (Q.ask > 0) & (Q.ask < 1) & (Q.bid > 0) & (Q.bid < 1)
        ey = 100 * (p - Q.ask) - fee_c(Q.ask.values, N)
        en = 100 * ((1 - p) - (1 - Q.bid)) - fee_c(1 - Q.bid.values, N)
        R = Q.assign(p=p, ey=ey, en=en)[ok]
        return R

    def bets(R, margin):
        # at most one bet per market: the first minute that qualifies (either side)
        y = R[R.ey > margin].assign(side="yes", edge=lambda d: d.ey, px=lambda d: d.ask, won=lambda d: d.y)
        n = R[R.en > margin].assign(side="no", edge=lambda d: d.en, px=lambda d: 1 - d.bid, won=lambda d: 1 - d.y)
        B = pd.concat([y, n]).sort_values("t").groupby("event").head(1).copy()
        B["pnl_c"] = 100 * B.won - 100 * B.px - fee_c(B.px.values, N)
        B["dollars"] = B.pnl_c * N / 100
        return B

    def score(B, s, e):
        B = B[(B.day >= s) & (B.day < e)]
        d = B.groupby("day").dollars.sum()
        t = d.mean() / d.std() * np.sqrt(len(d)) if len(d) > 2 and d.std() > 0 else np.nan
        return {"bets": len(B), "c_per_bet": round(B.pnl_c.mean(), 2) if len(B) else np.nan,
                "pred_edge_c": round(B.edge.mean(), 2) if len(B) else np.nan, "total_$": round(B.dollars.sum()),
                "day_t": round(t, 2), "win": round(B.won.mean(), 3) if len(B) else np.nan}

    R = evaluate(0)
    L = [f"# {a.series} (15-min up/down) vs volatility model, Aug-Sep 2026", "",
         f"Minute quotes used: {len(R)}; events {R.event.nunique()}; k = {k:.2f}; median spread "
         f"{100 * (R.ask - R.bid).median():.2f}c", "",
         "Brier on all minute quotes (lower better): model "
         f"{((R.p - R.y) ** 2).mean():.4f} vs Kalshi mid {((((R.ask + R.bid) / 2) - R.y) ** 2).mean():.4f}", ""]
    rows = [{"margin_c": mg, **{f"aug_{k_}": v for k_, v in score(bets(R, mg), *TRAIN).items()}} for mg in (1, 2, 3, 5, 8)]
    G = pd.DataFrame(rows)
    ok = G[G.aug_bets >= 100]
    best = int(ok.sort_values("aug_day_t", ascending=False).margin_c.iloc[0]) if len(ok) else 5
    L += ["## Margin chosen on August", "", G.to_markdown(index=False), "", f"Chosen: {best}c", "",
          "## September (run once)", "",
          pd.DataFrame([{"bot": "model", **score(bets(R, best), *HOLD)},
                        {"bot": "placebo: spot 5 min staler", **score(bets(evaluate(5), best), *HOLD)}]).to_markdown(index=False), ""]
    out = f"../results/FIFTEEN_{a.series}.md"
    open(out, "w").write("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    main()
