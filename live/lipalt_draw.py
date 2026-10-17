"""Family filter for the alt-data LIP forward twin (results/PLAN_LIP_ALTDATA.md, 'Forward' paragraph).  Replaces the seeded random draw of
live/lipgen_draw.py: EVERY live liquidity program whose series matches ^KX[A-Z0-9]+(APP|FT|CC)$ (excl. MENTION / LEAD / SWIFT / KXLYFT) is tracked.
Append-only live/lipalt_draw.jsonl (same shapes lipgen_summary.py reads):
  {"k":"add","ts","program":{row..,"cat":"APP|FT|CC"}}     program became live (started, or starts within 10 min)
  {"k":"end","ts","id"}                                    program ended / vanished / paid out
Public GET only, no orders.   .venv/bin/python live/lipalt_draw.py   (prints the current family count)"""
from __future__ import annotations

import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kxlipbook as KL  # noqa: E402
import lipgen_draw as LD  # noqa: E402

DRAW_FILE = os.path.join(HERE, "lipalt_draw.jsonl")
PAT = re.compile(r"^KX[A-Z0-9]+(APP|FT|CC)$")
LEAD_S = 600.0


def sub_of(series):
    """'APP'|'FT'|'CC' if the series is in the family (plan rule), else None."""
    m = PAT.match(series)
    if not m or any(x in series for x in ("MENTION", "LEAD", "SWIFT")) or series == "KXLYFT":
        return None
    return m.group(1)


def family_live(rows, now):
    out = []
    for r in rows:
        if r.get("incentive_type") != "liquidity" or r.get("paid_out"):
            continue
        sb = sub_of(KL.series_of(r["market_ticker"]))
        s0, s1 = KL.iso_ts(r.get("start_date", "")), KL.iso_ts(r.get("end_date", ""))
        if sb and s0 is not None and s1 is not None and s0 <= now + LEAD_S and s1 > now:
            out.append(dict(r, cat=sb))
    return sorted(out, key=lambda r: r["id"])


class FamilyDraw(LD.Draw):
    def __init__(self, path=DRAW_FILE):
        self.ever = set()
        super().__init__(path)

    def _apply(self, o):
        if o["k"] == "add":
            p = o["program"]
            self.drawn[p["id"]] = p
            self.active[p["id"]] = p
            self.ever.add(p["id"])
        else:
            super()._apply(o)

    @property
    def initialised(self):
        return True                                              # no seeded draw to protect: the family rule is the universe

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
    print(len(f), "live family programs;", len({KL.series_of(r["market_ticker"]) for r in f}), "series;",
          {k: sum(r["cat"] == k for r in f) for k in ("APP", "FT", "CC")})
