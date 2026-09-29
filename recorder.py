"""Read-only recorder of short-dated price-range / above-below / up-down contracts + the underlying prices.

Records (public endpoints only, no account, no keys, NEVER places orders):
  Kalshi      every open market in SERIES (bid/ask/last/volume/OI per bracket) + settled results
  Polymarket  crypto price buckets / above ladders / up-or-down (outcome prices, bid/ask, volume)
  Spot        Coinbase BTC/ETH/SOL/XRP spot; Yahoo 1-min bars for S&P, Nasdaq, gold, oil, EUR/USD

Network handling (run it every couple of minutes from launchd; it decides by itself whether to work):
  school Wi-Fi   the school intercepts HTTPS (fake certificates) -> detected, logged, run skipped
  hotspot (EE)   the carrier's DNS sends betting sites to a block page -> hosts are resolved through
                 Cloudflare DNS-over-HTTPS instead, which reaches the real servers
  anything else  same as hotspot

Output: $RECORDER_OUT (default ./data)/<source>/<YYYY-MM-DD>/<HHMMSS>.jsonl.gz (one JSON object per line)
        log/<YYYY-MM-DD>.log (one line per run: time, network, what was recorded)

  python binary/recorder.py            # one pass (what launchd runs)
  python binary/recorder.py --check    # just say which network you're on and whether sites are reachable
"""
from __future__ import annotations

import gzip
import json
import os
import socket
import ssl
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import certifi
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("RECORDER_OUT", os.path.join(HERE, "data"))
RUN = datetime.now(timezone.utc)
STATE = os.path.join(OUT, "state.json")

KALSHI = "https://api.elections.kalshi.com/trade-api/v2"
GAMMA = "https://gamma-api.polymarket.com"
# range / above-below / up-down series worth pricing with a volatility forecast
SERIES = [
    "KXBTC", "KXBTCD", "KXBTC15M", "KXETH", "KXETHD", "KXETH15M", "KXSOL", "KXSOLE", "KXSOL15M",  # crypto
    "KXINX", "KXINXU", "KXINXI", "KXINX15M", "KXNASDAQ100", "KXNASDAQ100U", "KXNDQ15M",          # indices
    "KXGOLD", "WTI", "WTIH",                                                                     # commodities
    "KXEURUSD", "KXEURUSDH", "KXEURUSD15M", "KXUSDJPY", "KXUSDJPYH", "KXGBPUSD15M",            # FX
    "KX10YRRATE15M",                                                                             # rates
]
PM_KEYS = ("-price-on-", "-above-on-", "up-or-down", "what-price-will")
YAHOO = {"sp500": "^GSPC", "nasdaq100": "^NDX", "es": "ES=F", "nq": "NQ=F", "gold": "GC=F", "oil": "CL=F",
         "silver": "SI=F", "eurusd": "EURUSD=X", "usdjpy": "JPY=X", "gbpusd": "GBPUSD=X"}
COINBASE = ["BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD"]
UA = {"User-Agent": "Mozilla/5.0 (research recorder; read-only)"}

# ------------------------------------------------------------------ network
_doh_cache: dict[str, tuple[float, list[str]]] = {}
_BYPASS = {"api.elections.kalshi.com", "gamma-api.polymarket.com", "clob.polymarket.com"}
_orig_getaddrinfo = socket.getaddrinfo


def _doh(host):
    """resolve through Cloudflare DNS-over-HTTPS (by IP, so the carrier's DNS is never asked)"""
    hit = _doh_cache.get(host)
    if hit and time.time() - hit[0] < 300:
        return hit[1]
    r = requests.get("https://1.1.1.1/dns-query", params={"name": host, "type": "A"},
                     headers={"accept": "application/dns-json"}, timeout=10, verify=certifi.where())
    ips = [a["data"] for a in r.json().get("Answer", []) if a.get("type") == 1]
    _doh_cache[host] = (time.time(), ips)
    return ips


def _getaddrinfo(host, port, *a, **k):
    if host in _BYPASS:
        try:
            ips = _doh(host)
            if ips:
                return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port)) for ip in ips]
        except Exception:
            pass
    return _orig_getaddrinfo(host, port, *a, **k)


socket.getaddrinfo = _getaddrinfo


def network():
    """'school' if HTTPS is being intercepted, 'offline' if nothing answers, else 'open' (hotspot/home)"""
    ctx = ssl.create_default_context(cafile=certifi.where())
    try:
        with socket.create_connection(("api.coinbase.com", 443), timeout=8) as s:
            with ctx.wrap_socket(s, server_hostname="api.coinbase.com"):
                return "open"
    except ssl.SSLCertVerificationError:
        return "school"
    except OSError:
        return "offline"


def get(url, **params):
    """GET with retries: a dropped TLS handshake, rate limiting (429) or a server error backs off and retries"""
    for attempt in range(5):
        try:
            r = requests.get(url, params=params or None, headers=UA, timeout=30, verify=certifi.where())
            if r.status_code == 429 or r.status_code >= 500:
                raise requests.exceptions.HTTPError(f"{r.status_code}", response=r)
            r.raise_for_status()
            return r.json()
        except (requests.exceptions.SSLError, requests.exceptions.HTTPError) as err:
            code = getattr(err.response, "status_code", None)
            if attempt == 4 or (code is not None and code != 429 and code < 500):
                raise
            time.sleep(2 ** attempt)


