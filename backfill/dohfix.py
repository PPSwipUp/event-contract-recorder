"""EE mobile DNS sends Kalshi/Polymarket to a block page (109.249.x.x).  Only when the system resolver returns that
block address do we ask Cloudflare DNS-over-HTTPS instead (school Wi-Fi blocks DoH, but resolves normally).
Import once, before making requests."""
import json
import os
import socket
import urllib.request

HOSTS = ("api.elections.kalshi.com", "gamma-api.polymarket.com", "clob.polymarket.com")
BLOCK_PREFIX = "109.249."
_orig = socket.getaddrinfo
_cache = {}


def _doh(host):
    if host not in _cache:
        try:
            req = urllib.request.Request(f"https://cloudflare-dns.com/dns-query?name={host}&type=A",
                                         headers={"accept": "application/dns-json"})
            ans = json.load(urllib.request.urlopen(req, timeout=5)).get("Answer", [])
            _cache[host] = next((a["data"] for a in ans if a.get("type") == 1), None)
        except Exception:
            _cache[host] = None
    return _cache[host]


def _getaddrinfo(host, *args, **kw):
    res = _orig(host, *args, **kw)
    if host in HOSTS and any(r[4][0].startswith(BLOCK_PREFIX) for r in res):
        ip = _doh(host)
        if ip:
            return _orig(ip, *args, **kw)
    return res


# 2026-10-10: OFF by default - the user asked not to bypass the carrier filter.  Opt in with EVENTREC_DOH=1.
if os.environ.get("EVENTREC_DOH") == "1":
    socket.getaddrinfo = _getaddrinfo
