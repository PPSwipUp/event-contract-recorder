"""Skill or luck? Closing-line test of the Polymarket US day-of fills (variants B/C/D of PLAN_PMUS.md).

The closing price (last recorded mid before first pitch) is the best outcome-free estimate of each prop's probability.
Per fill: signed value vs the mid at +5 m, +30 m, +60 m and at close (positive = good for us).  Expected P&L at close
= sum over markets of (cash + inventory x closing mid); realised = the same with the settlement value.
realised - expected = outcome noise; its z-score uses Bernoulli variance inv^2 x p(1-p) per market (independence
assumed, so |z| is overstated: props of one game are correlated).
  python backfill/pmusclv.py --day 2026-10-05
"""
from __future__ import annotations

import argparse
import glob
import math

import numpy as np
import pandas as pd

import pmusday as P


def load(day):
    prog = pd.concat([pd.read_csv(f) for f in sorted(glob.glob(f"{P.REC}/programs_*.csv"))]).drop_duplicates(["slug", "period"])
    prog = prog[(prog.period == "day_of") & prog.slug.str.contains(day)].copy()
    prog["game"] = prog.slug.map(P.game_of)
    prog["n_markets"] = prog.groupby("program").slug.transform("nunique")
    prog = prog.set_index("slug")
    B = pd.read_json(f"{P.REC}/{day}.jsonl", lines=True)
    B = B[B.slug.isin(prog.index)].sort_values(["slug", "ts"])
    B["game"] = B.slug.map(P.game_of)
    B["start"] = B.slug.map(prog.start)
    B = B[(B.ts >= B.start - P.PERIOD_S) & (B.ts < B.start)]
    B["mid"] = (B.bids.map(lambda x: x[0][0] if x else np.nan) + B.offers.map(lambda x: x[0][0] if x else np.nan)) / 2
    B["touch_size"] = B.bids.map(lambda x: x[0][1] if x else 0) + B.offers.map(lambda x: x[0][1] if x else 0)
    first = B.groupby("slug").first()
    thin = set()
    for _, f in first.groupby("game"):
        thin |= set(f[f.touch_size <= f.touch_size.quantile(0.2)].index)
    return prog, B, thin


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", default="2026-10-05")
    a = ap.parse_args()
    prog, B, thin = load(a.day)
    settle, fills, mk = {}, [], []
    for v in "BCD":
        for slug, M in B.groupby("slug"):
            o = P.run(M, prog, v, thin, [])
            if not o["fills"]:
                continue
            if slug not in settle:
                settle[slug] = P.settlement(slug)
            mids = M.dropna(subset=["mid"])
            close = mids.mid.iloc[-1]
            for ts, side, px in o["fills"]:
                sgn = 1 if side == "buy" else -1
                r = {"variant": v, "game": M.game.iloc[0], "slug": slug, "side": side, "px": px, "close": close,
                     "settle": settle[slug], "prop": slug.split("-2026-10-05-")[-1].split("-")[0]}
                for k, h in (("5m", 300), ("30m", 1800), ("60m", 3600)):
                    later = mids[mids.ts >= ts + h].mid
                    r[f"mo_{k}"] = sgn * (later.iloc[0] - px) if len(later) else sgn * (close - px)
                r["mo_close"] = sgn * (close - px)
                r["mo_settle"] = sgn * (settle[slug] - px) if settle[slug] is not None else np.nan
                fills.append(r)
            mk.append({"variant": v, "game": M.game.iloc[0], "slug": slug, "inv": o["inv"], "cash": o["cash"], "close": close,
                       "settle": settle[slug]})
    F, K = pd.DataFrame(fills), pd.DataFrame(mk)
    L = ["# Skill or luck? Closing-line test of Polymarket US day-of fills (B/C/D, PLAN_PMUS.md)", ""]
    # 3) data checks first
    sv = pd.Series(settle).dropna()
    L += [f"Data checks: settlement values seen {sorted(sv.unique().tolist())} over {len(sv)} markets (missing {sum(v is None for v in settle.values())}); "
          f"fills per variant {F.variant.value_counts().to_dict()}", ""]
    # 1) mark-out curve (cents per contract, mean and t over fills; clustered by market)
    rows = []
    for v, G in F.groupby("variant"):
        r = {"variant": v, "fills": len(G)}
        for c in ("mo_5m", "mo_30m", "mo_60m", "mo_close", "mo_settle"):
            x = G[c].dropna()
            g = (x - x.mean()).groupby(G.loc[x.index, "slug"]).sum()
            se = math.sqrt((g ** 2).sum()) / len(x) if len(x) else np.nan
            r[c + "_c"] = round(100 * x.mean(), 2)
            r[c + "_t"] = round(x.mean() / se, 2) if se else np.nan
        rows.append(r)
    L += ["## 1) Mark-out curve: cents per contract after the fill (+ = good for us), t clustered by market", "",
          pd.DataFrame(rows).to_markdown(index=False), ""]
    # 2) expected (closing line) vs realised (settlement)
    rows = []
    for v, G in K.dropna(subset=["settle"]).groupby("variant"):
        exp_ = (G.cash + G.inv * G.close).sum()
        real = (G.cash + G.inv * G.settle).sum()
        sd = math.sqrt((G.inv ** 2 * G.close * (1 - G.close)).sum())
        rows.append({"variant": v, "markets": len(G), "expected_at_close_$": round(exp_), "realised_settle_$": round(real),
                     "luck_$": round(real - exp_), "luck_z (indep., overstated)": round((real - exp_) / sd, 2) if sd else np.nan})
    L += ["## 2) Expected P&L at the closing line vs realised at settlement (fills only, before rewards/rebate)", "",
          pd.DataFrame(rows).to_markdown(index=False), ""]
    # 4) where the settlement profit came from
    F["longshot"] = np.where(F.px < 0.25, "<25c", np.where(F.px > 0.75, ">75c", "25-75c"))
    by = F.groupby(["variant", "side", "longshot"]).agg(fills=("px", "size"), clv_c=("mo_close", "mean"), settle_c=("mo_settle", "mean"))
    by[["clv_c", "settle_c"]] *= 100
    L += ["## 4) By side and price band: closing-line value vs settlement value (cents/contract)", "", by.round(2).to_markdown(), ""]
    byp = F[F.variant == "C"].groupby("prop").agg(fills=("px", "size"), clv_c=("mo_close", "mean"), settle_c=("mo_settle", "mean"))
    byp[["clv_c", "settle_c"]] *= 100
    L += ["## 4b) Variant C by prop type", "", byp.sort_values("fills", ascending=False).round(2).to_markdown(), ""]
    out = "\n".join(L)
    open("../results/PMUS_CLV.md", "w").write(out)
    print(out)


if __name__ == "__main__":
    main()
