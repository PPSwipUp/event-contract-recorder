# Plan (frozen 2026-10-04 23:40, before the variant has run): Polymarket paper LP, "tight + calm pull"

Variant label: `_tight_calm` (live/pmlp.py --size 500 --dist tick --tag _tight_calm --calm).
Runs side by side with the existing `_tight` run (same code, same fills, same reward formula).
Nothing below may change after results are seen; any change = a new, separately labelled run.

## Rule
- Identical to `_tight`: join the touch (one tick grid), 500 shares/side, back-of-queue fills (only prints strictly
  through our price), inventory cap 2x size, quotes dropped after a gap > 5 min.
- Market choice unchanged: highest daily reward pools among markets ending > 14 days out with mid in [0.10, 0.90].
  NEW, applied every loop: a market whose end date is now <= 14 days away, or whose mid leaves [0.10, 0.90], is
  no longer quoted (existing runs only apply this at start-up).
- Pull: no quotes while the market's trailing-24h jumpiness ("day" in results/PM_JUMP.md = mean |hourly price
  change| over the last 24 hours, from CLOB prices-history, refreshed hourly) is >= 0.009583, the frozen top-decile
  threshold in backfill/data_local/pmjump/calm_threshold.txt.  No reward accrues while pulled.

## Evaluation
- Burn-in: the first 2 days after launch are not scored.  Then a 5-day confirmation period.
- Metric: net $ = rewards + mark-to-mid change, per market-day; t-stat over market-days (clustered by market).
- PASS only if `_tight_calm` is net positive with t > 2 in the confirmation period.  Also reported: the same metric
  for `_tight` over the same days, fills, mark-outs (+5 m / +1 h / +24 h / settlement), share of time pulled.

## Prior evidence (stated before the run)
The 60-day replay of this exact idea (results/PM_LP_REPLAY.md, touch/back + calm) lost -$49/day (t -2.7), and real
maker wallets in these markets lost -$1.02M against +$493k rewards (LP_WALLETS.md).  Expected outcome: FAIL.

## Relevance to the user (US resident)
Polymarket international bars US persons.  Polymarket US runs its own Liquidity Incentive Program with Kalshi-style
scoring (Discount^ticks x size, Target Size, optional Max Spread) plus a maker rebate of 0.0125 x C x p(1-p).
This paper run scores with the international formula, so even a PASS needs re-scoring under Polymarket US rules.
