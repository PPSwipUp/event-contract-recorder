# Plan (frozen 2026-10-06 before the run starts): Polymarket US paper LP on non-sports daily reward programs

Venue the user can use (US resident).  Read-only paper run from public data (gateway books + incentives list).
Nothing below may change after results are seen; any change = a new, separately labelled run.

## Markets
At start: every market in an active non-sports (category != SPR) liquidity program with period daily / daily_event,
ranked by its program's pool / number of markets in the program; keep the top 20 with a two-sided book, mid in
[0.10, 0.90] and no event start within 14 days.  Re-checked every loop: a market leaving [0.10, 0.90] or coming within
14 days of its start is no longer quoted.

## Quoting (two labelled runs, same markets)
  _join  1,000 contracts at the best bid and best offer (back of the queue)
  _back  1,000 contracts one tick behind the best bid and best offer
Every 30 s; a side is not re-quoted for 5 min after it fills; inventory cap 2,000 per market; quotes dropped after a
gap > 5 min (school Wi-Fi blackout).

## Scoring (docs.polymarket.us/incentives/liquidity)
Per snapshot and side: walk from the best price to Target Size, our order at the back of its level, score
Discount^(ticks from best) x size; a side pays only if it reaches Target Size; Max Spread enforced when set.
Money = our share x pool x dt / 86,400 / (2 x markets in the program).  Maker rebate 0.0125 x n x p(1-p) per fill.

## Fills (no public trade feed)
A resting bid at b fills if the next snapshot's best bid is below b AND the market's sharesTraded increased (mirror for
offers).  Every fill logged with the mid at the time; mids of quoted markets logged each loop for mark-outs.

## Evaluation after 7 days (judged WITHOUT outcomes)
- Fill mark-out vs mid at +5 min, +1 h, +24 h (cents/contract, t clustered by market).
- Outcome-free net = rewards + rebate + inventory marked to the current mid.
- PASS only if net > 0 AND the +1 h mark-out is not significantly negative (t > -2).  Then 7 more days to confirm.
