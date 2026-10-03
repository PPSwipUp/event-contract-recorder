# Paper liquidity provider: 60-day historical replay of fill costs (20 markets)

Rewards = today's share against the live book, assumed constant (unverified assumption).

## Totals per day (all 20 markets)

|                    |   fills |   fill_pnl_day |   reward_day |   net_day |
|:-------------------|--------:|---------------:|-------------:|----------:|
| ('touch', 'back')  |     640 |       -1076.33 |       316.5  |   -759.84 |
| ('touch', 'front') |   10993 |        -344.24 |       316.5  |    -27.73 |
| ('wide', 'back')   |     191 |        -269.32 |        58.39 |   -210.92 |
| ('wide', 'front')  |     592 |        -298.1  |        58.39 |   -239.69 |

- wide/front: daily net mean $-19.84, sd $77.93, worst day $-436.61, max drawdown $1376.47, positive days 59%, t -1.99
- wide/back: daily net mean $-20.95, sd $78.85, worst day $-388.61, max drawdown $1373.42, positive days 56%, t -2.08
- touch/front: daily net mean $305.81, sd $265.61, worst day $-295.99, max drawdown $295.99, positive days 98%, t 8.99
- touch/back: daily net mean $-87.67, sd $252.05, worst day $-1245.99, max drawdown $5492.04, positive days 48%, t -2.72

## Per market (touch / back queue = most realistic tight quoting)

| market                                   | kind   | queue   |   trades |   fills |   fill_pnl_day_$ |   reward_day_$ |   net_day_$ |   worst_day_$ |
|:-----------------------------------------|:-------|:--------|---------:|--------:|-----------------:|---------------:|------------:|--------------:|
| Any of the Cornell 7 charged with a felo | touch  | back    |      592 |      30 |          -263.75 |          27.79 |     -235.96 |        -875   |
| Will Texas enact a data center moratoriu | touch  | back    |      210 |      14 |          -158    |          12.54 |     -145.46 |        -422.5 |
| Will Indiana enact a data center morator | touch  | back    |      193 |      12 |           -91    |          11.78 |      -79.22 |        -232.5 |
| Will Louisiana enact a data center morat | touch  | back    |      112 |      16 |           -64    |           8.8  |      -55.2  |        -197.5 |
| Israel accuses Iran/proxies of plane sta | touch  | back    |     1038 |      80 |           -78.75 |          32.14 |      -46.61 |        -235   |
| Will Missouri enact a data center morato | touch  | back    |      111 |       5 |           -67.5  |          25.92 |      -41.58 |        -145   |
| Will Texas enact a data center moratoriu | touch  | back    |       45 |       6 |           -70    |          29.93 |      -40.07 |        -107.5 |
| Will Oklahoma enact a data center morato | touch  | back    |       87 |       6 |           -43    |           9.19 |      -33.81 |        -127.5 |
| Will Louisiana enact a data center morat | touch  | back    |      136 |       4 |           -30    |           7.41 |      -22.59 |        -130   |
| Will Ohio enact a data center moratorium | touch  | back    |       87 |       8 |           -33    |          13    |      -20    |        -130   |
| Will Anthropic announce bankruptcy by De | touch  | back    |      103 |       6 |           -22.94 |           3.27 |      -19.67 |        -340   |
| Will Indiana enact a data center morator | touch  | back    |      116 |      14 |           -93.33 |          78.47 |      -14.87 |        -192.5 |
| Will the Fed increase interest rates by  | touch  | back    |     7476 |     142 |           -16.07 |           3.38 |      -12.68 |        -230   |
| Will there be no change in Fed interest  | touch  | back    |     9647 |     129 |           -13.4  |           2.09 |      -11.32 |        -212.5 |
| Will Oklahoma enact a data center morato | touch  | back    |      337 |      16 |           -20    |          13.45 |       -6.55 |        -127.5 |
| Will the Republican Party control the Se | touch  | back    |     2207 |      15 |            -3.16 |           0.64 |       -2.52 |         -57.5 |
| 2026 Balance of Power: D Senate, D House | touch  | back    |     5754 |      52 |            -3.03 |           0.97 |       -2.06 |         -37.5 |
| Will the Democratic Party control the Se | touch  | back    |     3415 |      31 |            -2.09 |           0.76 |       -1.33 |         -50   |
| 2026 Balance of Power: R Senate, D House | touch  | back    |     2288 |      44 |            -1.64 |           0.77 |       -0.87 |         -20   |
| Will Oklahoma enact a data center morato | touch  | back    |       65 |      10 |            -1.67 |          34.2  |       32.53 |         -60   |

