"""Related-market early warning for Polymarket US day-of quoting (results/PLAN_PMUS_LEAD.md, frozen).
  python backfill/pmuslead.py --days 2026-10-06,2026-10-07
"""
from __future__ import annotations

import argparse
import glob
import math
import os
import re

import numpy as np
import pandas as pd

import pmusday as P

LEAD_MOVE, FOLLOW_MOVE, PULL_S = 0.02, 0.03, 600
LEADER = ("aec-", "asc-", "tsc-")


def game_of(slug):
    m = re.search(r"((?:mlb|nhl)-[a-z]+-[a-z]+-\d{4}-\d\d-\d\d)", slug)
    return m.group(1) if m else None


def load(days):
    prog = pd.concat([pd.read_csv(f) for f in sorted(glob.glob(f"{P.REC}/programs_*.csv"))]).drop_duplicates(["slug", "period"])
    prog = prog[(prog.period == "day_of") & prog.slug.str.contains("|".join(days))].copy()
    prog["game"] = prog.slug.map(game_of)
    prog = prog.dropna(subset=["game"])
    prog["n_markets"] = prog.groupby("program").slug.transform("nunique")
    prog = prog.set_index("slug")
    files = sorted({f for d in days for f in glob.glob(f"{P.REC}/{d}.jsonl")} |
                   {f"{P.REC}/{(pd.Timestamp(d) + pd.Timedelta(days=1)).date()}.jsonl" for d in days} & set(glob.glob(f"{P.REC}/*.jsonl")))
    B = pd.concat([pd.read_json(f, lines=True) for f in files])
    B = B[B.slug.isin(prog.index)].drop_duplicates(["slug", "ts"]).sort_values(["slug", "ts"])
    B["game"] = B.slug.map(prog.game)
    B["start"] = B.slug.map(prog.start)
    B = B[(B.ts >= B.start - P.PERIOD_S) & (B.ts < B.start)]
    B["mid"] = (B.bids.map(lambda x: x[0][0] if x else np.nan) + B.offers.map(lambda x: x[0][0] if x else np.nan)) / 2
    B["touch_size"] = B.bids.map(lambda x: x[0][1] if x else 0) + B.offers.map(lambda x: x[0][1] if x else 0)
    B["leader"] = B.slug.str.startswith(LEADER)
    B["move"] = B.groupby("slug").mid.diff().abs()
    first = B[~B.leader].groupby("slug").first()
    thin = set()
    for _, f in first.groupby("game"):
        thin |= set(f[f.touch_size <= f.touch_size.quantile(0.2)].index)
    return prog, B, thin


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", required=True)
    a = ap.parse_args()
    days = a.days.split(",")
    prog, B, thin = load(days)
    L = [f"# Related-market early warning (PLAN_PMUS_LEAD.md), days {a.days}", "",
         f"Games: {B.game.nunique()}; snapshots: {len(B)}; leader markets: {B[B.leader].slug.nunique()}; thin follower set: {len(thin)}", ""]
    # 1) prediction: 30-s buckets per game
    B["slot"] = (B.ts // 30).astype(int)
    rows = []
    for g, G in B.groupby("game"):
        lead = G[G.leader].groupby("slot").move.max().fillna(0) >= LEAD_MOVE - 1e-9
        foll = G[~G.leader].groupby("slot").move.max().fillna(0) >= FOLLOW_MOVE - 1e-9
        idx = sorted(set(lead.index) | set(foll.index))
        lead, foll = lead.reindex(idx, fill_value=False), foll.reindex(idx, fill_value=False)
        nxt = foll.shift(-1, fill_value=False)
        rows.append({"game": g, "slots": len(idx), "leader_moves": int(lead.sum()),
                     "P(prop jump next | leader moved)": round(nxt[lead].mean(), 3) if lead.any() else np.nan,
                     "P(prop jump next | no leader move)": round(nxt[~lead].mean(), 3)})
    L += ["## 1) Do leader moves precede prop jumps? (next 30-s slot)", "", pd.DataFrame(rows).to_markdown(index=False), ""]
    # 2-3) C vs C_lead
    pulls = {}
    for g, G in B[B.leader].groupby("game"):
        pulls[g] = [(t, t + PULL_S) for t in sorted(G.ts[G.move >= LEAD_MOVE - 1e-9])]
    res, fl = [], []
    for name in ("C", "C_lead"):
        for slug, M in B[~B.leader].groupby("slug"):
            g = M.game.iloc[0]
            o = P.run(M, prog, "C", thin, pulls.get(g, []), pull_any=(name == "C_lead"))
            if not o["fills"] and o["reward"] == 0:
                continue
            close = M.mid.dropna().iloc[-1]
            clv = 0.0
            for ts, side, px in o["fills"]:
                s = 1 if side == "buy" else -1
                fl.append({"variant": name, "game": g, "slug": slug, "clv": s * (close - px)})
                clv += s * P.SIZE * (close - px)
            res.append({"variant": name, "game": g, "reward": o["reward"], "rebate": o["rebate"], "fills_at_close": clv,
                        "fills": len(o["fills"])})
    R = pd.DataFrame(res)
    S = R.groupby(["variant", "game"]).sum(numeric_only=True)
    S["net_outcome_free"] = S.reward + S.rebate + S.fills_at_close
    F = pd.DataFrame(fl)
    clv = []
    for v, G in F.groupby("variant"):
        g = (G.clv - G.clv.mean()).groupby(G.slug).sum()
        se = math.sqrt((g ** 2).sum()) / len(G)
        clv.append({"variant": v, "fills": len(G), "clv_c": round(100 * G.clv.mean(), 2), "t": round(G.clv.mean() / se, 2) if se else np.nan})
    L += ["## 2) Fills: closing-line value (cents/contract, t clustered by market)", "", pd.DataFrame(clv).to_markdown(index=False), "",
          "## 3) Outcome-free money per game ($): rewards + rebate + fills valued at the closing line", "", S.round(2).to_markdown(), ""]
    mlb = S.xs("C_lead", level="variant")
    mlb = mlb[mlb.index.str.startswith("mlb")]
    c_lead_clv = next((r["clv_c"] for r in clv if r["variant"] == "C_lead"), np.nan)
    ok = c_lead_clv > 0 and (mlb.net_outcome_free > 0).sum() > len(mlb) / 2
    L += [f"GATE (MLB games): C_lead CLV {c_lead_clv}c, net>0 in {(mlb.net_outcome_free > 0).sum()}/{len(mlb)} games -> {'PASS' if ok else 'FAIL'}", ""]
    out = "\n".join(L)
    open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results", "PMUS_LEAD.md"), "w").write(out)
    print(out)


if __name__ == "__main__":
    main()
