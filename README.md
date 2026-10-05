# event-contract-recorder

Records prices of short-dated price-range, above/below and up/down contracts, plus the underlying prices,
every 5 minutes from GitHub Actions. Read-only: it uses public endpoints, no account and no keys, and never
places an order.

| source | what |
|---|---|
| Kalshi | every open market in BTC/ETH/SOL ranges and above/below, S&P 500 and Nasdaq ranges and 15-min, gold, WTI oil, EUR/USD, USD/JPY, GBP/USD, 10Y yield (bid/ask/last/volume/open interest); settled results hourly |
| Polymarket | crypto price buckets, "above" ladders and up/down markets ending within 3 days |
| Spot | Coinbase BTC/ETH/SOL/XRP; Yahoo 1-minute bars for S&P 500, Nasdaq-100, ES, NQ, gold, oil, silver, EUR/USD, USD/JPY, GBP/USD (hourly) |

## Where the data is

- Today so far: the [`data` branch](../../tree/data), one gzipped JSON-lines file per run:
  `<source>/<YYYY-MM-DD>/<HHMMSS>.jsonl.gz`, and `log/<YYYY-MM-DD>.log` (one line per run).
- Finished days: one release per day, `data-YYYY-MM-DD`, holding `data-YYYY-MM-DD.tar`.

```bash
gh release download data-2026-10-01 -R PPSwipUp/event-contract-recorder
```

## How it runs

- `record.yml`: one run records every 5 minutes for about 5.5 hours, then starts the next run; an hourly schedule restarts the chain if it ever breaks. Each pass
  first moves finished days into releases (`compact.sh`) and resets the `data` branch, so the repository
  stays small.
