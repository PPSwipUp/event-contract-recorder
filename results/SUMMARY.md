# Where things stand (2026-10-01)

**The volatility model has a real but small edge on Kalshi's hourly BTC/ETH *range* markets. There is no edge on the
liquid *above/below* markets. It isn't big enough to matter yet: at the size that actually traded, it's roughly
$100-200 a month.**

## What was tested

| Test | Data | Result |
|---|---|---|
| First-minute stale prices (BTC) | Aug-Sep 2026 quotes | One day (28 Sep) made 96% of the profit: **dead** |
| 3,888-config sweep | Aug-Sep 2026 quotes | Training performance barely predicts the holdout (rank corr 0.15-0.27): mostly luck |
| ETH rules, 7-month holdout | Jan-Jul 2026 trades | Baseline **+4.1c/bet, t 3.56, 7/7 months**. The first version looked like $30k: two look-ahead leaks, found and fixed |
| **2-year database** | Nov 2024-Sep 2026, ~45k hourly events, real trades | See below |

## The 2-year database (leak-free, real trade prices, Kalshi fees)

| Market | Model vs market accuracy | Baseline rule | At the size that actually traded |
|---|---|---|---|
| BTC hourly ranges | model better in 2024-25, tied in 2026; a blend beats the market | +2.7c/bet, **t 3.74** (4.18 excluding Aug-Sep 26) | ~$2,900 over 2 years |
| ETH hourly ranges | model better every year; a blend beats the market | +2.8c/bet, **t 3.19** (walk-forward t 3.8) | ~$1,100 over 2 years |
| BTC hourly above/below (8.3 billion contracts traded) | **market better** in 2025-26 | ~0, loses in 2026 | - |
| ETH hourly above/below | market better in 2026 | ~0 | - |

**Why:** the model's odds are close to perfectly calibrated (e.g. 18.4% forecast vs 18.4% actual). Where many traders compete,
the market is just as good. The edge survives only where liquidity is thin, which is also why it can't be scaled up.
The median trade proving each price was 5-8 contracts.

## Compounding the self-tuning bot (Jan-Jul 2026, from $1,000, capped at traded size)

| Risk per bet | Final | CAGR | Max drawdown |
|---|---|---|---|
| 1% | $1,169 | 37% | 12% |
| 2% | $1,603 | 156% | 14% |
| 5% | $2,180 | 373% | 29% |

The percentages are high only because $1,000 is tiny and 6 months is annualised. The liquidity cap holds dollar profits to ~$1-2k per half-year whatever the bankroll.

## Running automatically (nothing needed from you)

- **Recorder** (`record.yml`): Kalshi + Polymarket + spot prices every 5 minutes, packed into daily releases.
- **Forward test 1** (`forward.yml` -> FORWARD.md): ETH, rolling + volview rule, frozen 2026-10-01.
- **Forward test 2** (`forward.yml` -> FORWARD_BASE.md): the baseline rule on BTC + ETH ranges, frozen 2026-10-01 after the database test.
- Pre-registered pass mark for both: day-level t > 2 after at least 60 days (~early December 2026).

## Honest odds

About **30%** that the range edge holds live. Even then, it's worth ~$100-200 a month at realistic sizes unless order books
deepen. Don't put money in before the forward tests pass. If they do, the next step is the read-only live watcher on an
AWS us-east-2 server (needs your Kalshi API key added as a GitHub secret).

Also done today: ppc-forecaster **0.3.1** released on PyPI (`auto` no longer locks onto one model on short series).
