"""Live, read-only cross-venue check on SPORTS games: Kalshi game-winner markets (one market per team) vs Polymarket
moneyline markets (one market, two team outcomes).  Never places orders.

Matching: same game day (Polymarket gameStartTime vs the date in Kalshi's event ticker) and both teams matched by
name (Kalshi uses cities, e.g. 'Los Angeles R'; Polymarket uses nicknames or full names; alias table below).  Games
whose teams do not match cleanly are skipped, never guessed.
Packages per team X (each pays $1 if both venues settle the same way):
  Kalshi YES(X) + Polymarket(other team)        Kalshi NO(X) + Polymarket(X)
Best asks, size = smaller best-ask size, Kalshi taker fee with the series' multiplier, Polymarket fee rate*p*(1-p)
from the market's own schedule.  Every poll logs the best package per game to xvsports.jsonl.
Settlement-rule differences (postponements, ties, overtime) are a real risk and are NOT priced here.
  python live/xvsports.py --every 30 --hours 168
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backfill"))
import dohfix  # noqa: F401,E402
from arbscan import books, kget  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
PM = requests.Session()
LEAGUES = {"KXNFLGAME": "nfl", "KXMLBGAME": "mlb", "KXNBAGAME": "nba", "KXNHLGAME": "nhl"}
CITY = {  # nickname -> city, for leagues where Polymarket shows nicknames only
    # NFL
    "Cardinals": "Arizona", "Falcons": "Atlanta", "Ravens": "Baltimore", "Bills": "Buffalo", "Panthers": "Carolina",
    "Bears": "Chicago", "Bengals": "Cincinnati", "Browns": "Cleveland", "Cowboys": "Dallas", "Broncos": "Denver",
    "Lions": "Detroit", "Packers": "Green Bay", "Texans": "Houston", "Colts": "Indianapolis", "Jaguars": "Jacksonville",
    "Chiefs": "Kansas City", "Raiders": "Las Vegas", "Chargers": "Los Angeles C", "Rams": "Los Angeles R",
    "Dolphins": "Miami", "Vikings": "Minnesota", "Patriots": "New England", "Saints": "New Orleans",
    "Giants": "New York G", "Jets": "New York J", "Eagles": "Philadelphia", "Steelers": "Pittsburgh",
    "49ers": "San Francisco", "Seahawks": "Seattle", "Buccaneers": "Tampa Bay", "Titans": "Tennessee",
    "Commanders": "Washington",
    # NBA
    "Hawks": "Atlanta", "Celtics": "Boston", "Nets": "Brooklyn", "Hornets": "Charlotte", "Bulls": "Chicago",
    "Cavaliers": "Cleveland", "Mavericks": "Dallas", "Nuggets": "Denver", "Pistons": "Detroit",
    "Warriors": "Golden State", "Rockets": "Houston", "Pacers": "Indiana", "Clippers": "Los Angeles C",
    "Lakers": "Los Angeles L", "Grizzlies": "Memphis", "Heat": "Miami", "Bucks": "Milwaukee",
    "Timberwolves": "Minnesota", "Pelicans": "New Orleans", "Knicks": "New York", "Thunder": "Oklahoma City",
    "Magic": "Orlando", "76ers": "Philadelphia", "Suns": "Phoenix", "Trail Blazers": "Portland",
    "Spurs": "San Antonio", "Raptors": "Toronto", "Jazz": "Utah", "Wizards": "Washington",
    # NHL ('Kings', 'Panthers', 'Jets' clash with other leagues: NHL handled by the league-specific table below)
}
NHL = {"Ducks": "Anaheim", "Bruins": "Boston", "Sabres": "Buffalo", "Flames": "Calgary", "Hurricanes": "Carolina",
       "Blackhawks": "Chicago", "Avalanche": "Colorado", "Blue Jackets": "Columbus", "Stars": "Dallas",
       "Red Wings": "Detroit", "Oilers": "Edmonton", "Panthers": "Florida", "Kings": "Los Angeles", "Wild": "Minnesota",
       "Canadiens": "Montreal", "Predators": "Nashville", "Devils": "New Jersey", "Islanders": "New York I",
       "Rangers": "New York R", "Senators": "Ottawa", "Flyers": "Philadelphia", "Penguins": "Pittsburgh",
       "Sharks": "San Jose", "Kraken": "Seattle", "Blues": "St. Louis", "Lightning": "Tampa Bay",
       "Maple Leafs": "Toronto", "Utah": "Utah", "Mammoth": "Utah", "Canucks": "Vancouver", "Golden Knights": "Vegas",
       "Capitals": "Washington", "Jets": "Winnipeg"}
NBA_KINGS = {"Kings": "Sacramento"}


def norm(s):
    return re.sub(r"[^a-z0-9 ]", "", s.lower()).strip()


def same_team(kalshi_label, pm_name, league):
    """Kalshi 'Los Angeles R' / 'San Diego' vs Polymarket 'Rams' / 'San Diego Padres' / 'Maple Leafs'"""
    table = NHL if league == "nhl" else {**CITY, **(NBA_KINGS if league == "nba" else {})}
    full = pm_name if pm_name not in table else table[pm_name]
    k, p = norm(kalshi_label), norm(full)
    if not k or not p:
        return False
    if k == p or p.startswith(k + " ") or k.startswith(p + " ") and len(k) - len(p) <= 3:
        return True
    w = k.split()
    if len(w) >= 2 and len(w[-1]) <= 2:                       # 'los angeles r', 'chicago ws': city + initials
        city, ini = " ".join(w[:-1]), w[-1]
        rest = p[len(city):].split() if p.startswith(city) else None
        return bool(rest) and "".join(x[0] for x in rest)[:len(ini)] == ini or (p == k)
    return False


def kalshi_games():
    out = {}
    for series, league in LEAGUES.items():
        cur = None
        while True:
            p = {"series_ticker": series, "status": "open", "limit": 1000}
            if cur:
                p["cursor"] = cur
            d = kget("/markets", **p)
            for m in d.get("markets", []):
                out.setdefault((league, m["event_ticker"]), []).append(m)
            cur = d.get("cursor")
            if not cur or not d.get("markets"):
                break
    return out


def pm_games():
    out = []
    for league in set(LEAGUES.values()):
        evs = PM.get("https://gamma-api.polymarket.com/events", timeout=30,
                     params={"tag_slug": league, "active": "true", "closed": "false", "limit": 500}).json()
        for e in evs if isinstance(evs, list) else []:
            for m in e.get("markets") or []:
                outs = json.loads(m.get("outcomes") or "[]")
                if m.get("sportsMarketType") == "moneyline" and len(outs) == 2 and m.get("gameStartTime") and m.get("acceptingOrders"):
                    fs = m.get("feeSchedule") or {}
                    out.append({"league": league, "title": e["title"], "teams": outs, "tokens": json.loads(m["clobTokenIds"]),
                                "start": m["gameStartTime"], "rate": float(fs.get("rate") or 0) if m.get("feesEnabled") else 0.0})
    return out


def match(K, P):
    pairs = []
    for g in P:
        cand = []
        start = datetime.fromisoformat(g["start"].replace(" ", "T").replace("+00", "+00:00"))
        for (league, ev), ms in K.items():
            if league != g["league"]:
                continue
            day = re.search(r"-(\d{2}[A-Z]{3}\d{2})(\d{4})?", ev)
            if not day:
                continue
            kd = datetime.strptime(day.group(1), "%y%b%d").date()
            if abs((kd - (start - timedelta(hours=6)).date()).days) > 0:        # US-evening games cross UTC midnight
                continue
            if day.group(2):                                                    # ticker carries the ET start time
                et = datetime.strptime(day.group(1) + day.group(2), "%y%b%d%H%M").replace(tzinfo=ZoneInfo("America/New_York"))
                if abs((et - start).total_seconds()) > 5400:
                    continue
            teams = [m for m in ms if norm(m.get("yes_sub_title") or "") not in ("tie", "draw")]
            if len(teams) != 2:
                continue
            mapping = {}
            for i, name in enumerate(g["teams"]):
                hit = [m for m in teams if same_team(m.get("yes_sub_title") or "", name, league)]
                if len(hit) == 1:
                    mapping[i] = hit[0]
            if len(mapping) == 2 and mapping[0]["ticker"] != mapping[1]["ticker"]:
                cand.append((g, ev, mapping))
        if len(cand) == 1:                                                      # ambiguous (doubleheader) -> skip
            pairs.append(cand[0])
    return pairs


def pm_asks(tokens):
    r = PM.post("https://clob.polymarket.com/books", json=[{"token_id": t} for t in tokens], timeout=20).json()
    out = {}
    for b in r if isinstance(r, list) else []:
        asks = [(float(a["price"]), float(a["size"])) for a in b.get("asks", [])]
        out[b["asset_id"]] = min(asks) if asks else (None, 0)
    return out


FEE_MULT = {}


def kfee(series, p, n):
    if series not in FEE_MULT:
        s = kget(f"/series/{series}")["series"]
        FEE_MULT[series] = float(s.get("fee_multiplier") or 1)
    return math.ceil(7 * FEE_MULT[series] * n * p * (1 - p)) / n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--every", type=float, default=30)
    ap.add_argument("--hours", type=float, default=168)
    a = ap.parse_args()
    out = os.path.join(HERE, "xvsports.jsonl")
    stop, pairs, refreshed = time.time() + 3600 * a.hours, [], 0
    while time.time() < stop:
        t0 = time.time()
        try:
            if t0 - refreshed > 1800:                                            # re-match every 30 min
                pairs, refreshed = match(kalshi_games(), pm_games()), t0
                print(datetime.now(timezone.utc).strftime("%H:%M"), "matched games:", len(pairs),
                      [g["title"][:30] for g, _, _ in pairs[:5]], flush=True)
            if not pairs:
                time.sleep(a.every)
                continue
            Q = books(sorted({m["ticker"] for _, _, mp in pairs for m in mp.values()}))
            P = pm_asks([t for g, _, _ in pairs for t in g["tokens"]])
            now = datetime.now(timezone.utc).isoformat(timespec="seconds")
            with open(out, "a") as f:
                for g, ev, mp in pairs:
                    best = None
                    for i in (0, 1):
                        km, series = mp[i], mp[i]["ticker"].split("-")[0]
                        if km["ticker"] not in Q:
                            continue
                        ky, kys, kn, kns = Q[km["ticker"]]
                        for kind, (kp, ks), (pp, ps) in ((f"K_YES[{g['teams'][i]}]+PM[{g['teams'][1 - i]}]", (ky, kys), P.get(g["tokens"][1 - i], (None, 0))),
                                                         (f"K_NO[{g['teams'][i]}]+PM[{g['teams'][i]}]", (kn, kns), P.get(g["tokens"][i], (None, 0)))):
                            if kp is None or pp is None or ks <= 0 or ps <= 0:
                                continue
                            size = int(min(ks, ps))
                            if size < 1:
                                continue
                            edge = 100 - 100 * kp - 100 * pp - kfee(series, kp, size) - 100 * g["rate"] * pp * (1 - pp)
                            if best is None or edge > best["edge_c"]:
                                best = {"t": now, "game": g["title"], "league": g["league"], "kalshi_event": ev, "kind": kind,
                                        "k_ask": kp, "pm_ask": pp, "size": size, "edge_c": round(edge, 2)}
                    if best:
                        f.write(json.dumps(best) + "\n")
        except Exception as err:
            print(datetime.now(timezone.utc).strftime("%H:%M:%S"), "error", repr(err)[:150], flush=True)
        time.sleep(max(0, a.every - (time.time() - t0)))


if __name__ == "__main__":
    main()
