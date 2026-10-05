# Kalshi weekly TSA screenings (KXTSAW): nowcast vs real trades

Entries: 3229

## Accuracy (Brier)

| half    |    n |   model |   traded_price |
|:--------|-----:|--------:|---------------:|
| holdout |  931 |  0.118  |         0.0955 |
| train   | 2298 |  0.1735 |         0.1228 |

## Picked on 2023-2025

|   margin_c |   bets |   c_per_bet |   avg_contracts |   total_$ |   per_month_$ |   max_dd_$ |   day_t | months_pos   |
|-----------:|-------:|------------:|----------------:|----------:|--------------:|-----------:|--------:|:-------------|
|          3 |    189 |        6.67 |            56   |       485 |            13 |        489 |    1.06 | 19/36        |
|          5 |    166 |        6.71 |            57.2 |       499 |            14 |        502 |    1.1  | 20/36        |
|          8 |    142 |        6.86 |            59.6 |       468 |            13 |        513 |    1.05 | 15/36        |
|         12 |    112 |        4.55 |            58.2 |       241 |             7 |        517 |    0.55 | 14/36        |

Chosen: margin 5c

## Holdout 2026 (run once)

| bot                                 |   bets |   c_per_bet |   avg_contracts |   total_$ |   per_month_$ |   max_dd_$ |   day_t | months_pos   |
|:------------------------------------|-------:|------------:|----------------:|----------:|--------------:|-----------:|--------:|:-------------|
| model                               |     81 |       -0.39 |            45.7 |      -150 |           -17 |        276 |   -0.79 | 3/9          |
| placebo: last year's week, unscaled |     75 |       -2.78 |            39.7 |      -158 |           -18 |        252 |   -0.84 | 5/9          |
