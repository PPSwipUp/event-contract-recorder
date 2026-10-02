"""Volatility model on Kalshi's S&P 500 / Nasdaq-100 daily-close range markets, from real trades (Feb 2025 - Sep 2026).

Vol model: PPC Forecaster on log realized vol of 30-minute regular-session bars of SPY / QQQ (seasons 13 = one day,
65 = one week), predicting each bar from the past only.  Variance left until the 4pm close = rest of the current bar
+ later bars scaled by the training-period intraday profile.  Index level at the trade = ETF price one minute before
the trade x (previous official close / ETF's previous 4pm close) - all known at the time.
Entries: every 30 min from 10:00 to 15:30 ET, per market and side, the first real taker trade in the next 10 min
is the price we could have bought at.  Size = what other takers bought on that side at our price or better in the
following 30 min (max 100).  Kalshi fees (0.07 schedule, conservative).
Pre-declared: TRAIN = 2025-02..2025-12 picks the edge margin; HOLDOUT = 2026-01..2026-09 is run once.
  python backfill/idx_backtest.py --series KXINX --etf SPY
"""
from __future__ import annotations

import argparse
import glob
import os
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from ppc import Forecaster

from backtest import fee_c

ET = ZoneInfo("America/New_York")
D = "data_local/idx"
TRAIN, HOLD = ("2025-02-01", "2026-01-01"), ("2026-01-01", "2026-10-01")
CAP = 100


def bars(etf):
    m = pd.read_parquet(f"{D}/{etf}_1m.parquet")
    m = m[~m.index.duplicated()]
    et = m.index.tz_convert(ET)
    mins = et.hour * 60 + et.minute
    m = m[(mins >= 570) & (mins < 960)].copy()                     # 9:30-16:00 ET regular session
    et = m.index.tz_convert(ET)
    m["day"] = et.strftime("%Y-%m-%d")
    m["bkt"] = ((et.hour * 60 + et.minute) - 570) // 30            # 0..12
    m["lc"] = np.log(m.c)
    m["r"] = m.groupby("day").lc.diff()
    W = m.groupby(["day", "bkt"]).agg(rv=("r", lambda x: np.sqrt((x ** 2).sum())), first=("lc", "first"))
    return m, W


def model(W):
    lrv = np.log(W.rv.clip(lower=1e-6))
    P = Forecaster(horizons=(1,), season=[13, 65], transform=None, fast=True).fit_predict(
        pd.DataFrame({"y": lrv.values}), target="y")
    return pd.Series(np.exp(pd.Series(P.auto_h1.values, index=W.index).shift(1)).values, index=W.index)


