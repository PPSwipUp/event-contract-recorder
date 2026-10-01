# Improving the range bot (BTC + ETH hourly ranges)

729 risk-control combinations scored on TRAIN (Nov 2024 - Dec 2025); the best TRAIN Calmar is then run once on HOLDOUT (Jan - Sep 2026, 28 Sep excluded).

## Top 10 on TRAIN

| per_event   |   size |   crowd | calm   | stop_$   |   margin |   train_bets |   train_total_$ |   train_per_month_$ |   train_max_dd_$ |   train_calmar |   train_sharpe | train_months_pos   |   train_worst_month_$ |
|:------------|-------:|--------:|:-------|:---------|---------:|-------------:|----------------:|--------------------:|-----------------:|---------------:|---------------:|:-------------------|----------------------:|
| all         |     25 |     200 | 2.0    | 200      |       12 |          500 |          733.74 |               52.36 |            81.36 |           9.02 |           3.36 | 13/14              |                -34.68 |
| all         |     25 |     200 | 2.0    | none     |       12 |          500 |          733.74 |               52.36 |            81.36 |           9.02 |           3.36 | 13/14              |                -34.68 |
| all         |     25 |     200 | 2.0    | 100      |       12 |          500 |          733.74 |               52.36 |            81.36 |           9.02 |           3.36 | 13/14              |                -34.68 |
| all         |     25 |     200 | none   | 200      |       12 |          508 |          732.95 |               52.3  |            82.51 |           8.88 |           3.34 | 13/14              |                -34.68 |
| all         |     25 |     200 | none   | 100      |       12 |          508 |          732.95 |               52.3  |            82.51 |           8.88 |           3.34 | 13/14              |                -34.68 |
| all         |     25 |     200 | none   | none     |       12 |          508 |          732.95 |               52.3  |            82.51 |           8.88 |           3.34 | 13/14              |                -34.68 |
| 2           |     25 |     200 | 2.0    | none     |       12 |          499 |          717.13 |               51.18 |            81.36 |           8.81 |           3.3  | 13/14              |                -34.68 |
| 2           |     25 |     200 | 2.0    | 100      |       12 |          499 |          717.13 |               51.18 |            81.36 |           8.81 |           3.3  | 13/14              |                -34.68 |
| 2           |     25 |     200 | 2.0    | 200      |       12 |          499 |          717.13 |               51.18 |            81.36 |           8.81 |           3.3  | 13/14              |                -34.68 |
| 2           |     25 |     200 | none   | none     |       12 |          507 |          716.34 |               51.12 |            82.51 |           8.68 |           3.28 | 12/14              |                -34.68 |

## Chosen controls vs current bot

Chosen: per_event=all, size=25, crowd=200, calm=2.0, stop=200, margin=12

| bot                       |   train_bets |   train_total_$ |   train_per_month_$ |   train_max_dd_$ |   train_calmar |   train_sharpe | train_months_pos   |   train_worst_month_$ |   hold_bets |   hold_total_$ |   hold_per_month_$ |   hold_max_dd_$ |   hold_calmar |   hold_sharpe | hold_months_pos   |   hold_worst_month_$ |
|:--------------------------|-------------:|----------------:|--------------------:|-----------------:|---------------:|---------------:|:-------------------|----------------------:|------------:|---------------:|-------------------:|----------------:|--------------:|--------------:|:------------------|---------------------:|
| current bot (no controls) |         2792 |         1643.38 |              117.27 |          1280.22 |           1.28 |           0.93 | 10/14              |              -1026    |        3435 |        1397.84 |             155.66 |         1999.3  |          0.7  |          0.96 | 6/9               |               -935   |
| chosen controls           |          500 |          733.74 |               52.36 |            81.36 |           9.02 |           3.36 | 13/14              |                -34.68 |         654 |         561.84 |              62.56 |          108.36 |          5.19 |          2.8  | 7/9               |                -70.8 |

## Is it real?

| check                                     |   all_bets |   all_total_$ |   all_max_dd_$ |   all_sharpe |   hold_total_$ |   hold_sharpe |
|:------------------------------------------|-----------:|--------------:|---------------:|-------------:|---------------:|--------------:|
| chosen bot                                |       1154 |       1295.58 |         108.36 |         3.04 |         561.84 |          2.8  |
| placebo: opposite side of every bet       |       1154 |      -1794.6  |        1812.46 |        -4.13 |        -830.48 |         -4.08 |
| +1c slippage per contract                 |       1154 |       1117.18 |         122.3  |         2.64 |         463.96 |          2.32 |
| +2c slippage per contract                 |       1154 |        938.77 |         136.25 |         2.23 |         366.07 |          1.83 |
| placebo: model given a 5-minute-old price |       3241 |        441.7  |         458.38 |         0.61 |         124.98 |          0.35 |

Holdout weekly block bootstrap: 90% interval for total profit $204 to $910 (median $561); share of resamples at or below zero: 0.2%.

Profit by quarter (chosen bot): 2024Q4 $48, 2025Q1 $354, 2025Q2 $195, 2025Q3 $59, 2025Q4 $78, 2026Q1 $318, 2026Q2 $239, 2026Q3 $5
