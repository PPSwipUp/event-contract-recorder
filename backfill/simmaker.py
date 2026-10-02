"""Event-driven market-making simulator for Kalshi hourly BTC/ETH range markets, replaying the REAL trade tape and the
REAL 1-minute best bid/ask (Aug-Sep 2026), with our own resting orders inserted into that market.

Timeline per hourly event, for each of the 10 brackets nearest the price:
  * Every minute boundary tau we requote using only what is known at tau: the Coinbase price at tau (close of the
    minute that just ended), the PPC vol forecast for the hour, and Kalshi's best bid/ask at tau.
    Fair value p = the frozen vol model (k, z from data BEFORE the simulation period).
  * Orders go live LAT seconds after tau and are replaced at the next refresh (we cannot cancel faster than that, so
    a price jump inside the minute can pick us off - this is where real market makers lose money).
  * Sell-YES order: price a = best ask - 1c (we become the best ask) if that still beats p by MARGIN + maker fee;
    otherwise (JOIN) at the lowest price that does, sitting behind everyone already there.
    Buy-YES order: mirror image at best bid + 1c.  Never posted through the opposite side of the book.
  * Matching against each real taker trade while our order is live:
      - if we are the only order at the best price ("first"): a taker who bought YES at y >= a would have hit us first,
        at OUR price a; we fill min(their size, our remaining size) and the rest of their order goes to the book as
        it really did (market impact: we take that volume from the other makers);
      - if we joined a queue, or another bot is assumed to have matched our improved price first (probability
        COMPETE per order), we fill only when a trade prints strictly THROUGH our price (the queue at our price must
        have been eaten);
      - mirror image for buy-YES orders against takers who sold YES.
  * Limits: order size QSIZE; position per market and side <= POS; contracts per event <= EVCAP.
  * Fees: Kalshi maker fee per fill, ceil(1.75 * n * P * (1 - P)) cents (charged even if Kalshi waives it on these
    series - conservative).  Positions are held to settlement (no exit slippage), paid by Kalshi's real result.
Reported for a grid of the unknowns (COMPETE, LAT, QSIZE, maker fee) - NOT used to pick anything; the 8c margin is the
one frozen on 2024-25 data.  Baselines: same quoting with NO model (pure spread capture) and with the model's sign
flipped (placebo).
  python backfill/simmaker.py
"""
from __future__ import annotations

import glob
import itertools
import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd

import research
from backtest import hourly, sigmas
from collect import coinbase

SIM = "data_local/sim"
PAIRS = {"KXBTC": "BTC-USD", "KXETH": "ETH-USD"}
START = pd.Timestamp("2026-08-01", tz="UTC")
MARGIN = 8.0
POS, EVCAP = 100, 400


def maker_fee_total_c(p, n):
    return np.ceil(1.75 * n * p * (1 - p))


def load(series, product):
    def cat(kind):
        fs = sorted(glob.glob(f"{SIM}/{series}_*_{kind}.parquet"))
        return pd.concat([pd.read_parquet(f) for f in fs], ignore_index=True) if fs else pd.DataFrame()
    M, T, Q = cat("markets"), cat("trades"), cat("quotes")
    if M.empty:
        return None
    M["close"] = pd.to_datetime(M.close, utc=True)
    M = M[M.result.isin(["yes", "no"])]
    T["t"] = pd.to_datetime(T.ts, format="ISO8601", utc=True)
    spot = coinbase(product, (START - pd.Timedelta(days=200)).to_pydatetime(), datetime(2026, 10, 2, tzinfo=timezone.utc))
    W, minute = hourly(spot)
    S = sigmas(W)
    tr = (W.index < START) & S.ppc.notna()
    k = float(np.median(np.abs(W.ret[tr]) / S.ppc[tr]))
    z = np.sort((W.ret[tr] / (k * S.ppc[tr])).values)
    # one row per (market, minute boundary tau): what we know at tau
    Q = Q.merge(M[["ticker", "event", "close", "floor", "cap", "result"]], on="ticker")
    Q["tau"] = pd.to_datetime(Q.ts, unit="s", utc=True)
    Q = Q[(Q.tau >= Q.close - pd.Timedelta(hours=1)) & (Q.tau < Q.close - pd.Timedelta(minutes=1))].copy()
    Q["s0"] = minute.reindex(Q.tau - pd.Timedelta(minutes=1)).values           # bar ending exactly at tau
    Q["left"] = np.sqrt(np.clip((Q.close - Q.tau).dt.total_seconds().values / 3600, 0.01, 1))
    Q["sig_raw"] = S.ppc.reindex(Q.close - pd.Timedelta(hours=1)).values
    Q = Q[np.isfinite(Q.s0) & np.isfinite(Q.sig_raw)].copy()
    Q["p"] = research.probs(Q, z, np.full(len(Q), k))
    Q["series"] = series
    T = T.merge(M[["ticker", "event"]], on="ticker")
    return M, T, Q


