# Pre-registered go-live and scale-up plan for the range bot (frozen 2026-10-03, before any verdict)

Written before the forward tests can say anything, so the December decision is mechanical, not a judgement made
after seeing results. Nothing here may change once forward results come in. Source numbers: results/CAPACITY.md
(holdout Jan-Sep 2026), results/FORWARD.md, results/FORWARD_BASE.md.

## 1. Gate (unchanged from the forward tests)
A rule goes live only if its own forward test shows **day-level t > 2 after at least 60 scored days**:
- Forward test 1: ETH hourly ranges, 15 min after open, rolling recalibration, > 5c edge, 100 contracts.
- Forward test 2: baseline rule, BTC + ETH hourly ranges, 15 min after open, > 5c edge.
If neither passes: no live trading; the range bot is closed. If both pass: start with test 2's rule (more markets),
add test 1's rule only after step 3 below.

## 2. Live start (user runs it; Claude never places orders)
- `live/watcher.py` configured to the passing rule exactly (series, 15-min timing, margin), signals to signals.jsonl.
- `live/executor.py --live` with: max 25 contracts/order, 3 orders/event, $75/day at risk, kill switch file.
- Expected from the holdout at cap 25: ~$63/month, max drawdown ~$108.

## 3. Scale steps (each needs 30 live days at the current step)
| step | max contracts | daily budget | expected $/month (holdout) | holdout max DD |
|---|---|---|---|---|
| A | 25 | $75 | 63 | 108 |
| B | 50 | $150 | 100 | 197 |
| C | 100 | $300 | 162 | 359 |
| D | 250 (ceiling) | $600 | 221 | 580 |
Move up one step only if, over the last 30 live days, realised P&L >= 0 AND realised fill rate (filled / signalled
contracts) >= 50%. Never above 250: the capacity sweep shows uncapped/1000 sizes lose most of the edge (holdout Sharpe
1.0 -> 0.2).

## 4. Stop rules (any one halts trading; restart only by repeating step A)
- Drawdown from peak > 2x the current step's holdout max DD.
- 30-day realised P&L < -1x the step's expected monthly profit.
- Realised edge per filled contract below 0 over 200+ filled contracts.
- Any data-feed fault (the watcher's collapsed-vol guard firing more than once a day, or Kalshi API errors > 5%/h).

## 5. What is NOT allowed
Changing margin, timing, series or model after seeing live results; adding new series (alt coins failed);
removing the cap; trading the market-making, weather, index, nowcast or Polymarket variants (all failed).
