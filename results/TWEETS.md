# Polymarket 'Elon Musk # tweets' brackets vs a running-count nowcast

CHECK: tracker count lands in the winning bracket for 94 of 95 closed windows

Entries: 57281; negative-binomial size k = 4.22 (daily counts 2025-11-01..2026-04-01)

## Accuracy (Brier)

| half    |     n |   model |   traded_price |
|:--------|------:|--------:|---------------:|
| holdout | 29056 |  0.0828 |         0.0794 |
| train   | 28225 |  0.0653 |         0.0631 |

## Picked on 2025-11..2026-03

|   margin_c |   bets |   c_per_bet |   avg_shares |   total_$ |   per_month_$ |   max_dd_$ |   week_t | months_pos   |
|-----------:|-------:|------------:|-------------:|----------:|--------------:|-----------:|---------:|:-------------|
|          3 |   5527 |        1.52 |         96.1 |      7563 |          1513 |       3776 |     1.64 | 4/5          |
|          5 |   3405 |        2.3  |         96.3 |      7452 |          1490 |       1904 |     2.03 | 4/5          |
|          8 |   1505 |        3.18 |         96.1 |      4569 |           914 |       1141 |     1.52 | 4/5          |
|         12 |    692 |        5.43 |         95.9 |      3558 |           712 |        501 |     1.76 | 3/5          |
|         20 |    216 |        3.82 |         95.4 |       851 |           170 |        550 |     0.78 | 4/5          |

Chosen: margin 5c

## Holdout 2026-04..10 (run once)

| bot                       |   bets |   c_per_bet |   avg_shares |   total_$ |   per_month_$ |   max_dd_$ |   week_t | months_pos   |
|:--------------------------|-------:|------------:|-------------:|----------:|--------------:|-----------:|---------:|:-------------|
| model                     |   4420 |        0.54 |         91.7 |      1495 |           214 |       6273 |     0.26 | 5/7          |
| model, cap 500            |   4420 |        0.54 |        380   |      -411 |           -59 |      27298 |    -0.02 | 5/7          |
| placebo: count 24 h stale |   5491 |       -0.19 |         92.3 |     -1852 |          -265 |       5105 |    -0.38 | 3/7          |
