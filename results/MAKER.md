# Market-making range bot (BTC + ETH hourly ranges): sell to takers who overpay per the model

Taker trades: 600513

## Margin picked on TRAIN (25% fill)

|   margin_c |   train_fills |   train_contracts |   train_c_per_contract |   train_per_month_$ |   train_max_dd_$ |   train_day_t | train_months_pos   |   train_sharpe |
|-----------:|--------------:|------------------:|-----------------------:|--------------------:|-----------------:|--------------:|:-------------------|---------------:|
|          2 |         47136 |           1098063 |                   4    |                3139 |             2434 |          8.15 | 14/14              |           7.49 |
|          5 |         24383 |            517628 |                   6.11 |                2258 |             1092 |          8.54 | 14/14              |           7.84 |
|          8 |         13431 |            260105 |                   9.04 |                1680 |              644 |          8.6  | 14/14              |           7.89 |
|         12 |          6807 |            123251 |                  12.93 |                1138 |              624 |          8.22 | 14/14              |           7.53 |
|         20 |          2214 |             37748 |                  17.58 |                 474 |              275 |          6.51 | 14/14              |           5.95 |

Chosen 8c

## HOLDOUT 2026 (run once)

|   fill |   cap |   fills |   contracts |   c_per_contract |   per_month_$ |   max_dd_$ |   day_t | months_pos   |   sharpe |
|-------:|------:|--------:|------------:|-----------------:|--------------:|-----------:|--------:|:-------------|---------:|
|   0.25 |    25 |   21177 |      209886 |             4.5  |          1049 |       1259 |    4.05 | 8/9          |     4.68 |
|   0.25 |   100 |   21188 |      308160 |             4.36 |          1492 |       2287 |    3.97 | 8/9          |     4.59 |
|   0.5  |    25 |   24465 |      305496 |             4.7  |          1596 |       1821 |    4.31 | 8/9          |     4.99 |
|   0.5  |   100 |   24485 |      532742 |             4.67 |          2765 |       3456 |    4.26 | 8/9          |     4.92 |

Placebo (join the taker on the same holdout trades): -8.81c per contract over 32368 trades
