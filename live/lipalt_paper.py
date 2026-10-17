"""PAPER-ONLY alt-data LIP forward bot (results/PLAN_LIP_ALTDATA.md): live/lipgen_paper.py (GenBot, per-window accounting, settlement marking)
reading live/lipalt/ written by live/lipalt_rec.py, output live/lipalt_paper.jsonl.  Own api gap 1.4 s (<= 0.7 req/s).  No orders, no keys.
  .venv/bin/python -u live/lipalt_paper.py"""
from __future__ import annotations

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kxlipbook as KL  # noqa: E402
import lipgen_paper as GP  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.path.join(HERE, "lipalt"))
    ap.add_argument("--out", default=os.path.join(HERE, "lipalt_paper.jsonl"))
    ap.add_argument("--max-seconds", type=float, default=None)
    ap.add_argument("--sweep", type=float, default=15.0)
    ap.add_argument("--summary-every", type=float, default=3600.0)
    a = ap.parse_args()
    a.series = GP.AnySeries()
    api = KL.Api(gap=1.4)
    api.s.headers["User-Agent"] = "lipalt-readonly/1.0"
    GP.GenBot(a, api).run(a.max_seconds)


if __name__ == "__main__":
    main()
