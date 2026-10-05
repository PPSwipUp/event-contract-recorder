# Paper liquidity provider: 60-day historical replay of fill costs (20 markets)

Rewards = today's share against the live book, assumed constant (unverified assumption).

## Totals per day (all 20 markets)

|                        |   fills |   fill_pnl_day |   reward_day |   net_day |
|:-----------------------|--------:|---------------:|-------------:|----------:|
| ('touch', 'back')      |     640 |       -1076.33 |       316.5  |   -759.84 |
| ('touch', 'back+calm') |     413 |        -523.27 |       218.54 |   -304.72 |
| ('touch', 'front')     |   10993 |        -344.24 |       316.5  |    -27.73 |
| ('wide', 'back')       |     191 |        -269.32 |        58.39 |   -210.92 |
| ('wide', 'back+calm')  |     101 |        -134.01 |        39.11 |    -94.91 |
| ('wide', 'front')      |     592 |        -298.1  |        58.39 |   -239.69 |

- wide/front: daily net mean $-19.84, sd $77.93, worst day $-436.61, max drawdown $1376.47, positive days 59%, t -1.99
- wide/back: daily net mean $-20.95, sd $78.85, worst day $-388.61, max drawdown $1373.42, positive days 56%, t -2.08
- wide/back+calm: daily net mean $-10.08, sd $46.82, worst day $-316.91, max drawdown $718.69, positive days 54%, t -1.68
- touch/front: daily net mean $305.81, sd $265.61, worst day $-295.99, max drawdown $295.99, positive days 98%, t 8.99
- touch/back: daily net mean $-87.67, sd $252.05, worst day $-1245.99, max drawdown $5492.04, positive days 48%, t -2.72
- touch/back+calm: daily net mean $-48.82, sd $140.81, worst day $-943.95, max drawdown $3052.94, positive days 49%, t -2.71

## Per market (touch / back queue = most realistic tight quoting)

| market                                   | kind   | queue   |   trades |   fills |   quoted_% |   fill_pnl_day_$ |   reward_day_$ |   net_day_$ |   worst_day_$ |
|:-----------------------------------------|:-------|:--------|---------:|--------:|-----------:|-----------------:|---------------:|------------:|--------------:|
| Any of the Cornell 7 charged with a felo | touch  | back    |      592 |      30 |        100 |          -263.75 |          27.79 |     -235.96 |        -875   |
| Will Texas enact a data center moratoriu | touch  | back    |      210 |      14 |        100 |          -158    |          12.54 |     -145.46 |        -422.5 |
| Will Indiana enact a data center morator | touch  | back    |      193 |      12 |        100 |           -91    |          11.78 |      -79.22 |        -232.5 |
| Will Louisiana enact a data center morat | touch  | back    |      112 |      16 |        100 |           -64    |           8.8  |      -55.2  |        -197.5 |
| Israel accuses Iran/proxies of plane sta | touch  | back    |     1038 |      80 |        100 |           -78.75 |          32.14 |      -46.61 |        -235   |
| Will Missouri enact a data center morato | touch  | back    |      111 |       5 |        100 |           -67.5  |          25.92 |      -41.58 |        -145   |
| Will Texas enact a data center moratoriu | touch  | back    |       45 |       6 |        100 |           -70    |          29.93 |      -40.07 |        -107.5 |
| Will Oklahoma enact a data center morato | touch  | back    |       87 |       6 |        100 |           -43    |           9.19 |      -33.81 |        -127.5 |
| Will Louisiana enact a data center morat | touch  | back    |      136 |       4 |        100 |           -30    |           7.41 |      -22.59 |        -130   |
| Will Ohio enact a data center moratorium | touch  | back    |       87 |       8 |        100 |           -33    |          13    |      -20    |        -130   |
| Will Anthropic announce bankruptcy by De | touch  | back    |      103 |       6 |        100 |           -22.94 |           3.27 |      -19.67 |        -340   |
| Will Indiana enact a data center morator | touch  | back    |      116 |      14 |        100 |           -93.33 |          78.47 |      -14.87 |        -192.5 |
| Will the Fed increase interest rates by  | touch  | back    |     7476 |     142 |        100 |           -16.07 |           3.38 |      -12.68 |        -230   |
| Will there be no change in Fed interest  | touch  | back    |     9647 |     129 |        100 |           -13.4  |           2.09 |      -11.32 |        -212.5 |
| Will Oklahoma enact a data center morato | touch  | back    |      337 |      16 |        100 |           -20    |          13.45 |       -6.55 |        -127.5 |
| Will the Republican Party control the Se | touch  | back    |     2207 |      15 |        100 |            -3.16 |           0.64 |       -2.52 |         -57.5 |
| 2026 Balance of Power: D Senate, D House | touch  | back    |     5754 |      52 |        100 |            -3.03 |           0.97 |       -2.06 |         -37.5 |
| Will the Democratic Party control the Se | touch  | back    |     3415 |      31 |        100 |            -2.09 |           0.76 |       -1.33 |         -50   |
| 2026 Balance of Power: R Senate, D House | touch  | back    |     2288 |      44 |        100 |            -1.64 |           0.77 |       -0.87 |         -20   |
| Will Oklahoma enact a data center morato | touch  | back    |       65 |      10 |        100 |            -1.67 |          34.2  |       32.53 |         -60   |

