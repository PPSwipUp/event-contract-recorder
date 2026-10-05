"""Wide configuration sweep with a strict holdout, plus a study of where the model is (and isn't) accurate.

Periods (fixed in advance):  TRAIN = Aug 2026,  VALID = 1-15 Sep,  HOLDOUT = 16-30 Sep (looked at once, at the end).
Configs: series x minutes-after-open x vol estimator x scale (fixed / rolling) x filter x side x price band x margin.
Selection: rank on TRAIN day-level t (>= 20 bets), confirm on VALID, report the chosen one on HOLDOUT.
Overfitting check: across all configs, does TRAIN performance predict HOLDOUT performance at all?

  python backfill/sweep.py --data out --out results/SWEEP.md
"""
from __future__ import annotations

import argparse
import itertools
import os

import numpy as np
import pandas as pd

import research
from backtest import PAIRS, fee_c, sigmas, hourly

TRAIN, VALID, HOLD = ("2026-08-01", "2026-09-01"), ("2026-09-01", "2026-09-16"), ("2026-09-16", "2026-10-01")
MARGINS = (2, 5, 10)
BANDS = {"all": (0.0, 1.0), "cheap": (0.0, 0.15), "middle": (0.15, 0.85)}       # cost of the contract bought
SIDES = ("both", "yes", "no")


def day_t(day, pnl):
    d = pd.Series(pnl).groupby(np.asarray(day)).sum()
    if len(d) < 3 or d.std() == 0:
        return np.nan, len(d)
    return d.mean() / (d.std(ddof=1) / np.sqrt(len(d))), len(d)


def evaluate(B, p, allow_y, allow_n, margin, band, side):
    ask, bid, y = B.ask.values, B.bid.values, B.y.values
    fy, fn = fee_c(ask, 100), fee_c(1 - bid, 100)
    lo, hi = BANDS[band]
    by = (100 * (p - ask) - fy > margin) & allow_y & (ask >= lo) & (ask < hi) & (side != "no")
    bn = (100 * (bid - p) - fn > margin) & allow_n & (bid > 0) & (1 - bid >= lo) & (1 - bid < hi) & (side != "yes")
    pnl = np.r_[(100 * y - 100 * ask - fy)[by], (100 * (1 - y) - 100 * (1 - bid) - fn)[bn]]
    day = np.r_[B.day.values[by], B.day.values[bn]]
    return day, pnl


def stats(day, pnl, period, excl=None):
    m = (day >= period[0]) & (day < period[1])
    if excl:
        m &= day != excl
    t, nd = day_t(day[m], pnl[m])
    return {"bets": int(m.sum()), "c_per_bet": float(pnl[m].mean()) if m.any() else np.nan,
            "dollars": float(pnl[m].sum()), "t": t}