def quotes_for(Q, use_model=True, flip=False, fee_on=True):
    """our desired order prices at each tau (NaN = no order)"""
    mid = ((Q.bid + Q.ask) / 2).values
    p = Q.p.values if use_model else mid
    if flip:
        p = np.clip(2 * mid - Q.p.values, 0, 1)                                    # the model mirrored around the mid
    bid, ask = Q.bid.values, Q.ask.values
    f = (lambda px: maker_fee_total_c(px, 25) / 25) if fee_on else (lambda px: 0 * px)
    # sell YES
    a_imp = np.round(ask - 0.01, 2)
    ok_imp = np.isfinite(ask) & (a_imp > np.nan_to_num(bid, nan=0)) & (a_imp > 0)
    a_min = np.ceil((p + MARGIN / 100) * 100 - 1e-9) / 100                        # lowest price with enough edge
    a_min = np.where(100 * (a_min - p) - f(np.clip(a_min, 0.01, 0.99)) >= MARGIN, a_min, a_min + 0.01)
    need = MARGIN if use_model else 0.0
    imp_good = ok_imp & (100 * (a_imp - p) - f(np.clip(a_imp, 0.01, 0.99)) >= need)
    sell_px = np.where(imp_good, a_imp, np.where(use_model & np.isfinite(ask) & (a_min < 1), np.maximum(a_min, ask), np.nan))
    sell_first = imp_good
    # buy YES
    b_imp = np.round(bid + 0.01, 2)
    okb = np.isfinite(bid) & (b_imp < np.nan_to_num(ask, nan=1)) & (b_imp < 1)
    b_max = np.floor((p - MARGIN / 100) * 100 + 1e-9) / 100
    b_max = np.where(100 * (p - b_max) - f(np.clip(b_max, 0.01, 0.99)) >= MARGIN, b_max, b_max - 0.01)
    bimp_good = okb & (100 * (p - b_imp) - f(np.clip(b_imp, 0.01, 0.99)) >= need)
    buy_px = np.where(bimp_good, b_imp, np.where(use_model & np.isfinite(bid) & (b_max > 0), np.minimum(b_max, bid), np.nan))
    return sell_px, sell_first, buy_px, bimp_good


