"""Where do the simulator's losses come from?  Same data/model as simmaker.py, base case (compete 0.5, lat 2 s, size 25).
Variants: naive fills only (no crossing / no pick-off) = the old backtest's assumption; + crossing; + pick-off; all.
  python backfill/simdiag.py
"""
import numpy as np
import pandas as pd

import simmaker as sm

data = [x for x in (sm.load(s, p) for s, p in sm.PAIRS.items()) if x is not None]
M = pd.concat([d[0] for d in data], ignore_index=True)
T = pd.concat([d[1] for d in data], ignore_index=True)
Q = pd.concat([d[2] for d in data], ignore_index=True)
n_hours, days = M.close.nunique(), sorted(M.close.dt.strftime("%Y-%m-%d").unique())
rows = []
for name, kw in (("naive: only takers on our side, print-sized", dict(cross_fill=0.0, pickoff_c=None)),
                 ("+ pick-off of whole order on prints >=3c through", dict(cross_fill=0.0, pickoff_c=3)),
                 ("+ other traders' orders crossing us (50%)", dict(cross_fill=0.5, pickoff_c=None)),
                 ("all (base case)", dict(cross_fill=1.0, pickoff_c=3))):
    for mm in (60, 21):
        F = sm.simulate(M, T, Q, compete=0.5, lat=2, qsize=25, fee_on=True, max_mins=mm, **kw)
        if mm == 21:
            F = F[F.mins_in >= 10] if len(F) else F
        s = sm.summary(F, n_hours, days)
        rows.append({"fill rule": name, "minutes": "10-20" if mm == 21 else "all", **{k: s.get(k) for k in
                     ("fills", "contracts", "c_per_contract", "pred_edge_c", "$_per_month_if_every_hour", "day_t")}})
print(pd.DataFrame(rows).to_markdown(index=False))
