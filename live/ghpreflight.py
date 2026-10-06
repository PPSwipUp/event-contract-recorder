"""Preflight for the overnight GitHub run: every data source the night needs must answer with real data, or exit 1.
  python live/ghpreflight.py mlb-nyy-tb-2026-10-05
"""
import sys

import pmusrec
import soccerlive

fails = []


def check(name, fn):
    try:
        msg = fn()
        print(f"OK   {name}: {msg}", flush=True)
    except Exception as err:
        fails.append(name)
        print(f"FAIL {name}: {err!r}"[:300], flush=True)


def pm_us_incentives():
    rows = pmusrec.programs(sys.argv[1])
    if not rows:                     # the game has started/finished: its programs are gone, nothing to record (not a failure)
        assert pmusrec.programs("mlb-"), "incentives API returned nothing at all"
        return "game's programs gone (started) - API itself OK"
    return f"{len(rows)} program rows"


def pm_us_book():
    rows = pmusrec.programs(sys.argv[1]) or pmusrec.programs("mlb-")
    slug = rows[0]["slug"]
    b = pmusrec.book(slug)
    assert b and (b["bids"] or b["offers"]), f"empty book for {slug}"
    return f"{slug} bids {len(b['bids'])} offers {len(b['offers'])}"


def us_soccer():
    M = soccerlive.us_matches()
    assert M, "no soccer matches"
    Q = soccerlive.us_books([k for _, k, _ in M[0][2]])
    assert all(Q.get(k) for _, k, _ in M[0][2]), "missing US soccer books"
    return f"{len(M)} matches, sample {M[0][0]}"


def intl_soccer():
    M = soccerlive.intl_matches()
    assert M, "no intl soccer matches"
    Q = soccerlive.intl_books([k for _, k, _ in M[0][2]])
    assert len(Q) == 3, f"only {len(Q)} of 3 intl books"
    return f"{len(M)} matches, sample {M[0][0]}"


if __name__ == "__main__":
    check("Polymarket US incentives", pm_us_incentives)
    check("Polymarket US book", pm_us_book)
    check("Polymarket US soccer", us_soccer)
    check("Polymarket intl soccer + CLOB books", intl_soccer)
    if fails:
        print("PREFLIGHT FAILED:", ", ".join(fails), flush=True)
        sys.exit(1)
    print("PREFLIGHT PASSED", flush=True)
