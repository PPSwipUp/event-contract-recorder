"""Massive (ex-Polygon) free-tier fetcher: minute bars for stocks/ETFs and option contracts, cached to disk.
Free tier = 5 requests/minute, ~2 years of history.  Key read from the quant-research .env (never printed).
"""
from __future__ import annotations

import gzip
import json
import os
import time
import urllib.error
import urllib.request

import pandas as pd

KEY = dict(l.strip().split("=", 1) for l in open(os.path.expanduser("~/quant-research/v2/creators/.env")) if "=" in l)["MASSIVE_API_KEY"]
BASE = "https://api.massive.com"
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data_local", "massive")
SPACING = 12.5
_last = [0.0]


def _get(url):
    while True:
        wait = _last[0] + SPACING - time.time()
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()
        try:
            return json.loads(urllib.request.urlopen(f"{url}{'&' if '?' in url else '?'}apiKey={KEY}", timeout=60).read())
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504):
                time.sleep(30)
                continue
            raise
        except (urllib.error.URLError, OSError, ValueError):
            time.sleep(30)


def minutes(ticker, day_from, day_to):
    """1-minute bars (UTC index; columns o h l c v) for a ticker between two dates, cached per request"""
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, f"{ticker.replace(':', '_')}_{day_from}_{day_to}.json.gz")
    if os.path.exists(path):
        res = json.load(gzip.open(path, "rt"))
    else:
        res, url = [], f"{BASE}/v2/aggs/ticker/{ticker}/range/1/minute/{day_from}/{day_to}?adjusted=true&sort=asc&limit=50000"
        while url:
            d = _get(url)
            res += d.get("results") or []
            url = d.get("next_url")
        json.dump(res, gzip.open(path, "wt"))
    if not res:
        return pd.DataFrame(columns=["o", "h", "l", "c", "v"])
    f = pd.DataFrame(res)
    f.index = pd.to_datetime(f.t, unit="ms", utc=True)
    return f[["o", "h", "l", "c", "v"]]
