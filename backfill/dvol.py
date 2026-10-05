"""Does Deribit's implied volatility index (DVOL) improve the range bot's next-hour volatility forecast?

Next-hour realised vol (from Coinbase 1-min) vs: ppc forecast alone, and ppc + DVOL known at the start of the hour
(DVOL hourly close of the previous hour).  Linear fit in log space on 2025, scored once on 2026 (MSE of log rv and
QLIKE on the hour's return).  Only if DVOL clearly helps out of sample is it worth wiring into the bot.
  python backfill/dvol.py
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from backtest import hourly, sigmas
from collect import coinbase

CACHE = "data_local"


def spot(product):
    p = f"{CACHE}/spot_{product}.parquet"
    if not os.path.exists(p):
        coinbase(product, datetime(2024, 6, 1, tzinfo=timezone.utc), datetime.now(timezone.utc)).to_parquet(p)
    return pd.read_parquet(p)


def main():
    D = pd.read_parquet(f"{CACHE}/dvol.parquet")
    L = ["# DVOL as an extra input to the next-hour volatility forecast", "",
         "Fit on 2025, scored on 2026-01..09. log_rv = a + b*log(ppc) [+ c*log(DVOL hourly)].", ""]
    rows = []
    for cur, product in (("BTC", "BTC-USD"), ("ETH", "ETH-USD")):
        W, _ = hourly(spot(product))
        S = sigmas(W)
        dv = D[D.cur == cur].set_index("t").dvol
        X = pd.DataFrame({"lrv": np.log(W.rv.clip(lower=1e-6)), "ret": W.ret, "lppc": np.log(S.ppc),
                          "ldv": np.log(dv / 100 / np.sqrt(8760)).shift(1).reindex(W.index)}).dropna()
        tr, te = X[(X.index >= "2025-01-01") & (X.index < "2026-01-01")], X[X.index >= "2026-01-01"]
        for name, cols in (("ppc", ["lppc"]), ("dvol only", ["ldv"]), ("ppc + dvol", ["lppc", "ldv"])):
            A = np.c_[np.ones(len(tr)), tr[cols]]
            b = np.linalg.lstsq(A, tr.lrv, rcond=None)[0]
            res_tr = tr.lrv - A @ b
            pred = np.c_[np.ones(len(te)), te[cols]] @ b
            sig = np.exp(pred + res_tr.var() / 2)                     # mean of lognormal rv
            q = (te.ret ** 2 / sig ** 2 + np.log(sig ** 2)).mean()
            rows.append({"asset": cur, "model": name, "coef": np.round(b, 3).tolist(),
                         "test_mse_logrv": round(float(((te.lrv - pred) ** 2).mean()), 4), "test_qlike": round(float(q), 4),
                         "n_test": len(te)})
    L += [pd.DataFrame(rows).to_markdown(index=False), ""]
    open("../results/DVOL.md", "w").write("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    main()
