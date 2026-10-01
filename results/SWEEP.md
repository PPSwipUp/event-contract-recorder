# Wide sweep with a holdout

3888 configurations. TRAIN = August, VALID = 1-15 Sep, HOLDOUT = 16-30 Sep. t = day-level t-statistic.

## Does doing well in training predict the holdout? (if not, the 'best' configs are luck)

Rank correlation, train t vs validation t: **0.15**; train t vs holdout t: **0.27** (0 = no relation, 1 = perfect), over 1743 configs with >= 20 training bets.

Holdout cents/bet: top-25 by training 8.31 vs all configs 0.96.

## Chosen config (best average of train and validation t), then its holdout

| series   |   lag | vol   | scale   | filter   |   margin | band   | side   |   train_bets |   train_c_per_bet |   train_t |   valid_bets |   valid_c_per_bet |   valid_t |   hold_bets |   hold_c_per_bet |   hold_dollars |   hold_t |   hold_excl28_dollars |
|:---------|------:|:------|:--------|:---------|---------:|:-------|:-------|-------------:|------------------:|----------:|-------------:|------------------:|----------:|------------:|-----------------:|---------------:|---------:|----------------------:|
| KXETH    |    15 | ppc   | fixed   | shrink50 |        2 | all    | both   |           94 |              8.35 |      2.15 |           28 |                 7 |      0.63 |          13 |             7.21 |          93.67 |     0.64 |                112.71 |

## Top 25 by training t, with what happened next

| series   |   lag | vol   | scale   | filter   |   margin | band   | side   |   train_bets |   train_c_per_bet |   train_t |   valid_bets |   valid_c_per_bet |   valid_t |   hold_bets |   hold_c_per_bet |   hold_dollars |   hold_t |   hold_excl28_dollars |
|:---------|------:|:------|:--------|:---------|---------:|:-------|:-------|-------------:|------------------:|----------:|-------------:|------------------:|----------:|------------:|-----------------:|---------------:|---------:|----------------------:|
| KXBTC    |    15 | last  | fixed   | none     |       10 | all    | both   |           56 |             11.92 |      2.57 |           16 |             -8.81 |     -0.74 |           7 |            -8.59 |         -60.1  |    -0.96 |                -43.15 |
| KXBTC    |    15 | last  | fixed   | none     |       10 | middle | both   |           54 |             12.28 |      2.54 |           14 |             -8.02 |     -0.62 |           4 |            -5.21 |         -20.82 |    -0.3  |                 -3.87 |
| KXBTC    |    15 | last  | fixed   | volview  |       10 | middle | both   |           41 |             14.44 |      2.28 |           13 |             -4.81 |     -0.43 |           4 |            -5.21 |         -20.82 |    -0.3  |                 -3.87 |
| KXETH    |    15 | ppc   | fixed   | shrink50 |        2 | middle | both   |           81 |             10.05 |      2.24 |           24 |              5.02 |      0.47 |           5 |            16.8  |          84.01 |     0.7  |                103.05 |
| KXBTC    |    15 | last  | fixed   | volview  |       10 | all    | both   |           42 |             13.89 |      2.24 |           15 |             -6.08 |     -0.6  |           7 |            -8.59 |         -60.1  |    -0.96 |                -43.15 |
| KXBTC    |     1 | last  | fixed   | none     |        5 | all    | no     |           46 |              7.77 |      2.19 |            6 |            -32.65 |     -1.04 |          90 |            37.96 |        3416.4  |     1.01 |                 32.15 |
| KXBTC    |     1 | last  | rolling | none     |        5 | all    | no     |           39 |              7.25 |      2.18 |            6 |            -32.65 |     -1.04 |          87 |            40.29 |        3504.81 |     1.04 |                120.56 |
| KXETH    |    15 | ppc   | fixed   | shrink50 |        2 | all    | both   |           94 |              8.35 |      2.15 |           28 |              7    |      0.63 |          13 |             7.21 |          93.67 |     0.64 |                112.71 |
| KXETH    |     5 | last  | rolling | volview  |       10 | middle | no     |           25 |              8.98 |      2.09 |            0 |            nan    |    nan    |           0 |           nan    |           0    |   nan    |                  0    |
| KXETH    |     5 | last  | fixed   | volview  |       10 | middle | no     |           25 |              8.98 |      2.09 |            0 |            nan    |    nan    |           0 |           nan    |           0    |   nan    |                  0    |
| KXETH    |     5 | last  | fixed   | volview  |       10 | all    | no     |           25 |              8.98 |      2.09 |            0 |            nan    |    nan    |           0 |           nan    |           0    |   nan    |                  0    |
| KXBTC    |    15 | last  | rolling | shrink50 |        5 | all    | both   |           38 |             12.66 |      2.04 |            7 |            -19.24 |    nan    |           7 |           -20.88 |        -146.18 |    -3.68 |               -129.23 |
| KXBTC    |    15 | last  | rolling | shrink50 |        5 | middle | both   |           37 |             12.65 |      2.01 |            6 |            -19.97 |    nan    |           4 |           -26.72 |        -106.9  |    -3.71 |                -89.95 |
| KXETH    |    15 | last  | rolling | volview  |       10 | all    | both   |           67 |             11.83 |      2.01 |           31 |            -13.46 |     -3.1  |          21 |             5.74 |         120.54 |     0.78 |                139.58 |
| KXBTC    |     1 | last  | rolling | volview  |        5 | all    | no     |           27 |              9.79 |      1.99 |            4 |            -39.95 |    nan    |          86 |            40.52 |        3484.98 |     1.04 |                100.73 |
| KXETH    |     5 | last  | rolling | volview  |       10 | all    | no     |           26 |              8.11 |      1.98 |            0 |            nan    |    nan    |           0 |           nan    |           0    |   nan    |                  0    |
| KXETH    |    15 | last  | rolling | volview  |       10 | middle | both   |           64 |             12.03 |      1.97 |           31 |            -13.46 |     -3.1  |          17 |             4.21 |          71.51 |     0.45 |                 90.55 |
| KXETH    |     1 | ppc   | rolling | shrink50 |        2 | all    | both   |           57 |             10.13 |      1.92 |            8 |            -17.46 |     -0.83 |          13 |           -12.82 |        -166.66 |    -0.95 |               -166.66 |
| KXETH    |    15 | last  | rolling | none     |       10 | all    | both   |           79 |              9.56 |      1.89 |           36 |             -7.19 |     -2.33 |          22 |             7    |         153.94 |     0.99 |                172.98 |
| KXETH    |    15 | last  | fixed   | volview  |       10 | all    | both   |           68 |             10.96 |      1.89 |           27 |            -11.9  |     -2.39 |           7 |            -0.62 |          -4.32 |    -0.04 |                 -4.32 |
| KXETH    |    15 | last  | rolling | none     |       10 | middle | both   |           76 |              9.64 |      1.85 |           36 |             -7.19 |     -2.33 |          18 |             5.83 |         104.91 |     0.65 |                123.95 |
| KXETH    |    15 | last  | fixed   | volview  |       10 | middle | both   |           65 |             11.11 |      1.85 |           27 |            -11.9  |     -2.39 |           7 |            -0.62 |          -4.32 |    -0.04 |                 -4.32 |
| KXETH    |    15 | last  | rolling | shrink50 |        5 | middle | yes    |           28 |             14.58 |      1.83 |           13 |            -11.62 |     -0.87 |           3 |            44.52 |         133.55 |   nan    |                133.55 |
| KXETH    |    15 | last  | rolling | shrink50 |        5 | all    | yes    |           28 |             14.58 |      1.83 |           13 |            -11.62 |     -0.87 |           3 |            44.52 |         133.55 |   nan    |                133.55 |
| KXETH    |    15 | ppc   | rolling | volview  |       10 | middle | both   |           25 |             12.07 |      1.81 |            7 |              5.4  |      0.27 |           3 |             9.1  |          27.3  |     0.3  |                 46.34 |

