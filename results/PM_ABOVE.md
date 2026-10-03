# Polymarket daily BTC/ETH above-$K at noon vs the frozen vol model

Entries: 77117

## Accuracy (Brier)

|                         |     n |   model |   traded_price |
|:------------------------|------:|--------:|---------------:|
| ('holdout', 'bitcoin')  | 27214 |  0.0879 |         0.0876 |
| ('holdout', 'ethereum') | 19441 |  0.0812 |         0.0819 |
| ('train', 'bitcoin')    | 15082 |  0.1202 |         0.1201 |
| ('train', 'ethereum')   | 15380 |  0.1283 |         0.1272 |

## Picked on 2025-10..2026-01

|   margin_c |   bets |   c_per_bet |   avg_shares |   total_$ |   per_month_$ |   max_dd_$ |   week_t | months_pos   |
|-----------:|-------:|------------:|-------------:|----------:|--------------:|-----------:|---------:|:-------------|
|          3 |   1881 |       -2.68 |         81   |     -6121 |         -1530 |       7270 |    -2.59 | 0/4          |
|          5 |    873 |       -2.72 |         81.1 |     -3016 |          -754 |       4376 |    -1.42 | 0/4          |
|          8 |    242 |       -1.12 |         79.4 |      -866 |          -217 |       1202 |    -1.1  | 0/4          |
|         12 |     25 |       11.19 |         74.8 |       180 |            45 |         61 |     1.35 | 3/4          |
|         20 |      0 |      nan    |          0   |         0 |             0 |          0 |   nan    | 0/4          |

Chosen: margin 8c

## Holdout 2026-02..10 (run once)

| bot                       |   bets |   c_per_bet |   avg_shares |   total_$ |   per_month_$ |   max_dd_$ |   week_t | months_pos   |
|:--------------------------|-------:|------------:|-------------:|----------:|--------------:|-----------:|---------:|:-------------|
| model                     |    444 |       -1.82 |         80   |     -1498 |          -166 |       2423 |    -0.77 | 4/9          |
| model, cap 500            |    444 |       -1.82 |        313.1 |     -8253 |          -917 |       9940 |    -1.02 | 3/9          |
| placebo: 1-day-stale spot |   4296 |       -4.34 |         83.6 |    -21627 |         -2403 |      21744 |    -2.23 | 3/9          |

### holdout by asset / hours left

|                                                 |   bets |   c_per_bet |
|:------------------------------------------------|-------:|------------:|
| ('bitcoin', Interval(0, 1, closed='right'))     |      1 |        9.84 |
| ('bitcoin', Interval(6, 24, closed='right'))    |     44 |        4.95 |
| ('bitcoin', Interval(24, 200, closed='right'))  |    227 |       -1.18 |
| ('ethereum', Interval(0, 1, closed='right'))    |      1 |       59.55 |
| ('ethereum', Interval(6, 24, closed='right'))   |     37 |       -7.31 |
| ('ethereum', Interval(24, 200, closed='right')) |    134 |       -4.16 |
