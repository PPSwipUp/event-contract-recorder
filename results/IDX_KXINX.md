# Volatility model vs Kalshi KXINX (daily close ranges), SPY as the price feed

Entries (first real trade per market/side/30-min slot, 10:00-15:30 ET): 15533; vol scale k = 0.97.

## Who is more accurate? (lower Brier is better)

|   day |     n |   brier_model |   brier_price |
|------:|------:|--------------:|--------------:|
|  2025 |  4551 |        0.1695 |        0.1634 |
|  2026 | 10982 |        0.1463 |        0.1431 |

## Edge margin chosen on TRAIN (2025)

|   margin_c |   train_bets |   train_c_per_bet |   train_total_$ |   train_per_month_$ |   train_max_dd_$ |   train_day_t | train_months_pos   |   train_avg_contracts |
|-----------:|-------------:|------------------:|----------------:|--------------------:|-----------------:|--------------:|:-------------------|----------------------:|
|          2 |          349 |            -12.1  |           -2887 |              -262.5 |             2934 |         -3.44 | 2/11               |                  64.7 |
|          5 |          184 |             -8.62 |           -1060 |               -96.4 |             1103 |         -1.72 | 4/11               |                  64.2 |
|          8 |           97 |             -9.25 |            -694 |               -63.1 |              789 |         -1.4  | 5/11               |                  66.3 |
|         12 |           55 |             -3.72 |             -60 |                -5.4 |              296 |         -0.17 | 7/11               |                  68.5 |
|         20 |           26 |             -3.22 |             -34 |                -3.1 |              215 |         -0.16 | 5/11               |                  70   |

Chosen margin: 5c

## HOLDOUT (2026, run once)

| bot                    |   hold_bets |   hold_c_per_bet |   hold_total_$ |   hold_per_month_$ |   hold_max_dd_$ |   hold_day_t | hold_months_pos   |   hold_avg_contracts |
|:-----------------------|------------:|-----------------:|---------------:|-------------------:|----------------:|-------------:|:------------------|---------------------:|
| model                  |         611 |            -4.98 |          -3615 |             -401.7 |            3724 |        -2.64 | 3/9               |                   65 |
| placebo: opposite side |         611 |            -4.98 |           2476 |              275.1 |             914 |         1.84 | 6/9               |                   65 |

### Holdout by side / time of day

| taker   |   bets |   c_per_bet |   dollars |
|:--------|-------:|------------:|----------:|
| no      |    342 |       -5.7  |  -2359.02 |
| yes     |    269 |       -4.06 |  -1256.37 |

|   slot |   bets |   c_per_bet |   dollars |
|-------:|-------:|------------:|----------:|
|      0 |     96 |      -10.18 |   -891.98 |
|      1 |    172 |       -6.44 |   -892.45 |
|      2 |    343 |       -2.79 |  -1830.96 |