## Per market (touch / back queue / calm filter)

| market                                   | kind   | queue     |   trades |   fills |   quoted_% |   fill_pnl_day_$ |   reward_day_$ |   net_day_$ |   worst_day_$ |
|:-----------------------------------------|:-------|:----------|---------:|--------:|-----------:|-----------------:|---------------:|------------:|--------------:|
| Will Texas enact a data center moratoriu | touch  | back+calm |       45 |       2 |         74 |           -68.33 |          22    |      -46.33 |        -105   |
| Will Missouri enact a data center morato | touch  | back+calm |      111 |       5 |         86 |           -67.5  |          22.25 |      -45.25 |        -145   |
| Will Louisiana enact a data center morat | touch  | back+calm |      136 |       2 |         89 |           -45    |           6.58 |      -38.42 |        -127.5 |
| Will Indiana enact a data center morator | touch  | back+calm |      116 |       9 |         76 |           -89.17 |          59.7  |      -29.46 |        -180   |
| Any of the Cornell 7 charged with a felo | touch  | back+calm |      592 |      14 |         35 |           -36.25 |           9.68 |      -26.57 |         -75   |
| Will Texas enact a data center moratoriu | touch  | back+calm |      210 |       2 |         56 |           -31    |           6.99 |      -24.01 |        -110   |
| Will Indiana enact a data center morator | touch  | back+calm |      193 |       6 |         61 |           -31    |           7.17 |      -23.83 |        -157.5 |
| Will Ohio enact a data center moratorium | touch  | back+calm |       87 |       6 |         76 |           -33    |           9.9  |      -23.1  |        -127.5 |
| Will Oklahoma enact a data center morato | touch  | back+calm |       87 |       2 |         73 |           -26    |           6.74 |      -19.26 |         -60   |
| Will Oklahoma enact a data center morato | touch  | back+calm |      337 |       8 |         72 |           -25    |           9.72 |      -15.28 |         -87.5 |
| Will Louisiana enact a data center morat | touch  | back+calm |      112 |       8 |         93 |           -23    |           8.18 |      -14.82 |         -62.5 |
| Will there be no change in Fed interest  | touch  | back+calm |     9647 |      98 |         93 |           -13.11 |           1.95 |      -11.17 |        -187.5 |
| Will the Fed increase interest rates by  | touch  | back+calm |     7476 |      97 |         93 |           -12.34 |           3.14 |       -9.19 |        -207.5 |
| Will Anthropic announce bankruptcy by De | touch  | back+calm |      103 |       6 |         93 |           -10    |           3.04 |       -6.96 |        -170   |
| Will the Republican Party control the Se | touch  | back+calm |     2207 |      15 |        100 |            -3.16 |           0.64 |       -2.52 |         -57.5 |
| Will the Democratic Party control the Se | touch  | back+calm |     3415 |      27 |        100 |            -3.07 |           0.76 |       -2.31 |         -50   |
| 2026 Balance of Power: D Senate, D House | touch  | back+calm |     5754 |      52 |        100 |            -3.03 |           0.97 |       -2.06 |         -37.5 |
| 2026 Balance of Power: R Senate, D House | touch  | back+calm |     2288 |      44 |        100 |            -1.64 |           0.76 |       -0.88 |         -20   |
| Israel accuses Iran/proxies of plane sta | touch  | back+calm |     1038 |       0 |         28 |             0    |           9.02 |        9.02 |           0   |
| Will Oklahoma enact a data center morato | touch  | back+calm |       65 |      10 |         86 |            -1.67 |          29.35 |       27.68 |         -60   |

