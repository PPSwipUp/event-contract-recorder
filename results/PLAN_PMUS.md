# Plan (frozen 2026-10-05 ~14:10 BST, before any day-of data exists): Polymarket US liquidity incentives, 5 variants

Data: live/pmusrec.py books every 30 s for every incentivised market of the MLB wild-card games of 2026-10-05
(CWS-CLE, NYY-TB) during each game's day-of period (6 h before eventStartTime until start).  Public API only.
Nothing below may change after results are seen; any change = a new, separately labelled analysis.

## Scoring (Polymarket US rules, docs.polymarket.us/incentives/liquidity)
- Per snapshot and market side: walk from the best price outward to Target Size; orders inside score
  Discount^(ticks from best) x size; our order sits at the BACK of its price level.  A side pays only if it reaches
  Target Size (incl. ours); Max Spread applied where a program sets one.
- Program pool -> money: each snapshot carries pool x 30 s / period length.  Each market side is normalised to 1.0,
  so it gets 1 / (2 x markets in the program) of that slice; a side that does not qualify forfeits its slice
  (assumed NOT redistributed - conservative).  Our share of a side = our score / all scores on that side.
- Size: 500 contracts per side.  Maker rebate 0.0125 x n x p(1-p) per fill added.

## Fills (no public trade feed, so a book-based proxy)
- Our bid at price b is filled between snapshots if the next snapshot's best bid is < b (our level was cleared)
  AND the market's sharesTraded increased; same mirrored for our offer.  Whole 500 fills at b.  After a fill that
  side is not re-quoted for 5 minutes; inventory capped at 1,000 per market.
- Fill P&L marked to the market's final settlement price (gateway settlement) where available, else the last
  recorded mid.  Also reported: mark-out vs mid 5 min after the fill.

## Variants
  A  join the best bid and best offer on every market
  B  as A, only on the thinnest 20% of markets per game (lowest combined size at best bid + best offer in the
     first snapshot of the window - fixed at window start, no look-ahead)
  C  B, but quote one tick behind the best price on each side
  D  C, stop quoting 3 h before eventStartTime
  E  D, plus pull ALL of that game's quotes for 10 minutes whenever any of its markets' mid moved >= 3c since the
     previous snapshot

## Output
Per variant and game: rewards $, rebate $, fill P&L $, net $, net $/h of quoting, number of fills, capital
(max total $ resting), competition at the touch over time.  One day = 2 games, so this is a FIRST READ, not a
verdict: a variant must be net positive in both games to justify recording more game days (pre-registered next
step: 5 more game days, same code, pass = net positive with game-level t > 2).