## Per market (wide / back queue)

| market                                   | kind   | queue   |   trades |   fills |   fill_pnl_day_$ |   reward_day_$ |   net_day_$ |   worst_day_$ |
|:-----------------------------------------|:-------|:--------|---------:|--------:|-----------------:|---------------:|------------:|--------------:|
| Any of the Cornell 7 charged with a felo | wide   | back    |      592 |      14 |           -57    |           6.39 |      -50.61 |          -230 |
| Will Texas enact a data center moratoriu | wide   | back    |      210 |      10 |           -46    |           2.28 |      -43.72 |          -126 |
| Israel accuses Iran/proxies of plane sta | wide   | back    |     1038 |      39 |           -34.75 |           7.42 |      -27.33 |          -112 |
| Will Indiana enact a data center morator | wide   | back    |      193 |       4 |           -28    |           2.14 |      -25.86 |           -64 |
| Will Missouri enact a data center morato | wide   | back    |      111 |       2 |           -26    |           4.81 |      -21.19 |           -60 |
| Will Indiana enact a data center morator | wide   | back    |      116 |       2 |           -32    |          13.05 |      -18.95 |           -68 |
| Will Louisiana enact a data center morat | wide   | back    |      112 |       4 |           -16.8  |           1.59 |      -15.21 |           -32 |
| Will Louisiana enact a data center morat | wide   | back    |      136 |       4 |            -9.2  |           1.33 |       -7.87 |           -24 |
| Will Anthropic announce bankruptcy by De | wide   | back    |      103 |       5 |            -7.47 |           0.74 |       -6.73 |          -112 |
| Will Texas enact a data center moratoriu | wide   | back    |       45 |       5 |            -8.67 |           4.54 |       -4.12 |           -14 |
| Will there be no change in Fed interest  | wide   | back    |     9647 |      26 |            -3.84 |           0.21 |       -3.63 |           -61 |
| Will the Fed increase interest rates by  | wide   | back    |     7476 |      38 |            -3.61 |           0.34 |       -3.27 |           -92 |
| Will Oklahoma enact a data center morato | wide   | back    |      337 |      10 |            -5.2  |           2.45 |       -2.75 |           -49 |
| Will the Democratic Party control the Se | wide   | back    |     3415 |       4 |             0.03 |           0.14 |        0.17 |            -2 |
| Will the Republican Party control the Se | wide   | back    |     2207 |       2 |             0.07 |           0.11 |        0.18 |            -1 |
| 2026 Balance of Power: R Senate, D House | wide   | back    |     2288 |       8 |             0.07 |           0.17 |        0.24 |            -8 |
| 2026 Balance of Power: D Senate, D House | wide   | back    |     5754 |       2 |             1.05 |           0.22 |        1.27 |           -12 |
| Will Oklahoma enact a data center morato | wide   | back    |       87 |       1 |            -0.2  |           1.66 |        1.46 |           -29 |
| Will Ohio enact a data center moratorium | wide   | back    |       87 |       4 |             1.2  |           2.36 |        3.56 |             0 |
| Will Oklahoma enact a data center morato | wide   | back    |       65 |       7 |             7    |           6.44 |       13.44 |            -6 |