def simulate(M, T, Q, compete=0.0, lat=2, qsize=25, fee_on=True, use_model=True, flip=False, seed=0, max_mins=60):
    sell_px, sell_first, buy_px, buy_first = quotes_for(Q, use_model, flip, fee_on)
    late = ((Q.tau - (Q.close - pd.Timedelta(hours=1))).dt.total_seconds() / 60 >= max_mins).values
    sell_px, buy_px = np.where(late, np.nan, sell_px), np.where(late, np.nan, buy_px)
    rng = np.random.default_rng(seed)
    beaten_s = rng.random(len(Q)) < compete                  # another bot got to our improved price first
    beaten_b = rng.random(len(Q)) < compete
    O = pd.DataFrame({"ticker": Q.ticker.values, "event": Q.event.values, "tau": Q.tau.values,
                      "sell": sell_px, "sell_first": sell_first & ~beaten_s, "buy": buy_px, "buy_first": buy_first & ~beaten_b,
                      "p": Q.p.values})
    O["live_from"] = O.tau + pd.Timedelta(seconds=lat)
    O["live_to"] = O.tau + pd.Timedelta(seconds=60 + lat)
    # attach each trade to the order live at that time (orders are replaced each minute)
    Tm = T.copy()
    Tm["tau"] = (Tm.t - pd.Timedelta(seconds=lat)).dt.floor("1min")
    Tm = Tm.merge(O, on=["ticker", "event", "tau"], how="inner")
    Tm = Tm[(Tm.t >= Tm.live_from) & (Tm.t < Tm.live_to)]
    # can this trade reach our order?
    hit_s = (Tm.taker == "yes") & np.isfinite(Tm.sell) & np.where(Tm.sell_first, Tm.yes >= Tm.sell - 1e-9, Tm.yes > Tm.sell + 1e-9)
    hit_b = (Tm.taker == "no") & np.isfinite(Tm.buy) & np.where(Tm.buy_first, Tm.yes <= Tm.buy + 1e-9, Tm.yes < Tm.buy - 1e-9)
    C = pd.concat([Tm[hit_s].assign(side="sell", px=lambda d: d.sell), Tm[hit_b].assign(side="buy", px=lambda d: d.buy)])
    C = C.sort_values("t")
    # sequential fills with order size, position and event caps
    rem, pos, evn, fills = {}, {}, {}, []
    for r in C.itertuples(index=False):
        ok_key = (r.ticker, r.tau, r.side)
        o_rem = rem.get(ok_key, qsize)
        p_rem = POS - pos.get((r.ticker, r.side), 0)
        e_rem = EVCAP - evn.get(r.event, 0)
        n = min(o_rem, p_rem, e_rem, r.count)
        if n < 1:
            continue
        n = float(np.floor(n))
        rem[ok_key] = o_rem - n
        pos[(r.ticker, r.side)] = pos.get((r.ticker, r.side), 0) + n
        evn[r.event] = evn.get(r.event, 0) + n
        fills.append((r.ticker, r.event, r.t, r.side, r.px, n, r.p))
    F = pd.DataFrame(fills, columns=["ticker", "event", "t", "side", "yes_px", "n", "p_yes"])
    if F.empty:
        return F
    F = F.merge(M[["ticker", "result", "close"]], on="ticker")
    # sell YES = we hold NO bought at 1 - yes_px; buy YES = we hold YES at yes_px
    F["our_px"] = np.where(F.side == "sell", 1 - F.yes_px, F.yes_px)
    F["won"] = np.where(F.side == "sell", F.result == "no", F.result == "yes").astype(float)
    F["fee_$"] = maker_fee_total_c(F.our_px.values, F.n.values) / 100 if fee_on else 0.0
    F["pnl_$"] = (F.won - F.our_px) * F.n - F["fee_$"]
    F["pred_edge_c"] = 100 * np.where(F.side == "sell", F.yes_px - F.p_yes, F.p_yes - F.yes_px)
    F["day"] = F.close.dt.strftime("%Y-%m-%d")
    F["mins_in"] = (F.t - (F.close - pd.Timedelta(hours=1))).dt.total_seconds() // 60
    return F


