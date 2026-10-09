"""Scheduled US macro releases (results/PLAN_PMLP_EVENT.md).  Dates copied from quant-research v2/brain/trading/events.py
(federalreserve.gov FOMC calendar, bls.gov CPI + Employment Situation schedules) plus FOMC 2026-12-09.
event_pull(ts, question): True on an event day or the day after (US Eastern calendar days) for a rates-sensitive market.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

_ET = ZoneInfo("America/New_York")
FOMC = ["2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17", "2026-07-29", "2026-09-16", "2026-10-28", "2026-12-09"]
CPI = ["2026-01-13", "2026-02-13", "2026-03-11", "2026-04-10", "2026-05-12", "2026-06-10", "2026-07-14",
       "2026-08-12", "2026-09-11", "2026-10-14"]
NFP = ["2026-01-09", "2026-02-11", "2026-03-06", "2026-04-03", "2026-05-08", "2026-06-05", "2026-07-02",
       "2026-08-07", "2026-09-04", "2026-10-02"]
_DAYS = {date.fromisoformat(d) + timedelta(days=k) for d in FOMC + CPI + NFP for k in (0, 1)}
RATES = re.compile(r"\bfed\b|federal reserve|interest rate|fomc|\bcpi\b|inflation|rate cut|rate hike|powell", re.I)


def event_pull(ts, question):
    """ts: unix seconds"""
    return bool(RATES.search(question or "")) and datetime.fromtimestamp(ts, timezone.utc).astimezone(_ET).date() in _DAYS
