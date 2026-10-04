# Plan (frozen 2026-10-04 before any results): Kalshi CPI month-over-month vs the Cleveland Fed nowcast

Markets: Kalshi CPI / KXCPI events, "Will CPI rise more than K% in <month>?" (headline CPI-U, seasonally adjusted,
month-over-month, single decimal), one ladder of strikes per release.  Nothing below may change after results.

## Fair value
- Nowcast n: Cleveland Fed daily "CPI Inflation" month-over-month nowcast for the target month
  (clevelandfed.org nowcast_month.json), the latest vintage dated strictly before the decision day.
- Error model: empirical residuals r = actual (Kalshi expiration_value, single decimal) - n, from TRAIN releases only.
  P(YES) = share of residuals with round(n + r, 1) > K.

## Entries (real trades)
- Window: trades from 24 h to 1 h before market close (close = minutes before the 08:30 ET release).
- Buy YES at the first trade in the window whose taker bought YES (that price was the ask); buy NO likewise from
  the first NO-taker trade.  One entry per market per side.
- Bet if model edge >= 5c after the taker fee ceil(0.07 x 100 x p x (1-p)) per 100-lot (margin fixed, not tuned).
- P&L per contract = payout - price - fee/100.

## Test
- Train: releases before 2025-01-01 (fits the residuals only).  Holdout: releases from 2025-01-01.
- GATE: holdout mean P&L per contract > 0 AND t > 2 with standard errors clustered by release.
- Also reported: Brier of model vs the entry price on the holdout, number of releases, and a placebo
  (nowcast replaced by the previous month's actual CPI).
- Caveat: entry prints show nothing about size; ~monthly sample is small, so a pass needs a forward paper run.