## Per market (wide / back queue)

| market                                   | kind   | queue   |   trades |   fills |   quoted_% |   fill_pnl_day_$ |   reward_day_$ |   net_day_$ |   worst_day_$ |
|:-----------------------------------------|:-------|:--------|---------:|--------:|-----------:|-----------------:|---------------:|------------:|--------------:|
| Any of the Cornell 7 charged with a felo | wide   | back    |      592 |      14 |        100 |           -57    |           6.39 |      -50.61 |          -230 |
| Will Texas enact a data center moratoriu | wide   | back    |      210 |      10 |        100 |           -46    |           2.28 |      -43.72 |          -126 |
| Israel accuses Iran/proxies of plane sta | wide   | back    |     1038 |      39 |        100 |           -34.75 |           7.42 |      -27.33 |          -112 |
| Will Indiana enact a data center morator | wide   | back    |      193 |       4 |        100 |           -28    |           2.14 |      -25.86 |           -64 |
| Will Missouri enact a data center morato | wide   | back    |      111 |       2 |        100 |           -26    |           4.81 |      -21.19 |           -60 |
| Will Indiana enact a data center morator | wide   | back    |      116 |       2 |        100 |           -32    |          13.05 |      -18.95 |           -68 |
| Will Louisiana enact a data center morat | wide   | back    |      112 |       4 |        100 |           -16.8  |           1.59 |      -15.21 |           -32 |
| Will Louisiana enact a data center morat | wide   | back    |      136 |       4 |        100 |            -9.2  |           1.33 |       -7.87 |           -24 |
| Will Anthropic announce bankruptcy by De | wide   | back    |      103 |       5 |        100 |            -7.47 |           0.74 |       -6.73 |          -112 |
| Will Texas enact a data center moratoriu | wide   | back    |       45 |       5 |        100 |            -8.67 |           4.54 |       -4.12 |           -14 |
| Will there be no change in Fed interest  | wide   | back    |     9647 |      26 |        100 |            -3.84 |           0.21 |       -3.63 |           -61 |
| Will the Fed increase interest rates by  | wide   | back    |     7476 |      38 |        100 |            -3.61 |           0.34 |       -3.27 |           -92 |
| Will Oklahoma enact a data center morato | wide   | back    |      337 |      10 |        100 |            -5.2  |           2.45 |       -2.75 |           -49 |
| Will the Democratic Party control the Se | wide   | back    |     3415 |       4 |        100 |             0.03 |           0.14 |        0.17 |            -2 |
| Will the Republican Party control the Se | wide   | back    |     2207 |       2 |        100 |             0.07 |           0.11 |        0.18 |            -1 |
| 2026 Balance of Power: R Senate, D House | wide   | back    |     2288 |       8 |        100 |             0.07 |           0.17 |        0.24 |            -8 |
| 2026 Balance of Power: D Senate, D House | wide   | back    |     5754 |       2 |        100 |             1.05 |           0.22 |        1.27 |           -12 |
| Will Oklahoma enact a data center morato | wide   | back    |       87 |       1 |        100 |            -0.2  |           1.66 |        1.46 |           -29 |
| Will Ohio enact a data center moratorium | wide   | back    |       87 |       4 |        100 |             1.2  |           2.36 |        3.56 |             0 |
| Will Oklahoma enact a data center morato | wide   | back    |       65 |       7 |        100 |             7    |           6.44 |       13.44 |            -6 |
