# Fixing the range bot: pre-declared variants, chosen on August, tested on September

t_days = t-statistic with each DAY as one observation (|t| > 2 is the bar).

## KXBTC

| variant       |   min_after_open |   aug_bets |   aug_cents_per_bet |   aug_t_days |   sep_bets |   sep_cents_per_bet |   sep_dollars_100 |   sep_t_days |   sep_excl_28th_$ |
|:--------------|-----------------:|-----------:|--------------------:|-------------:|-----------:|--------------------:|------------------:|-------------:|------------------:|
| base          |                1 |         52 |               -3.79 |        -0.55 |        109 |               31.95 |           3482.06 |         1.03 |            113.71 |
| base          |                5 |        100 |               -9.6  |        -1.47 |         41 |                2.13 |             87.31 |         0.3  |            103.21 |
| base          |               15 |        157 |               -3.69 |        -1.01 |         78 |                0.36 |             28.26 |         0.06 |             73.95 |
| rollk         |                1 |         52 |               -5.76 |        -0.97 |        106 |               32.07 |           3399.53 |         1.01 |             40.76 |
| rollk         |                5 |        108 |               -7.88 |        -1.12 |         52 |               -0.32 |            -16.57 |        -0.05 |             21.65 |
| rollk         |               15 |        155 |               -2.51 |        -0.73 |         89 |                0.43 |             38.51 |         0.09 |            100.1  |
| shrink        |                1 |          4 |                8.62 |         0.47 |         77 |               43.95 |           3384.25 |       nan    |              0    |
| shrink        |                5 |          7 |                5.1  |         0.31 |          2 |              -42.38 |            -84.77 |       nan    |            -84.77 |
| shrink        |               15 |         13 |               11.81 |         0.98 |          5 |               -0.02 |             -0.1  |        -0    |             -0.1  |
| volview       |                1 |         41 |               -5.93 |        -0.71 |        100 |               33.79 |           3379.29 |         1    |             10.94 |
| volview       |                5 |         85 |               -8.81 |        -1.57 |         36 |               -1.86 |            -67.09 |        -0.25 |            -51.19 |
| volview       |               15 |        132 |               -3.49 |        -0.81 |         70 |               -2.22 |           -155.16 |        -0.34 |           -109.47 |
| rollk+volview |                1 |         40 |               -9.29 |        -1.33 |        103 |               33.12 |           3410.98 |         1.01 |             52.21 |
| rollk+volview |                5 |         89 |               -9.89 |        -1.34 |         46 |               -3.23 |           -148.64 |        -0.47 |           -110.42 |
| rollk+volview |               15 |        129 |               -1.66 |        -0.39 |         83 |               -0.94 |            -78.06 |        -0.18 |            -16.47 |

**Chosen on August (highest day-level t): shrink, 15 min after open.** September, untouched: 5 bets, -0.0c/bet, $-0 at 100 contracts, day-level t -0.00; without 28 Sep $-0.

Market-implied vol vs model (median ratio): 1.19; the model's own day-to-day scale drift (rolling k / fixed k, median): 0.99

## KXETH

| variant       |   min_after_open |   aug_bets |   aug_cents_per_bet |   aug_t_days |   sep_bets |   sep_cents_per_bet |   sep_dollars_100 |   sep_t_days |   sep_excl_28th_$ |
|:--------------|-----------------:|-----------:|--------------------:|-------------:|-----------:|--------------------:|------------------:|-------------:|------------------:|
| base          |                1 |        108 |                0.04 |         0.01 |         43 |               -3.42 |           -147.05 |        -0.66 |           -102.23 |
| base          |                5 |        142 |                1.46 |         0.34 |         38 |               -2.6  |            -98.61 |        -0.48 |            -77.49 |
| base          |               15 |        161 |                2.69 |         0.77 |         81 |                2.31 |            187.23 |         0.44 |            125.31 |
| rollk         |                1 |        104 |                2.35 |         0.57 |         66 |               -6.34 |           -418.15 |        -1.13 |           -290.17 |
| rollk         |                5 |        135 |               -0.15 |        -0.03 |         52 |                4.52 |            235.03 |         0.74 |            269.95 |
| rollk         |               15 |        154 |                2.76 |         0.8  |         97 |                4.48 |            434.88 |         0.88 |            380.44 |
| shrink        |                1 |          9 |                1.47 |         0.09 |          0 |              nan    |              0    |       nan    |              0    |
| shrink        |                5 |         11 |               10.58 |         0.75 |          0 |              nan    |              0    |       nan    |              0    |
| shrink        |               15 |          9 |               19.69 |         1.17 |          3 |              -25.57 |            -76.72 |       nan    |            -76.72 |
| volview       |                1 |         83 |               -0.68 |        -0.14 |         38 |               -0.06 |             -2.43 |        -0.01 |             42.39 |
| volview       |                5 |        118 |               -0.2  |        -0.04 |         36 |               -1.49 |            -53.73 |        -0.27 |            -32.61 |
| volview       |               15 |        142 |                5.37 |         1.43 |         73 |                3.21 |            234.34 |         0.59 |            172.42 |
| rollk+volview |                1 |         77 |                0.39 |         0.07 |         61 |               -5.16 |           -314.77 |        -1.01 |           -186.79 |
| rollk+volview |                5 |        113 |               -0.37 |        -0.08 |         51 |                4.13 |            210.38 |         0.66 |            245.3  |
| rollk+volview |               15 |        134 |                5.36 |         1.43 |         91 |                6.05 |            550.87 |         1.27 |            496.43 |

**Chosen on August (highest day-level t): rollk+volview, 15 min after open.** September, untouched: 91 bets, 6.1c/bet, $551 at 100 contracts, day-level t 1.27; without 28 Sep $496.

Market-implied vol vs model (median ratio): 1.50; the model's own day-to-day scale drift (rolling k / fixed k, median): 1.00
