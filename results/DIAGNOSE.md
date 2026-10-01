# Diagnosing the range bot (BTC + ETH hourly ranges, Nov 2024 - Sep 2026, 28 Sep excluded)

6229 bets, total $3051.

A real edge should make MORE money where the model predicts a BIGGER edge (first table).

### By predicted edge

| edge_band   |   bets |   win_rate |   avg_edge_predicted_c |   avg_profit_c |   total_$ |
|:------------|-------:|-----------:|-----------------------:|---------------:|----------:|
| 5-8c        |   3361 |      0.558 |                  6.261 |          1.637 |    560.44 |
| 8-12c       |   1607 |      0.518 |                  9.598 |          1.087 |  -1107.8  |
| 12-20c      |    885 |      0.527 |                 14.969 |          6.112 |   1820.48 |
| >20c        |    376 |      0.452 |                 33.852 |         11.684 |   1777.94 |

### By contract price

| price_band   |   bets |   win_rate |   avg_edge_predicted_c |   avg_profit_c |   total_$ |
|:-------------|-------:|-----------:|-----------------------:|---------------:|----------:|
| <15c         |    588 |      0.158 |                 13.463 |          4.168 |   475.811 |
| 15-50c       |   2669 |      0.352 |                 10.794 |          1.783 |   690.1   |
| 50-85c       |   2379 |      0.747 |                  9.142 |          4.03  |  1670.38  |
| >85c         |    593 |      0.902 |                  6.691 |          0.431 |   214.774 |

### By side

| side   |   bets |   win_rate |   avg_edge_predicted_c |   avg_profit_c |   total_$ |
|:-------|-------:|-----------:|-----------------------:|---------------:|----------:|
| no     |   2934 |      0.735 |                  8.906 |          3.542 |  2332.44  |
| yes    |   3295 |      0.361 |                 11.02  |          2.021 |   718.623 |

### By market

| series   |   bets |   win_rate |   avg_edge_predicted_c |   avg_profit_c |   total_$ |
|:---------|-------:|-----------:|-----------------------:|---------------:|----------:|
| KXBTC    |   3544 |      0.51  |                  9.735 |          2.672 |  2236.56  |
| KXETH    |   2685 |      0.573 |                 10.407 |          2.824 |   814.496 |

### By time of day (UTC)

| hours   |   bets |   win_rate |   avg_edge_predicted_c |   avg_profit_c |   total_$ |
|:--------|-------:|-----------:|-----------------------:|---------------:|----------:|
| 00-05   |   1433 |      0.544 |                  9.477 |          2.393 |  -637.077 |
| 06-11   |    701 |      0.569 |                  9.834 |          6.164 |   115.33  |
| 12-17   |   2279 |      0.512 |                  9.128 |          1.047 |  -227.95  |
| 18-23   |   1816 |      0.551 |                 11.655 |          3.808 |  3800.76  |

### Remove one month at a time

Total with each month removed: min $1717, max $4077 (removing 2026-03 hurts most). Months positive: 17/24.

### Calibration of the bets taken (does the model's probability match reality?)

| model_p     |   bets |   model_says |   price_paid |   actually_won |
|:------------|-------:|-------------:|-------------:|---------------:|
| (0.0, 0.1]  |      9 |        0.074 |        0.012 |          0     |
| (0.1, 0.3]  |    834 |        0.23  |        0.145 |          0.164 |
| (0.3, 0.5]  |   1521 |        0.396 |        0.284 |          0.305 |
| (0.5, 0.7]  |   1275 |        0.599 |        0.469 |          0.528 |
| (0.7, 0.9]  |   1522 |        0.804 |        0.686 |          0.736 |
| (0.9, 1.01] |   1068 |        0.952 |        0.841 |          0.89  |
