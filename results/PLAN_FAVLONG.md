# Plan (frozen 2026-10-04 before any results): favourite-longshot bias across Kalshi

Idea: retail overpays for longshots, so buying the favourite (YES or NO side priced 90-97c) at the ask wins more
often than its price implies, net of fees.  Nothing below may be changed after results are seen.

## Data
- Universe: every Kalshi market (non-multivariate) that settled yes/no between 2026-08-15 and 2026-10-03
  (hourly candles do not exist before ~mid-Aug).  Series with < 5 settled events dropped.
- Sample: per series up to 40 events, chosen at random (seed 0) so no series (e.g. crypto strike ladders)
  dominates.  Markets with total volume < 1,000 contracts dropped.
- Prices: Kalshi event candlesticks, 60-min period; the yes_bid / yes_ask CLOSE of the last candle ending at or
  before the decision time.  An ask of $1.00 / bid of $0 or missing = no quote.

## Rule
- Decision time: PRIMARY 6 h before close (market must have opened >= 12 h before close);
  SECONDARY 1 h before close (opened >= 2 h before).
- If yes_ask in [0.90, 0.97]: buy YES at yes_ask.  If no_ask = 1 - yes_bid in [0.90, 0.97]: buy NO at no_ask.
- Size 100 contracts; taker fee ceil(0.07 x 100 x p x (1-p)) dollars-cents per order with multiplier 1 for every
  series (conservative: some series are 0.5 or fee-free).
- P&L per contract = payout (1 or 0) - ask - fee/100.

## Test
- Train: close < 2026-09-15; holdout: close >= 2026-09-15.
- Primary metric: mean net P&L per contract on the PRIMARY rule, holdout.  Standard error clustered by series.
- GATE: holdout mean > 0 AND clustered t > 2.  Also reported (not gating): calibration table by 1c price bucket
  (win rate vs price), by category, the 1 h rule, and the mirror trade (buying the 3-10c longshot), which should be
  negative if the bias is real.
- Caveat stated up front: candle quotes say nothing about size at the ask; a pass would need a paper run with
  real book depth before any money.

## If PASS
Paper run on live books (read-only, 100 contracts, real ask depth), 2 weeks, same rule, same gate.
## If FAIL
Close the idea; move to idea 1 (Kalshi S&P / Nasdaq ranges vs options-implied odds).
