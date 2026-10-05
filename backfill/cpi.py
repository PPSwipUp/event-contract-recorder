"""Kalshi CPI month-over-month ladders vs the Cleveland Fed inflation nowcast (results/PLAN_CPI.md, frozen).
  python backfill/cpi.py
"""
from __future__ import annotations

import json
import math
import os

import numpy as np
import pandas as pd
import requests

import dohfix  # noqa: F401
from collect import K
from cryptolead import kget1

D = "data_local/cpi"
SPLIT = "2025-01-01"
MARGIN = 0.05
MON = {m: i for i, m in enumerate(["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], 1)}


def nowcasts():
    """daily CPI m/m nowcast vintages: DataFrame(target 'YYYY-M', date, value)"""
    p = f"{D}/nowcast.parquet"
    if os.path.exists(p):
        return pd.read_parquet(p)
    r = requests.get("https://www.clevelandfed.org/-/media/files/webcharts/inflationnowcasting/nowcast_month.json?sc_lang=en",
                     headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
    rows = []
    for x in r.json():
        ty, tm = map(int, x["chart"]["subcaption"].split("-"))
        labels = [c["label"] for c in x["categories"][0]["category"] if not c.get("vline")]
        cpi = next(s for s in x["dataset"] if s["seriesname"] == "CPI Inflation")["data"]
        assert len(labels) == len(cpi), (ty, tm)
        for lab, v in zip(labels, cpi):
            if not v.get("value"):
                continue
            mm, dd = map(int, lab.split("/"))
            yr = ty + 1 if mm < tm else ty                         # vintages run from the target month into the next
            rows.append({"target": f"{ty}-{tm}", "date": pd.Timestamp(yr, mm, dd), "value": float(v["value"])})
    N = pd.DataFrame(rows)
    N.to_parquet(p)
    return N


def events():
    out, cur = [], None
    while True:
        q = {"series_ticker": "KXCPI", "limit": 200}
        if cur:
            q["cursor"] = cur
        d = kget1(K + "/events", **q) or {}
        out += [e["event_ticker"] for e in d.get("events", [])]
        cur = d.get("cursor")
        if not cur or not d.get("events"):
            return out


def markets(ev):
    for base in ("/markets", "/historical/markets"):
        ms = (kget1(K + base, event_ticker=ev) or {}).get("markets", [])
        if ms:
            return ms
    return []


def trades(tk, a, b):
    out = []
    for base in ("/markets/trades", "/historical/trades"):
        cur = None
        while True:
            q = {"ticker": tk, "limit": 1000, "min_ts": a, "max_ts": b}
            if cur:
                q["cursor"] = cur
            d = kget1(K + base, **q) or {}
            out += d.get("trades", [])
            cur = d.get("cursor")
            if not cur or not d.get("trades"):
                break
    return out


def fee(p):
    return math.ceil(round(0.07 * 100 * p * (1 - p) * 100, 6)) / 100 / 100


def load():
    p = f"{D}/entries.parquet"
    if os.path.exists(p):
        return pd.read_parquet(p)
    rows = []
    for ev in events():
        y, mon = ev.split("-")[1][:2], ev.split("-")[1][2:]
        if mon not in MON:
            continue
        for m in markets(ev):
            if m.get("result") not in ("yes", "no") or m.get("strike_type") != "greater" or m.get("floor_strike") is None:
                continue
            close = pd.Timestamp(m["close_time"])
            c = int(close.timestamp())
            tr = sorted(trades(m["ticker"], c - 86400, c - 3600), key=lambda t: t["created_time"])
            for side in ("yes", "no"):
                t = next((t for t in tr if t["taker_side"] == side), None)
                if t:
                    rows.append({"event": ev, "target": f"20{y}-{MON[mon]}", "ticker": m["ticker"], "K": float(m["floor_strike"]),
                                 "close": close, "side": side, "px": float(t[f"{side}_price_dollars"]), "count": float(t["count_fp"]),
                                 "result": m["result"], "actual": float(m["expiration_value"].rstrip("%")) if m.get("expiration_value") else np.nan})
        print(ev, len(rows), flush=True)
    E = pd.DataFrame(rows)
    E.to_parquet(p)
    return E


def main():
    os.makedirs(D, exist_ok=True)
    N = nowcasts()
    E = load()
    assert len(E) > 100, f"only {len(E)} entries"
    # nowcast = latest vintage dated strictly before the decision day (decision window opens 24 h before close)
    E["dec_day"] = (E.close - pd.Timedelta(hours=24)).dt.tz_convert(None).dt.normalize()
    def nc(r):
        v = N[(N.target == r.target) & (N.date < r.dec_day)]
        return v.sort_values("date").value.iloc[-1] if len(v) else np.nan
    E["nowcast"] = E.apply(nc, axis=1)
    rel = E.groupby("event").agg(target=("target", "first"), close=("close", "first"), actual=("actual", "first"),
                                 nowcast=("nowcast", "first")).dropna()
    rel["actual"] = rel.actual.round(1)
    rel = rel.sort_values("close")
    rel["prev_actual"] = rel.actual.shift(1)
    rel["half"] = np.where(rel.close < pd.Timestamp(SPLIT, tz="UTC"), "train", "holdout")
    res_now = (rel[rel.half == "train"].actual - rel[rel.half == "train"].nowcast).values
    res_prev = (rel[rel.half == "train"].actual - rel[rel.half == "train"].prev_actual).dropna().values
    E = E.merge(rel[["half", "prev_actual"]], left_on="event", right_index=True)
    E["y"] = (E.result == "yes").astype(float)
    out = ["# Kalshi CPI m/m ladders vs Cleveland Fed nowcast (PLAN_CPI.md)", "",
           f"Releases with a nowcast: {len(rel)} (train {int((rel.half == 'train').sum())}, holdout {int((rel.half == 'holdout').sum())}); "
           f"entries {len(E)}", f"Train nowcast error (actual - nowcast): mean {res_now.mean():+.3f}, sd {res_now.std():.3f}", ""]
    for name, centre, res in (("nowcast", "nowcast", res_now), ("placebo: previous month's CPI", "prev_actual", res_prev)):
        X = E.dropna(subset=[centre]).copy()
        X["p_yes"] = [np.mean(np.round(c + res, 1) > k + 1e-9) for c, k in zip(X[centre], X.K)]
        X["p_side"] = np.where(X.side == "yes", X.p_yes, 1 - X.p_yes)
        X["win"] = np.where(X.side == "yes", X.y, 1 - X.y)
        X["fee"] = X.px.map(fee)
        X["edge"] = X.p_side - X.px - X.fee
        H = X[X.half == "holdout"]
        b_model = ((H.p_yes - H.y) ** 2)[H.side == "yes"].mean()
        b_price = ((H.px - H.y) ** 2)[H.side == "yes"].mean()
        for half in ("train", "holdout"):
            B = X[(X.half == half) & (X.edge >= MARGIN)].copy()
            B["pnl"] = B.win - B.px - B.fee
            if B.empty:
                out.append(f"{name} {half}: no bets")
                continue
            g = (B.pnl - B.pnl.mean()).groupby(B.event).sum()
            se = math.sqrt((g ** 2).sum()) / len(B)
            t = B.pnl.mean() / se if se > 0 else np.nan
            out.append(f"{name} {half}: bets {len(B)} over {B.event.nunique()} releases, mean {100 * B.pnl.mean():+.2f}c/contract, "
                       f"clustered t {t:.2f}, median print size {B['count'].median():.0f}")
            if name == "nowcast" and half == "holdout":
                gate = (B.pnl.mean(), t)
        out.append(f"{name} holdout Brier (YES-taker entries): model {b_model:.4f} vs entry price {b_price:.4f}")
        out.append("")
    mu, t = gate
    out.append(f"GATE (nowcast, holdout): mean {100 * mu:+.2f}c/contract, t {t:.2f} -> {'PASS' if mu > 0 and t > 2 else 'FAIL'}")
    open("../results/CPI.md", "w").write("\n".join(out) + "\n")
    print("\n".join(out))


if __name__ == "__main__":
    main()
