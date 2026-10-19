"""PUBLIC (no keys) Polymarket intl market-competitiveness recorder: drop-in replacement for live/pmcomp.py.
pmcomp.py needs the user's authenticated CLOB keys (/rewards/user/markets), so it cannot run on the public GitHub runner, and its
7-day laptop run ended 2026-10-14 21:00Z (since then every paper bot's reward_safe silently fell back to the raw book reward).
This recorder reads the unauthenticated per-market endpoint GET https://clob.polymarket.com/rewards/markets/<condition_id>
(field market_competitiveness, same name as the keyed endpoint) for every market in the paper bots' state files, and appends
snapshots in pmcomp.jsonl's format, so pmlp.latest_comp() picks them up unchanged:
  {"ts", "src": "public", "m": {condition_id: [competitiveness, rate_per_day, max_spread, min_size]}}
Read-only GETs; never places, cancels or signs anything.
  python live/pmcomp_pub.py [--every 600] [--hours 24*30] [--out live/pmcomp.jsonl]
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
URL = "https://clob.polymarket.com/rewards/markets/{}"


def cids():
    """condition ids of every paper bot's markets (pmlp*/pmlpws* state files in live/)"""
    out = set()
    for f in glob.glob(os.path.join(HERE, "pmlp*_state.json")):
        try:
            s = json.load(open(f))
        except (OSError, ValueError):
            continue
        out |= set(s.get("pos", {})) | {m["cid"] for m in s.get("markets", []) if "cid" in m}
    return sorted(c for c in out if c.startswith("0x"))


def one(sess, cid):
    r = sess.get(URL.format(cid), timeout=15)
    r.raise_for_status()
    d = (r.json().get("data") or [None])[0]
    if not d or d.get("market_competitiveness") is None:
        return None
    rate = sum(float(x.get("rate_per_day") or 0) for x in d.get("rewards_config") or [])
    return [float(d["market_competitiveness"]), rate, d.get("rewards_max_spread"), d.get("rewards_min_size")]


def snapshot(sess):
    m, bad = {}, 0
    for cid in cids():
        try:
            v = one(sess, cid)
        except (requests.RequestException, ValueError):
            v, bad = None, bad + 1
        if v is not None:
            m[cid] = v
        time.sleep(0.2)                                   # ~5 req/s
    return m, bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--every", type=float, default=600)
    ap.add_argument("--hours", type=float, default=24 * 30)
    ap.add_argument("--out", default=os.path.join(HERE, "pmcomp.jsonl"))
    a = ap.parse_args()
    sess, end = requests.Session(), time.time() + a.hours * 3600
    while time.time() < end:
        t0 = time.time()
        m, bad = snapshot(sess)
        if m:
            with open(a.out, "a") as f:
                f.write(json.dumps({"ts": int(time.time()), "src": "public", "m": m}, separators=(",", ":")) + "\n")
        print(time.strftime("%H:%M:%S"), f"{len(m)} markets, {bad} errors", flush=True)
        time.sleep(max(5.0, a.every - (time.time() - t0)))


if __name__ == "__main__":
    main()
