# Volatility model vs Kalshi KXNASDAQ100 (daily close ranges), QQQ as the price feed

Entries (first real trade per market/side/30-min slot, 10:00-15:30 ET): 7048; vol scale k = 0.97.

## Who is more accurate? (lower Brier is better)

|   day |    n |   brier_model |   brier_price |
|------:|-----:|--------------:|--------------:|
|  2025 | 1998 |        0.1654 |        0.1643 |
|  2026 | 5050 |        0.1382 |        0.1378 |

## Edge margin chosen on TRAIN (2025)

|   margin_c |   train_bets |   train_c_per_bet |   train_total_$ |   train_per_month_$ |   train_max_dd_$ |   train_day_t | train_months_pos   |   train_avg_contracts |
|-----------:|-------------:|------------------:|----------------:|--------------------:|-----------------:|--------------:|:-------------------|----------------------:|
|          2 |          102 |             -7.11 |            -222 |               -20.2 |              332 |         -0.63 | 5/11               |                  55.5 |
|          5 |           56 |             -7.97 |            -226 |               -20.5 |              341 |         -0.75 | 4/11               |                  62.9 |
|          8 |           32 |             -4.1  |             106 |                 9.7 |               94 |          0.52 | 8/11               |                  51.5 |
|         12 |           15 |              6.14 |             129 |                11.7 |               78 |          0.78 | 5/11               |                  51.5 |
|         20 |            7 |             14.24 |             112 |                10.1 |                7 |          1.65 | 4/11               |                  35.6 |

Chosen margin: 2c

## HOLDOUT (2026, run once)

| bot                    |   hold_bets |   hold_c_per_bet |   hold_total_$ |   hold_per_month_$ |   hold_max_dd_$ |   hold_day_t | hold_months_pos   |   hold_avg_contracts |
|:-----------------------|------------:|-----------------:|---------------:|-------------------:|----------------:|-------------:|:------------------|---------------------:|
| model                  |         363 |            -3.27 |           -960 |             -106.6 |            1083 |        -1.41 | 3/9               |                 50.8 |
| placebo: opposite side |         363 |            -3.27 |            479 |               53.2 |             788 |         0.7  | 6/9               |                 50.8 |

### Holdout by side / time of day

| taker   |   bets |   c_per_bet |   dollars |
|:--------|-------:|------------:|----------:|
| no      |    204 |       -2.57 |   -644.58 |
| yes     |    159 |       -4.17 |   -315.2  |

|   slot |   bets |   c_per_bet |   dollars |
|-------:|-------:|------------:|----------:|
|      0 |     35 |        8.69 |    119.08 |
|      1 |     78 |        0.36 |    -74.42 |
|      2 |    250 |       -6.07 |  -1004.44 |
