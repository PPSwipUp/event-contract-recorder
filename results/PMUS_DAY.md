# Polymarket US liquidity incentives: five frozen variants on recorded day-of books (PLAN_PMUS.md)

Day 2026-10-05; markets recorded in window: 603; snapshots: 434068; thin set: 122 markets
Pools shared across all of a program's markets (both games), per the rewards page.  Fills are a book-based proxy (no public trade feed).

## Per variant and game ($)

|                             |   markets |   reward |   rebate |   fill_pnl |      net |   fills |   capital |   quoted_h |   net_per_h |
|:----------------------------|----------:|---------:|---------:|-----------:|---------:|--------:|----------:|-----------:|------------:|
| ('A', 'cws-cle-2026-10-05') |       304 |   262.15 |   358.37 |      -2165 | -1544.49 |     339 |    150450 |       5.99 |     -257.84 |
| ('A', 'nyy-tb-2026-10-05')  |       296 |   231.76 |   286.57 |       -670 |  -151.67 |     266 |    146538 |       5.99 |      -25.32 |
| ('B', 'cws-cle-2026-10-05') |        62 |    52.91 |   113.92 |        345 |   511.83 |      93 |     30640 |       5.99 |       85.45 |
| ('B', 'nyy-tb-2026-10-05')  |        60 |    48.45 |    46.18 |        710 |   804.63 |      55 |     29700 |       5.99 |      134.33 |
| ('C', 'cws-cle-2026-10-05') |        62 |    36.74 |    74.34 |       1870 |  1981.08 |      59 |     30020 |       5.99 |      330.73 |
| ('C', 'nyy-tb-2026-10-05')  |        60 |    31.92 |    30    |        390 |   451.92 |      39 |     29100 |       5.99 |       75.45 |
| ('D', 'cws-cle-2026-10-05') |        62 |    21.89 |    47.36 |        805 |   874.25 |      39 |     30005 |       3    |      291.42 |
| ('D', 'nyy-tb-2026-10-05')  |        60 |    16.13 |    14.05 |        150 |   180.19 |      24 |     29100 |       3    |       60.06 |
| ('E', 'cws-cle-2026-10-05') |        58 |     2.35 |     6.24 |        -80 |   -71.41 |       6 |     28105 |       0.33 |     -216.39 |
| ('E', 'nyy-tb-2026-10-05')  |        57 |     2.03 |     1.07 |        110 |   113.11 |       1 |     27645 |       0.38 |      297.66 |

## Fills

|                             |   n |   markout_5m_c |   settled_share |
|:----------------------------|----:|---------------:|----------------:|
| ('A', 'cws-cle-2026-10-05') | 339 |          -2.12 |               1 |
| ('A', 'nyy-tb-2026-10-05')  | 266 |          -1.74 |               1 |
| ('B', 'cws-cle-2026-10-05') |  93 |          -3.3  |               1 |
| ('B', 'nyy-tb-2026-10-05')  |  55 |          -2.82 |               1 |
| ('C', 'cws-cle-2026-10-05') |  59 |          -3.65 |               1 |
| ('C', 'nyy-tb-2026-10-05')  |  39 |          -2.78 |               1 |
| ('D', 'cws-cle-2026-10-05') |  39 |          -4.73 |               1 |
| ('D', 'nyy-tb-2026-10-05')  |  24 |          -2.38 |               1 |
| ('E', 'cws-cle-2026-10-05') |   6 |          -3.33 |               1 |
| ('E', 'nyy-tb-2026-10-05')  |   1 |          -1.5  |               1 |

## Median size at best bid + best offer (others), by hours before start

|    |   cws-cle-2026-10-05 |   nyy-tb-2026-10-05 |
|---:|---------------------:|--------------------:|
|  0 |                  875 |                 963 |
|  1 |                  739 |                1183 |
|  2 |                 1129 |                1488 |
|  3 |                  938 |                1133 |
|  4 |                  653 |                1021 |
|  5 |                  431 |                1000 |

First read (frozen rule: a variant must be net positive in both games to justify 5 more game days): A: no, B: both +, C: both +, D: both +, E: no

## Fake-check (2026-10-06) — VERDICT: WEAK (expected net negative; the pass is settlement luck)
- Net is driven by fills held to settlement (directional prop bets), not by rewards. Rewards + rebate per game: B $95-167,
  C $62-111, D $30-69. Fill mark-out 5 min after the fill is NEGATIVE for every variant (-2.4c to -4.7c per contract).
- Mark-out-based net (rewards + rebate + fills x 500 x 5-min mark-out): B -$1,368 / -$681, C -$966 / -$480,
  D -$853 / -$256 per game (CWS-CLE / NYY-TB). All negative.
- Settlement P&L bootstrap over markets (treats props as independent, which they are not - same game/pitcher):
  B 95% [-$2,000, +$4,533], C [-$206, +$4,940], D [-$2,584, +$4,269]; top 3 markets = 138% / 66% / 16% of the total.
  Real independent units = 2 games. Best of 5 variants picked.
- Per the frozen plan B, C, D go on to 5 more game days; expectation: net negative once settlement luck averages out.