def summary(F, n_hours):
    if F.empty:
        return {"fills": 0}
    d = F.groupby("day")["pnl_$"].sum()
    days = pd.date_range("2026-08-01", "2026-09-30").strftime("%Y-%m-%d")
    d_all = pd.Series(0.0, index=days).add(d, fill_value=0)
    eq = d_all.cumsum()
    cap_used = (F.our_px * F.n).groupby(F.event).sum()
    return {"fills": len(F), "contracts": int(F.n.sum()),
            "c_per_contract": round(100 * F["pnl_$"].sum() / F.n.sum(), 2),
            "pred_edge_c": round((F.pred_edge_c * F.n).sum() / F.n.sum(), 2),
            "fees_$": round(F["fee_$"].sum()), "total_$": round(F["pnl_$"].sum()),
            "$_per_sim_hour": round(F["pnl_$"].sum() / n_hours, 2),
            "max_dd_$": round((eq.cummax() - eq).max()),
            "sharpe": round(d_all.mean() / d_all.std() * np.sqrt(365), 2) if d_all.std() > 0 else np.nan,
            "day_t": round(d.mean() / d.std() * np.sqrt(len(d)), 2) if len(d) > 2 and d.std() > 0 else np.nan,
            "peak_capital_per_hour_$": round(cap_used.max())}


def main():
    data = [x for x in (load(s, p) for s, p in PAIRS.items()) if x is not None]
    M = pd.concat([d[0] for d in data], ignore_index=True)
    T = pd.concat([d[1] for d in data], ignore_index=True)
    Q = pd.concat([d[2] for d in data], ignore_index=True)
    n_hours = M.event.nunique()
    L = [f"# Market-making simulation on the real Kalshi tape (BTC+ETH hourly ranges, {n_hours} sampled hours, "
         f"{M.close.min():%Y-%m-%d} to {M.close.max():%Y-%m-%d})", "",
         f"Taker trades replayed: {len(T)}; minute order-book states: {len(Q)}; margin {MARGIN}c (frozen); "
         f"position cap {POS}/market/side, {EVCAP}/event.", "",
         "Scale: 'per sim hour' x 24 x 30 / sampling = per month if run every hour (data samples every 2nd hour).", ""]
    rows = []
    for compete, lat, qsize, fee_on in itertools.product((0.0, 0.5, 1.0), (2, 10), (25, 100), (True, False)):
        F = simulate(M, T, Q, compete, lat, qsize, fee_on)
        rows.append({"compete": compete, "latency_s": lat, "order_size": qsize, "maker_fee": fee_on, **summary(F, n_hours)})
    G = pd.DataFrame(rows)
    L += ["## Model-driven market maker under different assumptions", "", G.to_markdown(index=False), ""]
    base = dict(compete=0.5, lat=2, qsize=25, fee_on=True)
    B = []
    for name, kw in (("model (base case)", {}),
                     ("model, quote only minutes 0-35 (pre-registered from KXBTCD Jan-Mar)", {"max_mins": 35}),
                     ("no model: quote 1c inside always", {"use_model": False}),
                     ("placebo: model mirrored around the mid", {"flip": True})):
        B.append({"bot": name, **summary(simulate(M, T, Q, **base, **kw), n_hours)})
    L += ["## Baselines (compete 0.5, latency 2 s, size 25, maker fee on)", "", pd.DataFrame(B).to_markdown(index=False), ""]
    F = simulate(M, T, Q, **base)
    for key, lab in ((F.ticker.str[:5], "market"), (pd.cut(F.mins_in, [-1, 9, 20, 30, 40, 50, 60]), "minute of the hour"),
                     (F.side, "side"), (F.day.str[:7], "month"), (pd.cut(F.pred_edge_c, [0, 10, 15, 25, 100]), "predicted edge")):
        g = F.groupby(key, observed=True)
        L += [f"### base case by {lab}", "", pd.DataFrame({"fills": g.size(), "contracts": g.n.sum(),
                                                            "c_per_contract": (100 * g["pnl_$"].sum() / g.n.sum()).round(2),
                                                            "dollars": g["pnl_$"].sum().round(0)}).to_markdown(), ""]
    os.makedirs("../results", exist_ok=True)
    open("../results/SIM_MAKER.md", "w").write("\n".join(L))
    F.to_parquet("data_local/sim_fills_base.parquet")
    print("\n".join(L))


if __name__ == "__main__":
    main()
