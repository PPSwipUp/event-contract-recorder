# Polymarket BTC/ETH weekly+monthly hit-price markets vs the frozen touch model

Entries (first taker trade per market/side/day, strike not yet touched): 30085

## Accuracy (Brier)

|                         |     n |   model |   traded_price |
|:------------------------|------:|--------:|---------------:|
| ('holdout', 'bitcoin')  | 11476 |  0.0762 |         0.0725 |
| ('holdout', 'ethereum') | 10202 |  0.0892 |         0.0839 |
| ('train', 'bitcoin')    |  3983 |  0.1078 |         0.1093 |
| ('train', 'ethereum')   |  4424 |  0.1008 |         0.0994 |

## Picked on 2025-07..12

|   margin_c |   bets |   c_per_bet |   avg_shares |   total_$ |   per_month_$ |   max_dd_$ |   week_t | months_pos   |
|-----------:|-------:|------------:|-------------:|----------:|--------------:|-----------:|---------:|:-------------|
|          3 |    956 |       -1.48 |         91.6 |     -1503 |          -251 |       4515 |    -0.56 | 3/6          |
|          5 |    630 |       -0.28 |         91.2 |      -299 |           -50 |       2791 |    -0.15 | 2/6          |
|          8 |    351 |        0.3  |         91.5 |         2 |             0 |       1639 |     0    | 2/6          |
|         12 |    135 |        0.62 |         87.2 |       231 |            39 |        373 |     0.25 | 5/6          |
|         20 |     14 |       11.7  |         86.3 |       106 |            18 |        186 |     0.36 | 2/6          |

Chosen: margin 12c

## Holdout 2026-01..09 (run once)

| bot                       |   bets |   c_per_bet |   avg_shares |   total_$ |   per_month_$ |   max_dd_$ |   week_t | months_pos   |
|:--------------------------|-------:|------------:|-------------:|----------:|--------------:|-----------:|---------:|:-------------|
| model                     |    616 |       -5.55 |         90.2 |     -3685 |          -368 |       3790 |    -2.04 | 2/10         |
| model, cap 500            |    616 |       -5.55 |        401.9 |    -19697 |         -1970 |      20051 |    -2.18 | 2/10         |
| placebo: 7-day-stale spot |   1974 |       -4.36 |         94.5 |     -9385 |          -939 |      13020 |    -1.65 | 3/10         |

### holdout by asset / kind / side

|                            |   bets |   c_per_bet |
|:---------------------------|-------:|------------:|
| ('bitcoin', 'max', 'no')   |    120 |       -4.12 |
| ('bitcoin', 'max', 'yes')  |     18 |      -11.86 |
| ('bitcoin', 'min', 'no')   |    141 |        1.36 |
| ('bitcoin', 'min', 'yes')  |      6 |       -4.42 |
| ('ethereum', 'max', 'no')  |    181 |      -16.32 |
| ('ethereum', 'max', 'yes') |      8 |      -15.11 |
| ('ethereum', 'min', 'no')  |    137 |        1.6  |
| ('ethereum', 'min', 'yes') |      5 |       -3.69 |
