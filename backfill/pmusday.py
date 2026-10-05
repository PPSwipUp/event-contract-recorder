"""Score the five frozen Polymarket US liquidity-incentive variants (results/PLAN_PMUS.md) on recorded day-of books.
  python backfill/pmusday.py --day 2026-10-05
A program's pool is shared across ALL of that program's markets (polymarket.us/rewards lists e.g. the MLB WC player-
props day-of program as one $850 pool over 483 markets spanning both games), as PLAN_PMUS.md specifies.
"""
from __future__ import annotations

import argparse
import glob
import os
import re

import numpy as np
import pandas as pd
import requests

import dohfix  # noqa: F401

REC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "live", "pmusrec")
SIZE, TICK, CAP, COOL, DT_MAX = 500.0, 0.01, 1000.0, 300, 90
PERIOD_S = 6 * 3600


def game_of(slug):
    m = re.search(r"mlb-([a-z]+-[a-z]+-\d{4}-\d\d-\d\d)", slug)
    return m.group(1) if m else None


def settlement(slug):
    try:
        r = requests.get(f"https://gateway.polymarket.us/v1/markets/{slug}/settlement", timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        return float(r.json()["settlement"]) if r.status_code == 200 else None
    except (requests.RequestException, KeyError, ValueError):
        return None


def side_share(levels, ours_px, target, disc, bid):
    """levels best first [(px, qty)]; our SIZE at ours_px at the back of its level. -> (our share, qualifies)"""
    better = (lambda p: p >= ours_px - 1e-9) if bid else (lambda p: p <= ours_px + 1e-9)
    lv = [(p, q, False) for p, q in levels if better(p)] + [(ours_px, SIZE, True)] + [(p, q, False) for p, q in levels if not better(p)]
    best = lv[0][0]
    mine = comp = cum = 0.0
    for p, q, is_ours in lv:
        take = min(q, target - cum)
        if take <= 0:
            break
        w = disc ** round(abs(best - p) / TICK) * take
        mine, comp = (mine + w, comp) if is_ours else (mine, comp + w)
        cum += take
    ok = cum >= target - 1e-9
    return (mine / (mine + comp) if ok and mine + comp > 0 else 0.0), ok


def run(B, prog, variant, thin, pulls):
    """B: one market's snapshots (sorted). Returns dict of totals for this market."""
    slug = B.slug.iloc[0]
    pr = prog.loc[slug]
    start = pr.start
    out = {"reward": 0.0, "rebate": 0.0, "fills": [], "quoted_s": 0.0, "capital": 0.0}
    if variant != "A" and slug not in thin:
        return out
    inv = cash = 0.0
    cool = {"bid": -1, "offer": -1}
    rows = B.to_dict("records")
    for i, r in enumerate(rows[:-1]):
        t, nxt = r["ts"], rows[i + 1]
        dt = min(nxt["ts"] - t, DT_MAX)
        if variant in "DE" and t >= start - 3 * 3600:
            break
        if variant == "E" and any(a <= t < b for a, b in pulls):
            continue
        bids, offers = [tuple(x) for x in r["bids"]], [tuple(x) for x in r["offers"]]
        q = {}
        if bids and t >= cool["bid"] and inv < CAP:
            q["bid"] = round(bids[0][0] - (TICK if variant in "CDE" else 0), 4)
        if offers and t >= cool["offer"] and inv > -CAP:
            q["offer"] = round(offers[0][0] + (TICK if variant in "CDE" else 0), 4)
        q = {k: v for k, v in q.items() if 0 < v < 1}
        if not q:
            continue
        out["quoted_s"] += dt
        out["capital"] = max(out["capital"], SIZE * (q.get("bid", 0) + (1 - q["offer"] if "offer" in q else 0)))
        slice_ = pr.pool * dt / PERIOD_S / (2 * pr.n_markets)
        for k, lv, isbid in (("bid", bids, True), ("offer", offers, False)):
            if k in q:
                sh, _ = side_share(lv, q[k], pr.target, pr.disc, isbid)
                out["reward"] += sh * slice_
        traded = float(nxt["shares_traded"] or 0) > float(r["shares_traded"] or 0)
        nb, no = nxt["bids"], nxt["offers"]
        if "bid" in q and traded and (not nb or nb[0][0] < q["bid"] - 1e-9):
            inv += SIZE; cash -= SIZE * q["bid"]; cool["bid"] = nxt["ts"] + COOL
            out["rebate"] += 0.0125 * SIZE * q["bid"] * (1 - q["bid"])
            out["fills"].append((nxt["ts"], "buy", q["bid"]))
        if "offer" in q and traded and (not no or no[0][0] > q["offer"] + 1e-9):
            inv -= SIZE; cash += SIZE * q["offer"]; cool["offer"] = nxt["ts"] + COOL
            out["rebate"] += 0.0125 * SIZE * q["offer"] * (1 - q["offer"])
            out["fills"].append((nxt["ts"], "sell", q["offer"]))
    out["inv"], out["cash"] = inv, cash
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", default="2026-10-05")
    a = ap.parse_args()
    prog = pd.concat([pd.read_csv(f) for f in sorted(glob.glob(f"{REC}/programs_*.csv"))]).drop_duplicates(["slug", "period"])
    prog = prog[prog.period == "day_of"].copy()
    prog["game"] = prog.slug.map(game_of)
    prog["n_markets"] = prog.groupby("program").slug.transform("nunique")
    prog = prog.set_index("slug")
    B = pd.read_json(f"{REC}/{a.day}.jsonl", lines=True)
    B = B[B.slug.isin(prog.index)].sort_values(["slug", "ts"])
    B["game"] = B.slug.map(game_of)
    B["start"] = B.slug.map(prog.start)
    B = B[(B.ts >= B.start - PERIOD_S) & (B.ts < B.start)]
    bb = B.bids.map(lambda x: x[0][0] if x else np.nan)
    bo = B.offers.map(lambda x: x[0][0] if x else np.nan)
    B["mid"] = (bb + bo) / 2
    B["touch_size"] = B.bids.map(lambda x: x[0][1] if x else 0) + B.offers.map(lambda x: x[0][1] if x else 0)
    first = B.groupby("slug").first()
    thin = set()
    for g, f in first.groupby("game"):
        thin |= set(f[f.touch_size <= f.touch_size.quantile(0.2)].index)
    pulls = {}
    for g, G in B.groupby("game"):
        mv = G.groupby("slug").mid.diff().abs()
        pulls[g] = [(t, t + 600) for t in sorted(G.ts[mv >= 0.03 - 1e-9])]
    settle = {}
    rows, fills = [], []
    for v in "ABCDE":
        for slug, M in B.groupby("slug"):
            g = M.game.iloc[0]
            o = run(M, prog, v, thin, pulls[g])
            if not o["fills"] and o["reward"] == 0:
                continue
            fill_pnl = 0.0
            if o["fills"]:
                if slug not in settle:
                    settle[slug] = settlement(slug)
                mark = settle[slug] if settle[slug] is not None else M.mid.dropna().iloc[-1]
                fill_pnl = o["cash"] + o["inv"] * mark
                for ts, side, px in o["fills"]:
                    later = M[M.ts >= ts + 300].mid.dropna()
                    mo = (later.iloc[0] - px if side == "buy" else px - later.iloc[0]) if len(later) else np.nan
                    fills.append({"variant": v, "game": g, "slug": slug, "side": side, "px": px, "markout_5m_c": 100 * mo,
                                  "settled": settle[slug] is not None})
            rows.append({"variant": v, "game": g, "slug": slug, "reward": o["reward"], "rebate": o["rebate"], "fill_pnl": fill_pnl,
                         "fills": len(o["fills"]), "quoted_h": o["quoted_s"] / 3600, "capital": o["capital"]})
    R = pd.DataFrame(rows)
    R["net"] = R.reward + R.rebate + R.fill_pnl
    S = R.groupby(["variant", "game"]).agg(markets=("slug", "nunique"), reward=("reward", "sum"), rebate=("rebate", "sum"),
                                           fill_pnl=("fill_pnl", "sum"), net=("net", "sum"), fills=("fills", "sum"),
                                           capital=("capital", "sum"), quoted_h=("quoted_h", "max")).round(2)
    S["net_per_h"] = (S.net / S.quoted_h.replace(0, np.nan)).round(2)
    F = pd.DataFrame(fills)
    comp = B.groupby([B.game, (B.start - B.ts) // 3600]).touch_size.median().unstack(0).round(0)
    L = ["# Polymarket US liquidity incentives: five frozen variants on recorded day-of books (PLAN_PMUS.md)", "",
         f"Day {a.day}; markets recorded in window: {B.slug.nunique()}; snapshots: {len(B)}; thin set: {len(thin)} markets",
         "Pools shared across all of a program's markets (both games), per the rewards page.  "
         "Fills are a book-based proxy (no public trade feed).", "",
         "## Per variant and game ($)", "", S.to_markdown(), ""]
    if len(F):
        L += ["## Fills", "", F.groupby(["variant", "game"]).agg(n=("px", "size"), markout_5m_c=("markout_5m_c", "mean"),
                                                                   settled_share=("settled", "mean")).round(2).to_markdown(), ""]
    L += ["## Median size at best bid + best offer (others), by hours before start", "", comp.to_markdown(), ""]
    pos = S.net.unstack("game")
    L += ["First read (frozen rule: a variant must be net positive in both games to justify 5 more game days): " +
          ", ".join(f"{v}: {'both +' if (pos.loc[v] > 0).all() else 'no'}" for v in pos.index), ""]
    open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results", "PMUS_DAY.md"), "w").write("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    main()