def calibration(B, p, label):
    mid = ((B.bid + B.ask) / 2).values
    bins = [0, .02, .05, .15, .35, .65, .85, .95, .98, 1.0001]
    g = pd.cut(mid, bins, right=False)
    D = pd.DataFrame({"band": g, "market": mid, "model": p, "won": B.y.values})
    R = D.groupby("band", observed=True).agg(brackets=("won", "size"), market_says=("market", "mean"),
                                             model_says=("model", "mean"), actually_won=("won", "mean"))
    R["market_error"] = (R.market_says - R.actually_won).abs()
    R["model_error"] = (R.model_says - R.actually_won).abs()
    R["closer"] = np.where(R.model_error < R.market_error, "model", "market")
    return [f"### {label}", "", R.round(4).to_markdown(), ""]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="out")
    ap.add_argument("--out", default="results/SWEEP.md")
    a = ap.parse_args()
    rows, L_cal = [], []
    for series, product in PAIRS.items():
        B, z = research.prep(a.data, series, product)
        W, _ = hourly(pd.read_parquet(os.path.join(a.data, f"{product}.parquet")))
        S = sigmas(W)
        B["day"] = B.close.dt.strftime("%Y-%m-%d").values
        mid = ((B.bid + B.ask) / 2).values
        centre = np.where(B.floor.isna(), B.cap, np.where(B.cap.isna(), B.floor, (B.floor + B.cap) / 2))
        for est in ("ppc", "last", "day"):
            raw = S[est].reindex(B.win).values
            ok_tr = W.index < B.win.min()
            kf = float(np.nanmedian(np.abs(W.ret[ok_tr]) / S[est][ok_tr]))
            kr = (np.abs(W.ret) / S[est]).shift(1).rolling(24 * 30, min_periods=24 * 7).median().reindex(B.win).values
            for scale in ("fixed", "rolling"):
                k = np.full(len(B), kf) if scale == "fixed" else np.where(np.isfinite(kr), kr, kf)
                Bx = B.assign(sig_raw=raw)
                p = research.probs(Bx, z, k)
                if est == "ppc" and scale == "fixed":
                    for lag in (1, 15):
                        sel = (B.lag_min == lag).values
                        L_cal += calibration(B[sel], p[sel], f"{series}, {lag} min after open")
                m = research.implied_mult(Bx, z, k).values
                outer = np.abs(np.log(centre) - B.s0.values) / (k * raw * B.left.values) > 1.0
                more, less = m < 1 / 1.2, m > 1.2
                filters = {
                    "none": (p, np.ones(len(B), bool), np.ones(len(B), bool)),
                    "volview": (p, (more & outer) | (less & ~outer), (more & ~outer) | (less & outer)),
                    "shrink25": (mid + 0.25 * (p - mid), np.ones(len(B), bool), np.ones(len(B), bool)),
                    "shrink50": (mid + 0.5 * (p - mid), np.ones(len(B), bool), np.ones(len(B), bool)),
                }
                for lag in (1, 5, 15):
                    sel = (B.lag_min == lag).values
                    Bl = B[sel]
                    for (fname, (pp, ay, an)), margin, band, side in itertools.product(filters.items(), MARGINS, BANDS, SIDES):
                        day, pnl = evaluate(Bl, pp[sel], ay[sel], an[sel], margin, band, side)
                        r = {"series": series, "lag": lag, "vol": est, "scale": scale, "filter": fname,
                             "margin": margin, "band": band, "side": side}
                        for name, per in (("train", TRAIN), ("valid", VALID), ("hold", HOLD)):
                            r.update({f"{name}_{k_}": v for k_, v in stats(day, pnl, per).items()})
                        r["hold_excl28_dollars"] = stats(day, pnl, HOLD, "2026-09-28")["dollars"]
                        rows.append(r)
        print(f"{series}: {len(rows)} configs so far", flush=True)
    R = pd.DataFrame(rows)
    R.to_csv(os.path.join(os.path.dirname(a.out) or ".", "sweep_all.csv"), index=False)

    ok = R[(R.train_bets >= 20) & R.train_t.notna()]
    top = ok.sort_values("train_t", ascending=False).head(25)
    both = ok[(ok.valid_bets >= 10)].assign(tv=lambda d: (d.train_t + d.valid_t.fillna(-9)) / 2)
    pick = both.sort_values("tv", ascending=False).iloc[0]
    rho = ok[["train_t", "hold_t"]].corr(method="spearman").iloc[0, 1]
    rho_v = ok[["train_t", "valid_t"]].corr(method="spearman").iloc[0, 1]
    cols = ["series", "lag", "vol", "scale", "filter", "margin", "band", "side", "train_bets", "train_c_per_bet",
            "train_t", "valid_bets", "valid_c_per_bet", "valid_t", "hold_bets", "hold_c_per_bet", "hold_dollars",
            "hold_t", "hold_excl28_dollars"]
    L = ["# Wide sweep with a holdout", "",
         f"{len(R)} configurations. TRAIN = August, VALID = 1-15 Sep, HOLDOUT = 16-30 Sep. t = day-level t-statistic.", "",
         "## Does doing well in training predict the holdout? (if not, the 'best' configs are luck)", "",
         f"Rank correlation, train t vs validation t: **{rho_v:.2f}**; train t vs holdout t: **{rho:.2f}** "
         f"(0 = no relation, 1 = perfect), over {len(ok)} configs with >= 20 training bets.", "",
         f"Holdout cents/bet: top-25 by training {top.hold_c_per_bet.mean():.2f} vs all configs {ok.hold_c_per_bet.mean():.2f}.", "",
         "## Chosen config (best average of train and validation t), then its holdout", "",
         pd.DataFrame([pick[cols]]).round(2).to_markdown(index=False), "",
         "## Top 25 by training t, with what happened next", "", top[cols].round(2).to_markdown(index=False), "",
         "## Where is the model more accurate than the market? (calibration by the market's price)", "",
         "market_says / model_says = average probability given; actually_won = how often it won; lower error is better.", ""]
    L += L_cal
    open(a.out, "w").write("\n".join(L))
    print("\n".join(L[:14]))


if __name__ == "__main__":
    main()
