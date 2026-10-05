"""Live signal engine for the two FORWARD-TESTED range-bot rules, computed exactly as backfill/forward.py and
backfill/forward_base.py score them (same research.probs / implied_mult / MARGIN / fee).  Read-only: public data,
no API key; it writes signals for live/executor.py, which is dry-run unless the user runs it with --live.

Every hour, 15 minutes after Kalshi's hourly range event opens (the forward tests' lag-15 quote):
  quote  each bracket's yes bid/ask (REST snapshot = the candle close the forward test uses)
  model  sig_raw = ppc forecast for this hour (fitted on Coinbase 1-min data up to the last completed hour),
         s0 = log price one minute before the quote, left = sqrt(hours to close),
         k_fixed / z fitted on all history before this hour, k_roll = 30-day trailing median |move| / forecast
  rule 'base' (forward test 2): BTC + ETH, fixed scale, bet where edge after fee > 5c
  rule 'eth'  (forward test 1): ETH, rolling scale + volatility view (implied multiplier vs outer/inner brackets)
Signals go to signals.jsonl (executor format: t, ticker, side, ask, size, edge_c, rule) and are logged to
rules_log.jsonl with every input, so live decisions can be audited against the forward-test ledger.
  python live/rules.py --rules base,eth
  python live/rules.py --check 2026-10-02      # replay a past day through this engine vs the forward test
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backfill"))
import dohfix  # noqa: F401,E402
import research  # noqa: E402
from backtest import fee_c, hourly  # noqa: E402
from collect import K, coinbase, event_ticker, get  # noqa: E402
from ppc import Forecaster  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
PRODUCTS = {"KXBTC": "BTC-USD", "KXETH": "ETH-USD"}
LAG = 15


def vol_state(minutes_df, hour):
    """model inputs for the hour starting at `hour` using only completed hours before it"""
    W, minute = hourly(minutes_df)
    W = W[W.index < hour]
    lrv = np.log(W.rv.clip(lower=1e-6))
    P = Forecaster(horizons=(1,), season=[24, 168], transform=None, fast=True).fit_predict(
        pd.DataFrame({"y": lrv.values}), target="y")
    fc = np.exp(pd.Series(P.auto_h1.values, index=W.index))       # forecast made at hour i for hour i+1
    ppc = fc.shift(1)                                              # = sigmas().ppc: forecast FOR hour i
    ok = ppc.notna()
    k_fixed = float(np.median(np.abs(W.ret[ok]) / ppc[ok]))
    z = np.sort((W.ret[ok] / (k_fixed * ppc[ok])).values)
    ratio = (np.abs(W.ret) / ppc).dropna()
    k_roll = float(ratio.iloc[-720:].median()) if len(ratio) >= 168 else np.nan
    return {"sig_raw": float(fc.iloc[-1]), "k_fixed": k_fixed, "k_roll": k_roll, "z": z, "minute": minute}


def decide(B, z, rule):
    """bets exactly as forward.py / forward_base.py select them; returns boolean arrays (yes, no) and p"""
    if rule == "base":
        p = research.probs(B, z, B.k_fixed.values)
        allow_yes = allow_no = None
    else:
        k = np.where(np.isfinite(B.k_roll), B.k_roll, B.k_fixed)
        p = research.probs(B, z, k)
        m = research.implied_mult(B, z, k).values
        centre = np.where(B.floor.isna(), B.cap, np.where(B.cap.isna(), B.floor, (B.floor + B.cap) / 2))
        outer = np.abs(np.log(centre) - B.s0.values) / (B.k_fixed.values * B.sig_raw.values * B.left.values) > 1.0
        more, less = m < 1 / 1.2, m > 1.2
        allow_yes, allow_no = (more & outer) | (less & ~outer), (more & ~outer) | (less & outer)
    ask, bid = B.ask.values, B.bid.values
    by = 100 * (p - ask) - fee_c(ask, 100) > research.MARGIN
    bn = (100 * (bid - p) - fee_c(1 - bid, 100) > research.MARGIN) & (bid > 0)
    if allow_yes is not None:
        by &= allow_yes
        bn &= allow_no
    return by, bn, p


def snapshot(series, close):
    ev = event_ticker(series, close)
    d = get(f"{K}/markets", event_ticker=ev, limit=1000) or {}
    rows = [{"event": ev, "ticker": m["ticker"], "floor": m.get("floor_strike"), "cap": m.get("cap_strike"),
             "bid": float(m["yes_bid_dollars"]) if m.get("yes_bid_dollars") else np.nan,
             "ask": float(m["yes_ask_dollars"]) if m.get("yes_ask_dollars") else np.nan} for m in d.get("markets", [])]
    B = pd.DataFrame(rows)
    if B.empty:
        return B
    for c in ("floor", "cap"):
        B[c] = pd.to_numeric(B[c], errors="coerce")
    return B[B.bid.notna() & (B.ask > 0) & (B.ask < 1)].copy()


def sizes(tickers):
    """best-ask sizes for YES and NO from the public batched order books"""
    out = {}
    for j in range(0, len(tickers), 100):
        d = get(f"{K}/markets/orderbooks", tickers=tickers[j:j + 100]) or {}
        for ob in d.get("orderbooks", []):
            b = ob["orderbook_fp"]
            yb = max(((float(p), float(q)) for p, q in b.get("yes_dollars") or []), default=(None, 0))
            nb = max(((float(p), float(q)) for p, q in b.get("no_dollars") or []), default=(None, 0))
            out[ob["ticker"]] = (nb[1], yb[1])                          # (YES-ask size, NO-ask size)
    return out


def run_hour(series, close, minutes_df, rules, qt):
    st = vol_state(minutes_df, close - timedelta(hours=1))
    B = snapshot(series, close)
    if B.empty:
        return []
    s0 = st["minute"].asof(pd.Timestamp(qt) - pd.Timedelta(minutes=1))
    B = B.assign(lag_min=LAG, close=pd.Timestamp(close), s0=s0, sig_raw=st["sig_raw"], k_fixed=st["k_fixed"],
                 k_roll=st["k_roll"], left=np.sqrt(np.clip((close - qt).total_seconds() / 3600, 0.01, 1)))
    out = []
    sz = None
    for rule in rules:
        if rule == "eth" and series != "KXETH":
            continue
        by, bn, p = decide(B, st["z"], rule)
        if by.any() or bn.any():
            sz = sz or sizes(B.ticker.tolist())
        for i in np.where(by | bn)[0]:
            r = B.iloc[i]
            side = "yes" if by[i] else "no"
            price = r.ask if side == "yes" else round(1 - r.bid, 4)
            out.append({"t": datetime.now(timezone.utc).isoformat(timespec="milliseconds"), "ticker": r.ticker,
                        "side": side, "ask": price, "size": (sz or {}).get(r.ticker, (0, 0))[0 if side == "yes" else 1],
                        "edge_c": round(100 * ((p[i] - price) if side == "yes" else (r.bid - p[i])), 2), "model": round(p[i], 4),
                        "rule": rule})
    log = {"t": datetime.now(timezone.utc).isoformat(timespec="seconds"), "series": series, "close": close.isoformat(),
           "quote_ts": qt.isoformat(), "s0": s0, "sig_raw": st["sig_raw"], "k_fixed": st["k_fixed"], "k_roll": st["k_roll"],
           "brackets": len(B), "signals": out}
    with open(os.path.join(HERE, "rules_log.jsonl"), "a") as f:
        f.write(json.dumps(log, default=float) + "\n")
    return out


def check(day):
    """replay one past day through decide() using the forward test's own inputs; counts must match its ledger"""
    import tempfile
    from concurrent.futures import ThreadPoolExecutor
    import collect
    d0 = datetime.fromisoformat(day).replace(tzinfo=timezone.utc)
    hours = pd.date_range(d0 + timedelta(hours=1), d0 + timedelta(hours=24), freq="1h", tz="UTC").to_pydatetime()
    for series, product in PRODUCTS.items():
        with ThreadPoolExecutor(4) as ex:
            rows = [r for rs in ex.map(collect.one_event, [(series, h) for h in hours]) for r in rs]
        with tempfile.TemporaryDirectory() as tmp:
            pd.DataFrame(rows).to_parquet(os.path.join(tmp, f"{series}.parquet"))
            coinbase(product, d0 - timedelta(days=200), d0 + timedelta(days=1, hours=2)).to_parquet(os.path.join(tmp, f"{product}.parquet"))
            B, z = research.prep(tmp, series, product)
        B = B[B.lag_min == LAG]
        for rule in ("base", "eth"):
            if rule == "eth" and series != "KXETH":
                continue
            by, bn, _ = decide(B, z, rule)
            print(day, series, rule, "bets via rules.decide:", int(by.sum() + bn.sum()), flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rules", default="base,eth")
    ap.add_argument("--out", default=os.path.join(HERE, "signals.jsonl"))
    ap.add_argument("--check", default="", help="replay a past UTC day and print bet counts")
    a = ap.parse_args()
    if a.check:
        check(a.check)
        return
    rules = a.rules.split(",")
    hist = {s: coinbase(p, datetime.now(timezone.utc) - timedelta(days=200), datetime.now(timezone.utc)) for s, p in PRODUCTS.items()}
    print("history loaded", {s: len(h) for s, h in hist.items()}, flush=True)
    while True:
        now = datetime.now(timezone.utc)
        close = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        qt = close - timedelta(minutes=60 - LAG)                     # 15 min after the event opens
        if now < qt:
            time.sleep((qt - now).total_seconds())
        elif now > qt + timedelta(minutes=2):                        # missed this hour's window: wait for the next
            time.sleep((close - now).total_seconds() + 5)
            continue
        try:
            for s, p in PRODUCTS.items():
                last = pd.to_datetime(hist[s].ts.max(), unit="s", utc=True).to_pydatetime()
                new = coinbase(p, last, datetime.now(timezone.utc))
                hist[s] = pd.concat([hist[s], new]).drop_duplicates("ts").sort_values("ts")
                sig = run_hour(s, close, hist[s], rules, qt)
                with open(a.out, "a") as f:
                    for x in sig:
                        f.write(json.dumps(x) + "\n")
                print(datetime.now(timezone.utc).strftime("%H:%M:%S"), s, "signals:", len(sig), flush=True)
        except Exception as err:
            print(datetime.now(timezone.utc).strftime("%H:%M:%S"), "error", repr(err)[:200], flush=True)
        time.sleep(max(0, (close - datetime.now(timezone.utc)).total_seconds() + 5))


if __name__ == "__main__":
    main()