# ------------------------------------------------------------------ storage
def write(source, rows):
    if not rows:
        return 0
    d = os.path.join(OUT, source, RUN.strftime("%Y-%m-%d"))        # one new file per run: nothing is rewritten
    os.makedirs(d, exist_ok=True)
    with gzip.open(os.path.join(d, RUN.strftime("%H%M%S") + ".jsonl.gz"), "wt") as fh:
        for r in rows:
            fh.write(json.dumps(r, separators=(",", ":")) + "\n")
    return len(rows)


def load_state():
    try:
        with open(STATE) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def save_state(s):
    os.makedirs(OUT, exist_ok=True)
    with open(STATE + ".tmp", "w") as fh:
        json.dump(s, fh)
    os.replace(STATE + ".tmp", STATE)


# ------------------------------------------------------------------ sources
KEEP_K = ("ticker", "event_ticker", "floor_strike", "cap_strike", "strike_type", "yes_bid_dollars",
          "yes_ask_dollars", "no_bid_dollars", "no_ask_dollars", "last_price_dollars", "volume_fp",
          "volume_24h_fp", "open_interest_fp", "liquidity_dollars", "close_time", "status", "result",
          "expiration_value")


def kalshi_markets(series, status):
    out, cursor = [], None
    while True:
        p = {"series_ticker": series, "status": status, "limit": 1000}
        if status == "settled":
            p["min_close_ts"] = int(time.time() - 3 * 3600)
        if cursor:
            p["cursor"] = cursor
        d = get(f"{KALSHI}/markets", **p)
        out += d.get("markets", [])
        cursor = d.get("cursor")
        if not cursor or not d.get("markets"):
            return out


def record_kalshi(ts, settled):
    jobs = [(s, st) for s in SERIES for st in (("open", "settled") if settled else ("open",))]

    def one(job):
        s, status = job
        try:
            return [{"ts": ts, "series": s, **{k: m.get(k) for k in KEEP_K}} for m in kalshi_markets(s, status)], None
        except Exception as err:
            return [], f"{s}:{getattr(getattr(err, 'response', None), 'status_code', type(err).__name__)}"

    with ThreadPoolExecutor(4) as ex:
        res = list(ex.map(one, jobs))
    rows = [r for rs, _ in res for r in rs]
    return write("kalshi", rows), [b for _, b in res if b]


def record_polymarket(ts):
    now = datetime.now(timezone.utc)
    rows, off = [], 0
    while off < 2000:
        ev = get(f"{GAMMA}/events", closed="false", tag_slug="crypto-prices", limit=100, offset=off,
                 end_date_min=now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                 end_date_max=(now + timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%SZ"))
        for e in ev:
            if not any(k in e.get("slug", "") for k in PM_KEYS):
                continue
            for m in e.get("markets", []):
                rows.append({"ts": ts, "event": e["slug"], "end": e.get("endDate"), "market": m.get("slug"),
                             "question": m.get("question"), "outcomes": m.get("outcomes"),
                             "prices": m.get("outcomePrices"), "bid": m.get("bestBid"), "ask": m.get("bestAsk"),
                             "last": m.get("lastTradePrice"), "volume": m.get("volumeNum"),
                             "liquidity": m.get("liquidityNum"), "closed": m.get("closed")})
        if len(ev) < 100:
            break
        off += 100
    return write("polymarket", rows)


def record_spot(ts, with_bars):
    rows = []
    for p in COINBASE:
        try:
            rows.append({"ts": ts, "symbol": p, "price": float(get(f"https://api.coinbase.com/v2/prices/{p}/spot")["data"]["amount"])})
        except Exception:
            pass
    n = write("spot", rows)
    if with_bars:                                      # 1-min bars for the last day: gaps between runs are filled
        def bar(item):
            name, sym = item
            try:
                d = get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}", interval="1m", range="1d")
                r = d["chart"]["result"][0]
                q = r["indicators"]["quote"][0]
                return {"ts": ts, "name": name, "t": r["timestamp"], "c": q["close"], "h": q["high"], "l": q["low"]}
            except Exception:
                return None

        with ThreadPoolExecutor(8) as ex:
            n += write("bars", [b for b in ex.map(bar, YAHOO.items()) if b])
    return n


# ------------------------------------------------------------------ main
def log(line):
    d = os.path.join(OUT, "log")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, RUN.strftime("%Y-%m-%d") + ".log"), "a") as fh:
        fh.write(line + "\n")


def main():
    net = network()
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    if "--check" in sys.argv:
        print(f"network: {net}")
        if net == "open":
            for name, url in [("kalshi", f"{KALSHI}/exchange/status"), ("polymarket", f"{GAMMA}/events?limit=1")]:
                try:
                    get(url)
                    print(f"  {name}: reachable")
                except Exception as err:
                    print(f"  {name}: NOT reachable ({type(err).__name__})")
        return
    if net != "open":
        log(f"{ts} {net} skipped")
        return
    st = load_state()
    hourly = time.time() - st.get("last_hourly", 0) > 3600
    with ThreadPoolExecutor(3) as ex:                  # the three sources are independent: fetch at the same time
        fk = ex.submit(record_kalshi, ts, hourly)
        fp = ex.submit(record_polymarket, ts)
        fs = ex.submit(record_spot, ts, hourly)
    nk, bad = fk.result()
    try:
        npm = fp.result()
    except Exception as err:
        npm, bad = 0, bad + [f"polymarket:{type(err).__name__}"]
    ns = fs.result()
    if hourly:
        st["last_hourly"] = time.time()
    save_state(st)
    log(f"{ts} open kalshi={nk} polymarket={npm} spot={ns}" + (f" errors={','.join(bad)}" if bad else ""))


if __name__ == "__main__":
    main()
