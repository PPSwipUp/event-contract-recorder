# Plan (frozen 2026-10-04 before any results): fair-value-guarded market making on KXCRYPTOLEAD15M

Market: every 15 min Kalshi asks "which of BTC, ETH, SOL, XRP, HYPE has the highest return over the window"
(CF Benchmarks 60-s TWAP at start and end); 5 YES/NO markets per window, ~$20 incentive pool per market per window.
Goal: earn Liquidity Incentive rewards without losing more than that to informed fills.
Nothing below may be changed after results are seen; any change = a new, separately labelled test.

## Phase 1 - fair-value engine (offline, historical)
- Model: at time t in the window, return so far r_i = ln(P_i(t) / P_i(start)) from 1-min prices (Coinbase for
  BTC/ETH/SOL/XRP, Hyperliquid for HYPE); remaining minutes simulated by bootstrapping JOINT 1-min return vectors
  of the five coins from the previous 3 days (keeps correlation and fat tails); 4,000 paths;
  P(coin i leads) = share of paths where r_i + remaining_i is the largest.
- Test: the 4,001 settled windows (2026-08-20 .. 10-04). Train = before 2026-09-20, holdout = from 09-20.
  Compare model vs the market's own mid (1-min candles) at 3, 7 and 11 minutes into each window: Brier score.
- GATE: the model must be at least as accurate as the market mid on the holdout (Brier difference <= 0.002).
  If it is clearly worse, the strategy stops here (we'd be quoting around a worse number than the crowd's).

## Phase 2 - paper market maker (live, read-only), four variants run side by side on the same windows
Common: 100 contracts per side, quotes refreshed every 2 s, fills only from real trades strictly THROUGH our price
(back of queue), positions settled at the official result, conservative maker fee ceil(1.75 n p (1-p)),
rewards by Kalshi's published scoring incl. back-of-queue and the two-sided exclusion.
  A  baseline: join the best bid on YES and NO (= live/kxlip.py's rule, restricted to this series)
  B  guard: bid only at prices <= fair - 3c and ask only >= fair + 3c (YES side; NO mirrored); if the best bid is
     above the guard, rest at the guard price (scored with the discount) instead of joining
  C  guard + pull: B, plus cancel all quotes for 10 s when any coin moves > 0.15% within 5 s
  D  guard + pull + stop: C, plus no quotes in the last 3 minutes of each window
Fixed parameters: buffer 3c, pull 0.15% / 5 s / 10 s pause, stop 3 min, bootstrap 3 days, 4,000 paths.

## Phase 3 - evaluation
- Primary metric per variant: net $ = rewards + settled fill P&L - maker fees, per online hour; t-stat over
  15-min windows. Run 3 days (curfew hours excluded), then a CONFIRMATION run of 3 more days on the single best
  variant with the same parameters.
- PASS only if the confirmation run is net positive with window-level t > 2. Otherwise the idea is closed.
- Report also: fills per hour, average fill mark-out vs settlement, share of snapshots excluded.

## Constraints
- Read-only; Claude never places orders. Real use needs the user's Kalshi account, trading from the US.
- Expected scale if it works: the pool is ~$80/h across the five markets; a realistic share is a fraction of that.
