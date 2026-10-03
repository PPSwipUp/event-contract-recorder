# Polymarket daily BTC/ETH price-range markets vs the frozen vol model

Entries: 54790

## Accuracy (Brier)

|                         |     n |   model |   traded_price |
|:------------------------|------:|--------:|---------------:|
| ('holdout', 'bitcoin')  | 19367 |  0.0928 |         0.0915 |
| ('holdout', 'ethereum') | 12057 |  0.0989 |         0.0976 |
| ('train', 'bitcoin')    | 13808 |  0.0919 |         0.0899 |
| ('train', 'ethereum')   |  9558 |  0.0944 |         0.0933 |

## Picked on 2025-09..2026-01

|   margin_c |   bets |   c_per_bet |   avg_shares |   total_$ |   per_month_$ |   max_dd_$ |   week_t | months_pos   |
|-----------:|-------:|------------:|-------------:|----------:|--------------:|-----------:|---------:|:-------------|
|          3 |   1256 |       -4.82 |         80.7 |     -6636 |         -1327 |       6805 |    -3.25 | 0/5          |
|          5 |    668 |       -3.73 |         82.7 |     -3236 |          -647 |       3299 |    -2.64 | 0/5          |
|          8 |    290 |        1.71 |         86.4 |      -151 |           -30 |        644 |    -0.23 | 2/5          |
|         12 |    114 |        4.37 |         88.7 |       274 |            55 |        450 |     0.54 | 4/5          |
|         20 |     19 |       16    |         86.1 |       173 |            35 |        109 |     1.2  | 3/5          |

Chosen: margin 12c

## Holdout 2026-02..10 (run once)

| bot                       |   bets |   c_per_bet |   avg_shares |   total_$ |   per_month_$ |   max_dd_$ |   week_t | months_pos   |
|:--------------------------|-------:|------------:|-------------:|----------:|--------------:|-----------:|---------:|:-------------|
| model                     |    193 |       -8.08 |         75   |     -1497 |          -166 |       1497 |    -2.18 | 1/9          |
| model, cap 500            |    193 |       -8.08 |        282.9 |     -6484 |          -720 |       6484 |    -2.16 | 1/9          |
| placebo: 1-day-stale spot |   1658 |       -4.65 |         83   |     -8810 |          -979 |       9006 |    -4.7  | 1/9          |

### holdout by asset / hours left

|                                                 |   bets |   c_per_bet |
|:------------------------------------------------|-------:|------------:|
| ('bitcoin', Interval(6, 24, closed='right'))    |     36 |        0.72 |
| ('bitcoin', Interval(24, 200, closed='right'))  |     65 |      -13.96 |
| ('ethereum', Interval(6, 24, closed='right'))   |     41 |       -9.43 |
| ('ethereum', Interval(24, 200, closed='right')) |     51 |       -5.69 |