def entries(series, m):
    M = pd.read_parquet(f"{D}/{series}_markets.parquet")
    T = pd.concat([pd.read_parquet(f) for f in sorted(glob.glob(f"{D}/{series}_trades_*.parquet"))], ignore_index=True)
    T["t"] = pd.to_datetime(T.ts, format="ISO8601", utc=True)
    T = T.merge(M[["ticker", "event_ticker", "floor_strike", "cap_strike", "result", "close_time"]], on="ticker")
    T["day"] = pd.to_datetime(T.close_time, format="ISO8601", utc=True).dt.tz_convert(ET).dt.strftime("%Y-%m-%d")
    et = T.t.dt.tz_convert(ET)
    T = T[et.dt.strftime("%Y-%m-%d") == T.day]                     # trades on the settlement day itself
    et = T.t.dt.tz_convert(ET)
    mins = et.dt.hour * 60 + et.dt.minute
    T = T[(mins >= 600) & (mins < 960)].copy()                      # 10:00 - 16:00 ET
    T["slot"] = ((mins[T.index] - 600) // 30)
    T["in_win"] = ((mins[T.index] - 600) % 30) < 10
    T["px"] = np.where(T.taker == "yes", T.yes, 1 - T.yes)          # price the taker paid for their side
    first = T[T.in_win].sort_values("t").groupby(["ticker", "slot", "taker"]).head(1)
    # volume others bought on the same side at our price or better, after us, within the slot
    J = first[["ticker", "slot", "taker", "t", "px"]].merge(T[["ticker", "slot", "taker", "t", "px", "count"]],
                                                            on=["ticker", "slot", "taker"], suffixes=("", "_o"))
    av = J[(J.t_o > J.t) & (J.px_o <= J.px + 1e-9)].groupby(["ticker", "slot", "taker"])["count"].sum()
    E = first.join(av.rename("avail"), on=["ticker", "slot", "taker"])
    E["avail"] = E.avail.fillna(0)
    E["won"] = np.where(E.taker == "yes", E.result == "yes", E.result == "no").astype(float)
    E["floor"] = pd.to_numeric(E.floor_strike)
    E["cap"] = pd.to_numeric(E.cap_strike)
    # previous official close for the ETF->index ratio
    st = M.groupby("event_ticker").agg(close_time=("close_time", "first"), value=("expiration_value", "first")).reset_index()
    st["day"] = pd.to_datetime(st.close_time, format="ISO8601", utc=True).dt.tz_convert(ET).dt.strftime("%Y-%m-%d")
    st["value"] = pd.to_numeric(st.value, errors="coerce")
    st = st[st.event_ticker.str.contains("H1600|^INX-|^NASDAQ100-", regex=True)].sort_values("day").drop_duplicates("day")
    etf_close = m.groupby("day").c.last()
    ratio = (st.set_index("day").value / etf_close.reindex(st.day).values).shift(1)
    E["ratio"] = E.day.map(ratio)
    return E


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", default="KXINX")
    ap.add_argument("--etf", default="SPY")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    m, W = bars(a.etf)
    W["sig"] = model(W)
    days = sorted(m.day.unique())
    tr_days = [d for d in days if TRAIN[0] <= d < TRAIN[1]]
    prof = W.loc[tr_days].rv.groupby(level="bkt").median()

    E = entries(a.series, m)
    E = E[np.isfinite(E.ratio)].copy()
    tmin = (E.t.dt.floor("1min") - pd.Timedelta(minutes=1))
    lc = m.lc
    E["s0"] = lc.reindex(tmin).values + np.log(E.ratio.values)      # log index level one minute before the trade
    et = E.t.dt.tz_convert(ET)
    mins = (et.dt.hour * 60 + et.dt.minute).values
    b = (mins - 570) // 30
    sig_now = W.sig.reindex(pd.MultiIndex.from_arrays([E.day.values, b])).values
    var = np.zeros(len(E))
    for j in range(13):
        later = (b < j)
        var += np.where(later, (sig_now * prof[j] / prof.reindex(b).values) ** 2, 0)
    var += sig_now ** 2 * (30 - (mins - 570) % 30) / 30
    E["sig_rem"] = np.sqrt(var)
    E = E[np.isfinite(E.s0) & np.isfinite(E.sig_rem) & (E.sig_rem > 0)].copy()

    # empirical shape of (close - now) / predicted remaining vol, from TRAIN days at each slot start
    close_l = m.groupby("day").lc.last()
    zt = E[(E.day >= TRAIN[0]) & (E.day < TRAIN[1])].drop_duplicates(["day", "slot"])
    zr = (close_l.reindex(zt.day).values + np.log(zt.ratio.values) - zt.s0.values) / zt.sig_rem.values
    zr = zr[np.isfinite(zr)]
    k = float(np.median(np.abs(zr)) / 0.6745)
    z = np.sort(zr / k)

    def cdf(K):
        x = (np.log(K) - E.s0.values) / (k * E.sig_rem.values)
        return np.searchsorted(z, np.nan_to_num(x)) / len(z)

    p_yes = np.clip(np.where(E.cap.isna(), 1.0, cdf(E.cap.values + 1e-4)) - np.where(E.floor.isna(), 0.0, cdf(E.floor.values)), 0, 1)
    E["p"] = np.where(E.taker == "yes", p_yes, 1 - p_yes)
    E["fee"] = fee_c(E.px.values, 100)
    E["edge_c"] = 100 * (E.p - E.px) - E.fee
    E["pnl_c"] = 100 * E.won - 100 * E.px - E.fee
    E = E[(E.px > 0) & (E.px < 1)]

    # accuracy: model vs traded price (Brier), all entries
    def brier(x):
        return pd.Series({"n": len(x), "brier_model": ((x.p - x.won) ** 2).mean(), "brier_price": ((x.px - x.won) ** 2).mean()})
    L = [f"# Volatility model vs Kalshi {a.series} (daily close ranges), {a.etf} as the price feed", "",
         f"Entries (first real trade per market/side/30-min slot, 10:00-15:30 ET): {len(E)}; vol scale k = {k:.2f}.", "",
         "## Who is more accurate? (lower Brier is better)", "",
         E.groupby(E.day.str[:4]).apply(brier).round(4).to_markdown(), ""]

    def run(margin, flip=False):
        B = E[(E.edge_c > margin) & (E.avail > 0)].copy()
        B["n"] = np.minimum(B.avail, CAP)
        pnl = -B.pnl_c - 2 * B.fee if flip else B.pnl_c
        B["dollars"] = pnl * B.n / 100
        return B

    def score(B, s, e):
        B = B[(B.day >= s) & (B.day < e)]
        d = B.groupby("day").dollars.sum()
        alld = pd.Series(0.0, index=[x for x in days if s <= x < e]).add(d, fill_value=0)
        eq = alld.cumsum()
        t = d.mean() / d.std() * np.sqrt(len(d)) if len(d) > 2 and d.std() > 0 else np.nan
        mo = alld.groupby(alld.index.str[:7]).sum()
        return {"bets": len(B), "c_per_bet": round(B.pnl_c.mean(), 2) if len(B) else np.nan, "total_$": round(alld.sum()),
                "per_month_$": round(alld.sum() / max(1, len(mo)), 1), "max_dd_$": round((eq.cummax() - eq).max()),
                "day_t": round(t, 2), "months_pos": f"{(mo > 0).sum()}/{len(mo)}", "avg_contracts": round(B.n.mean(), 1) if len(B) else 0}

    rows = []
    for mg in (2, 5, 8, 12, 20):
        B = run(mg)
        rows.append({"margin_c": mg, **{f"train_{k_}": v for k_, v in score(B, *TRAIN).items()}})
    R = pd.DataFrame(rows)
    ok = R[R.train_bets >= 100]
    best = int(ok.sort_values("train_day_t", ascending=False).margin_c.iloc[0]) if len(ok) else 5
    L += ["## Edge margin chosen on TRAIN (2025)", "", R.to_markdown(index=False), "", f"Chosen margin: {best}c", ""]
    chk = []
    for name, B in (("model", run(best)), ("placebo: opposite side", run(best, flip=True))):
        chk.append({"bot": name, **{f"hold_{k_}": v for k_, v in score(B, *HOLD).items()}})
    L += ["## HOLDOUT (2026, run once)", "", pd.DataFrame(chk).to_markdown(index=False), ""]
    B = run(best)
    B = B[(B.day >= HOLD[0]) & (B.day < HOLD[1])]
    L += ["### Holdout by side / time of day", "",
          B.groupby("taker").agg(bets=("n", "size"), c_per_bet=("pnl_c", "mean"), dollars=("dollars", "sum")).round(2).to_markdown(), "",
          B.groupby(B.slot // 4).agg(bets=("n", "size"), c_per_bet=("pnl_c", "mean"), dollars=("dollars", "sum")).round(2).to_markdown(), ""]
    out = a.out or f"../results/IDX_{a.series}.md"
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, "w").write("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    main()
