"""Family filter for the F4E LIP forward twin (results/PLAN_LIP_F4E_FWD.md): every live liquidity program of the 123 frozen series in
live/lipf4e_series.json (Kalshi Economics series settling on NY Fed or BLS, rates series removed).  Same draw-file shapes as live/lipalt_draw.py.
Public GET only, no orders.   python live/lipf4e_draw.py   (prints the current family count)"""
from __future__ import annotations

import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kxlipbook as KL  # noqa: E402
import lipalt_draw as AD  # noqa: E402
import lipgen_draw as LD  # noqa: E402

DRAW_FILE = os.path.join(HERE, "lipf4e_draw.jsonl")
import json  # noqa: E402
F4E = set(json.load(open(os.path.join(HERE, "lipf4e_series.json"))))
CPI = {"KXCPI", "KXCPICOMBO", "KXCPICORE", "KXCPICOREYOY", "KXCPIYOY", "KXLCPIMAXYOY", "KXGROCERYCPI", "KXPCEHEAD"}


def sub_of(series):
    """sub-family label (descriptive only): CPI = inflation prints, OTH = every other frozen series."""
    return None if series not in F4E else "CPI" if series in CPI else "OTH"


def family_live(rows, now):
    out = []
    for r in rows:
        if r.get("incentive_type") != "liquidity" or r.get("paid_out"):
            continue
        sb = sub_of(KL.series_of(r["market_ticker"]))
        s0, s1 = KL.iso_ts(r.get("start_date", "")), KL.iso_ts(r.get("end_date", ""))
        if sb and s0 is not None and s1 is not None and s0 <= now + AD.LEAD_S and s1 > now:
            out.append(dict(r, cat=sb))
    return sorted(out, key=lambda r: r["id"])


class FamilyDraw(AD.FamilyDraw):
    def __init__(self, path=DRAW_FILE):
        super().__init__(path)

    def maintain(self, rows, now, cat_of_series=None, open_ok=None):
        by_id = {r["id"]: r for r in rows}
        new = []
        for pid in sorted(self.active):
            cur = by_id.get(pid)
            if cur is None or cur.get("paid_out") or (KL.iso_ts(cur["end_date"]) or 0) <= now:
                self._append({"k": "end", "ts": now, "id": pid})
        for r in family_live(rows, now):
            if r["id"] not in self.active and r["id"] not in self.ever:
                self._append({"k": "add", "ts": now, "program": r})
                new.append(r)
        return new


if __name__ == "__main__":
    api = KL.Api(gap=0.5)
    rows = LD.pull_programs(api)
    if rows is None:
        sys.exit("program pull failed")
    f = family_live(rows, time.time())
    print(len(f), "live F4E programs;", len({KL.series_of(r["market_ticker"]) for r in f}), "series;",
          {k: sum(r["cat"] == k for r in f) for k in ("CPI", "OTH")})
