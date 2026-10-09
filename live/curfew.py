"""Pre-blackout wind-down shared by the paper LP bots (the school Wi-Fi is off 00:00-06:30 UK, when a bot can neither
quote nor trade, so carrying inventory through it scores luck, not the strategy).

From 23:45 to 06:35 UK a bot posts no quotes and earns no reward.  Any open position is closed by crossing the book
like a taker: a long sells into the bids, a short buys from the asks, walking the depth level by level, plus the
venue's taker fee.  That never helps the bot: it gives up ~7 h of reward and pays the spread (and fee) to get out.
If the book is too thin for the whole position, the rest is closed at the worst visible level.
"""
from __future__ import annotations

import time
from datetime import datetime
from datetime import time as dtime
from zoneinfo import ZoneInfo

UK = ZoneInfo("Europe/London")
START, END = dtime(23, 45), dtime(6, 35)


def quiet(ts: float | None = None) -> bool:
    t = datetime.fromtimestamp(ts if ts is not None else time.time(), UK).time()
    return t >= START or t < END


def close(inv: float, bids, asks, fee=lambda px: 0.0):
    """Cash change from closing `inv` YES shares against best-first [(px, size)] levels, and the average price.
    fee(px) = taker fee per share at px.  Returns (cash_delta, avg_px) or (0.0, None) if that side is empty."""
    levels = list(bids if inv > 0 else asks)
    if not inv or not levels:
        return 0.0, None
    left, notional, fees = abs(inv), 0.0, 0.0
    for px, q in levels:
        take = min(left, q)
        notional, fees, left = notional + take * px, fees + take * fee(px), left - take
        if left <= 1e-9:
            break
    if left > 1e-9:                                   # thin book: the rest at the worst visible level
        px = levels[-1][0]
        notional, fees = notional + left * px, fees + left * fee(px)
    avg = notional / abs(inv)
    return (notional if inv > 0 else -notional) - fees, avg


# --- results/PLAN_WINDDOWN.md variant D (pmlp.py --wind --liq-cap) ---
WIND = dtime(21, 45)


def winding(ts: float | None = None) -> bool:
    """21:45-23:45 UK: quote only the side that shrinks inventory"""
    t = datetime.fromtimestamp(ts if ts is not None else time.time(), UK).time()
    return WIND <= t < START


def close_capped(inv: float, bids, asks, mid: float, max_dist: float, fee=lambda px: 0.0):
    """Like close(), but only takes levels within max_dist ($) of mid; the rest stays open.
    Returns (cash_delta, shares_closed signed like inv, avg_px or None)."""
    levels = list(bids if inv > 0 else asks)
    left, notional, fees = abs(inv), 0.0, 0.0
    for px, q in levels:
        if abs(px - mid) > max_dist + 1e-9 or left <= 1e-9:
            break
        take = min(left, q)
        notional, fees, left = notional + take * px, fees + take * fee(px), left - take
    done = abs(inv) - left
    if done <= 1e-9:
        return 0.0, 0.0, None
    return (notional if inv > 0 else -notional) - fees, (done if inv > 0 else -done), notional / done


def exitable(inv: float, bids, asks, mid: float, max_dist: float) -> bool:
    """could `inv` be closed entirely within max_dist of mid on this book?"""
    if not inv:
        return True
    return abs(close_capped(inv, bids, asks, mid, max_dist)[1]) >= abs(inv) - 1e-9
