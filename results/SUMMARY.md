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

## Volume-checked full simulation (Nov 2024 - Sep 2026, 28 Sep excluded; see SIM.md)

Each bet is sized to what other traders actually bought at our price or better after our entry (max 100 contracts).

| Strategy | Bets | Win rate | Total | Per month | Sharpe (ann.) | Max drawdown | Months positive |
|---|---|---|---|---|---|---|---|
| **Ranges only, self-tuning** | 8,240 | 57% | **+$3,661** | **+$174** | **1.09** | $2,091 | 15/22 |
| Ranges only, baseline | 6,229 | 54% | +$3,051 | +$134 | 0.94 | $1,999 | 17/24 |
| All four, baseline | 19,259 | 62% | -$13,131 | -$575 | -1.62 | $17,131 | 10/24 |
| Above/below (BTC, ETH) baseline | 13,030 | 65% | -$16,182 | - | -1.6 / -2.6 | - | 7-8/24 |

**Above/below loses once size is counted** (adverse selection: the bets with lots of volume behind them are the losers).
Ranges only, compounding from $1,000 at 2% per bet: $3,548 (CAGR 107%, max drawdown 48%).

## Lower-drawdown range bot (chosen on 2024-25, tested once on Jan-Sep 2026; see IMPROVE.md, DIAGNOSE.md)

Rules: only bets with > 12c edge after fees, max 25 contracts (never above what others traded), skip if the trade showing the price was > 200 contracts.
(The daily stop and "calm hour" filters barely matter.)

| Bot | Holdout profit | Per month | Max drawdown | Sharpe | Months positive |
|---|---|---|---|---|---|
| Current (no controls) | $1,398 | $156 | $1,999 | 0.96 | 6/9 |
| **Lower-drawdown** | $562 | $63 | **$108** | **2.8** | 7/9 |

Reality checks: betting the opposite side loses $1,795 (Sharpe -4.1); +2c slippage still makes money (Sharpe 2.2);
weekly bootstrap 90% range $204-$910, 0.2% chance of <= $0. Feeding the model a 5-minute-old price kills most of the edge,
so it needs a fresh spot price. Warning: 2026 Q3 made only $5 - the edge may be fading.
The model overstates its edge ~3x (actual win rate sits a third of the way from price to model), which is why the 12c margin works.

## Running automatically (nothing needed from you)

- **Recorder** (`record.yml`): Kalshi + Polymarket + spot prices every 5 minutes, packed into daily releases.
- **Forward test 1** (`forward.yml` -> FORWARD.md): ETH, rolling + volview rule, frozen 2026-10-01.
- **Forward test 2** (`forward.yml` -> FORWARD_BASE.md): the baseline rule on BTC + ETH ranges, frozen 2026-10-01 after the database test.
- Pre-registered pass mark for both: day-level t > 2 after at least 60 days (~early December 2026).

## Honest odds

About **25-30%** that the range edge holds live (Sharpe ~1, drawdowns about a year of profit). Even then, it's worth ~$100-200 a month at realistic sizes unless order books
deepen. Don't put money in before the forward tests pass. If they do, the next step is the read-only live watcher on an
AWS us-east-2 server (needs your Kalshi API key added as a GitHub secret).

Also done today: ppc-forecaster **0.3.1** released on PyPI (`auto` no longer locks onto one model on short series).