## Where is the model more accurate than the market? (calibration by the market's price)

market_says / model_says = average probability given; actually_won = how often it won; lower error is better.

### KXBTC, 1 min after open

| band         |   brackets |   market_says |   model_says |   actually_won |   market_error |   model_error | closer   |
|:-------------|-----------:|--------------:|-------------:|---------------:|---------------:|--------------:|:---------|
| [0.0, 0.02)  |     170123 |        0.0054 |       0.0001 |         0.0001 |         0.0054 |        0      | model    |
| [0.02, 0.05) |      12180 |        0.0329 |       0.0098 |         0.009  |         0.0238 |        0.0007 | model    |
| [0.05, 0.15) |      34873 |        0.1036 |       0.0148 |         0.0141 |         0.0894 |        0.0006 | model    |
| [0.15, 0.35) |      11284 |        0.2327 |       0.0483 |         0.0502 |         0.1825 |        0.0019 | model    |
| [0.35, 0.65) |      32124 |        0.4744 |       0.0061 |         0.0064 |         0.468  |        0.0002 | model    |
| [0.65, 0.85) |         37 |        0.7181 |       0.7139 |         0.8919 |         0.1738 |        0.178  | market   |
| [0.95, 0.98) |          1 |        0.965  |       0.9987 |         1      |         0.035  |        0.0013 | model    |

### KXBTC, 15 min after open

| band         |   brackets |   market_says |   model_says |   actually_won |   market_error |   model_error | closer   |
|:-------------|-----------:|--------------:|-------------:|---------------:|---------------:|--------------:|:---------|
| [0.0, 0.02)  |     229984 |        0.0052 |       0.0002 |         0.0002 |         0.0051 |        0      | model    |
| [0.02, 0.05) |      20508 |        0.0397 |       0.0061 |         0.0056 |         0.0341 |        0.0005 | model    |
| [0.05, 0.15) |       6163 |        0.0895 |       0.0756 |         0.0743 |         0.0152 |        0.0012 | model    |
| [0.15, 0.35) |       3024 |        0.2168 |       0.1835 |         0.1839 |         0.0329 |        0.0004 | model    |
| [0.35, 0.65) |       1995 |        0.4642 |       0.0993 |         0.1083 |         0.3559 |        0.009  | model    |
| [0.65, 0.85) |         48 |        0.7164 |       0.7161 |         0.8125 |         0.0961 |        0.0964 | market   |
| [0.85, 0.95) |          3 |        0.8833 |       0.9351 |         1      |         0.1167 |        0.0649 | model    |

