"""How much settled history does Kalshi have for each price-range / above-below series?

  python backfill/survey.py SERIES [SERIES ...] --out survey.csv
For each series: settled markets (live + historical API), distinct events, first and last close, total volume.
"""
from __future__ import annotations

import argparse
import sys

import pandas as pd

from collect import K, get


def survey(series):
    n, events, first, last, vol = 0, set(), None, None, 0.0
    for base in (f"{K}/markets", f"{K}/historical/markets"):
        cursor = None
        while True:
            p = {"series_ticker": series, "limit": 1000}
            if base.endswith("/markets") and "historical" not in base:
                p["status"] = "settled"
            if cursor:
                p["cursor"] = cursor
            d = get(base, **p) or {}
            ms = d.get("markets", [])
            for m in ms:
                n += 1
                events.add(m["event_ticker"])
                c = m.get("close_time")
                first = c if first is None or c < first else first
                last = c if last is None or c > last else last
                vol += float(m.get("volume_fp") or m.get("volume") or 0)
            cursor = d.get("cursor")
            if not cursor or not ms:
                break
    return {"series": series, "markets": n, "events": len(events), "first_close": first, "last_close": last,
            "contracts_traded": vol}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("series", nargs="+")
    ap.add_argument("--out", default="survey.csv")
    a = ap.parse_args()
    rows = []
    for s in a.series:
        r = survey(s)
        print(r, flush=True)
        rows.append(r)
    pd.DataFrame(rows).to_csv(a.out, index=False)


if __name__ == "__main__":
    main()
