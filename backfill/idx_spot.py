"""Download SPY and QQQ minute bars, Oct 2024 - Sep 2026, month by month (Massive free tier, cached).
  python backfill/idx_spot.py
"""
import pandas as pd

from massive import minutes

if __name__ == "__main__":
    months = pd.date_range("2024-10-01", "2026-10-01", freq="MS")
    for tk in ("SPY", "QQQ"):
        parts = []
        for a, b in zip(months[:-1], months[1:]):
            f = minutes(tk, a.strftime("%Y-%m-%d"), (b - pd.Timedelta(days=1)).strftime("%Y-%m-%d"))
            parts.append(f)
            print(tk, a.strftime("%Y-%m"), len(f), flush=True)
        pd.concat(parts).sort_index().to_parquet(f"data_local/idx/{tk}_1m.parquet")
