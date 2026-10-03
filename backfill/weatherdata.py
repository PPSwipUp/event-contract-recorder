"""Data for the Kalshi daily-high temperature backtest (6 cities, 2025-01 .. 2026-09).  Read-only public sources.
  truth     : NWS daily climate report high (what Kalshi settles on)        - Iowa Mesonet cli.py
  forecast  : Open-Meteo hourly forecast as issued 1 and 2 days before     - previous-runs API (point-in-time)
  obs       : hourly station readings during the day (running max so far)  - Iowa Mesonet ASOS
  kalshi    : every market (strikes, result) + real trades in two 1-hour decision windows on the day
              (10:00-11:00 and 14:00-15:00 local)
  python backfill/weatherdata.py
"""
from __future__ import annotations

import io
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests

from collect import K, get
from fullhour import all_trades

OUT = "data_local/weather"
START, END = date(2025, 1, 1), date(2026, 10, 1)
CITIES = {   # series: (CLI station, ASOS id, lat, lon, tz)
    "KXHIGHNY": ("KNYC", "NYC", 40.7789, -73.9692, "America/New_York"),
    "KXHIGHCHI": ("KMDW", "MDW", 41.7860, -87.7524, "America/Chicago"),
    "KXHIGHMIA": ("KMIA", "MIA", 25.7906, -80.3164, "America/New_York"),
    "KXHIGHAUS": ("KAUS", "AUS", 30.1945, -97.6699, "America/Chicago"),
    "KXHIGHDEN": ("KDEN", "DEN", 39.8466, -104.6562, "America/Denver"),
    "KXHIGHLAX": ("KLAX", "LAX", 33.9382, -118.3866, "America/Los_Angeles"),
}
WINDOWS = (10, 14)          # local decision hours; trades from h:00 to h+1:00
S = requests.Session()


def truth(st):
    rows = []
    for y in range(START.year, END.year + 1):
        d = S.get("https://mesonet.agron.iastate.edu/json/cli.py", params={"station": st, "year": y}, timeout=60).json()
        rows += [{"day": r["valid"], "high": r["high"]} for r in d.get("results", [])]
    f = pd.DataFrame(rows)
    f["high"] = pd.to_numeric(f.high, errors="coerce")
    return f.dropna().drop_duplicates("day")


def forecast(lat, lon, tz):
    d = S.get("https://previous-runs-api.open-meteo.com/v1/forecast", timeout=120, params={
        "latitude": lat, "longitude": lon, "start_date": START.isoformat(), "end_date": (END - timedelta(days=1)).isoformat(),
        "hourly": "temperature_2m_previous_day1,temperature_2m_previous_day2", "temperature_unit": "fahrenheit",
        "timezone": tz}).json()["hourly"]
    return pd.DataFrame({"time": pd.to_datetime(d["time"]), "f1": d["temperature_2m_previous_day1"],
                         "f2": d["temperature_2m_previous_day2"]})


def obs(asos, tz):
    parts = []
    for y in range(START.year, END.year + 1):
        r = S.get("https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py", timeout=300, params={
            "station": asos, "data": "tmpf", "year1": y, "month1": 1, "day1": 1, "year2": y, "month2": 12, "day2": 31,
            "tz": tz, "format": "onlycomma", "latlon": "no", "missing": "empty", "trace": "empty", "report_type": [3, 4]})
        parts.append(pd.read_csv(io.StringIO(r.text)))
    f = pd.concat(parts)
    f["valid"] = pd.to_datetime(f.valid)
    f["tmpf"] = pd.to_numeric(f.tmpf, errors="coerce")
    return f.dropna()[["valid", "tmpf"]]


def kalshi(series, tz):
    z = ZoneInfo(tz)
    mon = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]

    def one(day):
        ev = f"{series}-{day:%y}{mon[day.month - 1]}{day:%d}"
        try:
            ms = []
            for base in (f"{K}/markets", f"{K}/historical/markets"):
                d = get(base, event_ticker=ev, limit=100)
                if d and d.get("markets"):
                    ms = d["markets"]
                    break
            mk = [{"series": series, "day": day.isoformat(), "event": ev, "ticker": m["ticker"], "floor": m.get("floor_strike"),
                   "cap": m.get("cap_strike"), "strike_type": m.get("strike_type"), "result": m.get("result"),
                   "volume": float(m.get("volume_fp") or 0)} for m in ms]
            tr = []
            for h in WINDOWS:
                t0 = datetime(day.year, day.month, day.day, h, tzinfo=z)
                for m in ms:
                    for t in all_trades(m["ticker"], int(t0.timestamp()), int(t0.timestamp()) + 3600):
                        tr.append({"ticker": m["ticker"], "window": h, "ts": t["created_time"], "taker": t.get("taker_side"),
                                   "yes": float(t.get("yes_price_dollars") or np.nan), "count": float(t.get("count_fp") or 0)})
            return mk, tr
        except Exception as e:
            print("skip", ev, repr(e)[:80], flush=True)
            return [], []

    days = [START + timedelta(days=i) for i in range((END - START).days)]
    with ThreadPoolExecutor(6) as ex:
        res = list(ex.map(one, days))
    return pd.DataFrame([r for m, _ in res for r in m]), pd.DataFrame([r for _, t in res for r in t])


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for series, (st, asos, lat, lon, tz) in CITIES.items():
        p = f"{OUT}/{series}"
        if not os.path.exists(f"{p}_truth.parquet"):
            truth(st).to_parquet(f"{p}_truth.parquet")
            forecast(lat, lon, tz).to_parquet(f"{p}_fc.parquet")
            obs(asos, tz).to_parquet(f"{p}_obs.parquet")
            print(series, "weather data saved", flush=True)
        if not os.path.exists(f"{p}_trades.parquet"):
            M, T = kalshi(series, tz)
            M.to_parquet(f"{p}_markets.parquet")
            T.to_parquet(f"{p}_trades.parquet")
            print(series, len(M), "markets", len(T), "trades", flush=True)