### KXETH, 1 min after open

| band         |   brackets |   market_says |   model_says |   actually_won |   market_error |   model_error | closer   |
|:-------------|-----------:|--------------:|-------------:|---------------:|---------------:|--------------:|:---------|
| [0.0, 0.02)  |     336674 |        0.0054 |       0.0001 |         0.0001 |         0.0053 |        0      | model    |
| [0.02, 0.05) |      14355 |        0.0327 |       0.0057 |         0.0055 |         0.0272 |        0.0002 | model    |
| [0.05, 0.15) |       6061 |        0.0967 |       0.0651 |         0.0693 |         0.0274 |        0.0042 | model    |
| [0.15, 0.35) |      37971 |        0.1863 |       0.0159 |         0.0152 |         0.1711 |        0.0007 | model    |
| [0.35, 0.65) |       9233 |        0.4823 |       0.0249 |         0.0252 |         0.4571 |        0.0004 | model    |
| [0.65, 0.85) |         63 |        0.724  |       0.738  |         0.8571 |         0.1332 |        0.1191 | model    |
| [0.85, 0.95) |         16 |        0.9019 |       0.91   |         0.9375 |         0.0356 |        0.0275 | model    |
| [0.95, 0.98) |         11 |        0.9655 |       0.9815 |         1      |         0.0345 |        0.0185 | model    |

### KXETH, 15 min after open

| band         |   brackets |   market_says |   model_says |   actually_won |   market_error |   model_error | closer   |
|:-------------|-----------:|--------------:|-------------:|---------------:|---------------:|--------------:|:---------|
| [0.0, 0.02)  |     346009 |        0.0053 |       0.0001 |         0.0001 |         0.0052 |        0      | model    |
| [0.02, 0.05) |      17576 |        0.0358 |       0.0048 |         0.0042 |         0.0316 |        0.0006 | model    |
| [0.05, 0.15) |       5003 |        0.0954 |       0.0672 |         0.0702 |         0.0252 |        0.0029 | model    |
| [0.15, 0.35) |      35106 |        0.1836 |       0.0182 |         0.0176 |         0.1661 |        0.0006 | model    |
| [0.35, 0.65) |       2242 |        0.4699 |       0.1091 |         0.1151 |         0.3548 |        0.006  | model    |
| [0.65, 0.85) |         71 |        0.7379 |       0.7404 |         0.7606 |         0.0227 |        0.0202 | model    |
| [0.85, 0.95) |         26 |        0.9087 |       0.9029 |         0.9231 |         0.0144 |        0.0201 | market   |
| [0.95, 0.98) |         16 |        0.9653 |       0.9745 |         1      |         0.0347 |        0.0255 | model    |

## Trade records for older months (15th of each month, 12pm ET event)

```
KXBTC KXBTC-26JAN1511 markets 75 trades: {'markets/trades': 0, 'historical/trades': 899}
KXBTC KXBTC-26FEB1511 markets 75 trades: {'markets/trades': 0, 'historical/trades': 748}
KXBTC KXBTC-26MAR1512 markets 75 trades: {'markets/trades': 0, 'historical/trades': 643}
KXBTC KXBTC-26APR1512 markets 188 trades: {'markets/trades': 0, 'historical/trades': 433}
KXBTC KXBTC-26MAY1512 markets 188 trades: {'markets/trades': 0, 'historical/trades': 677}
KXBTC KXBTC-26JUN1512 markets 188 trades: {'markets/trades': 0, 'historical/trades': 654}
KXBTC KXBTC-26JUL1512 markets 188 trades: {'markets/trades': 0, 'historical/trades': 614}
KXETH KXETH-26JAN1511 markets 75 trades: {'markets/trades': 0, 'historical/trades': 83}
KXETH KXETH-26FEB1511 markets 75 trades: {'markets/trades': 0, 'historical/trades': 149}
KXETH KXETH-26MAR1512 markets 75 trades: {'markets/trades': 0, 'historical/trades': 81}
KXETH KXETH-26APR1512 markets 75 trades: {'markets/trades': 0, 'historical/trades': 223}
KXETH KXETH-26MAY1512 markets 75 trades: {'markets/trades': 0, 'historical/trades': 56}
KXETH KXETH-26JUN1512 markets 75 trades: {'markets/trades': 0, 'historical/trades': 99}
KXETH KXETH-26JUL1512 markets 75 trades: {'markets/trades': 0, 'historical/trades': 154}
```
