# Favourite-longshot bias across Kalshi (PLAN_FAVLONG.md)

Sampled events: 41198 from 1376 series; markets with volume >= 1000: 141407

## Net P&L per contract (cents), SE clustered by series

| rule   | trade                  | half    |     n |   series |   mean_pnl_c |   t_clustered |
|:-------|:-----------------------|:--------|------:|---------:|-------------:|--------------:|
| 6h     | favourite 90-97c       | train   | 13409 |      789 |       -9.671 |        -11.46 |
| 6h     | favourite 90-97c       | holdout |  9251 |      711 |       -8.195 |        -12.04 |
| 6h     | mirror: longshot 3-10c | train   | 13011 |      691 |        1.031 |          2.81 |
| 6h     | mirror: longshot 3-10c | holdout |  9861 |      654 |        0.031 |          0.09 |
| 1h     | favourite 90-97c       | train   | 14125 |      868 |      -10.008 |         -9.26 |
| 1h     | favourite 90-97c       | holdout | 10412 |      793 |       -7.519 |         -9.2  |
| 1h     | mirror: longshot 3-10c | train   | 12994 |      764 |       -1.493 |         -6.01 |
| 1h     | mirror: longshot 3-10c | holdout | 10024 |      720 |       -1.718 |         -6.53 |

## Calibration, primary rule (price bucket in cents)

|                 |    n |   win_rate |   mean_pnl_c |
|:----------------|-----:|-----------:|-------------:|
| ('holdout', 90) |  889 |      0.82  |       -8.628 |
| ('holdout', 91) |  976 |      0.844 |       -7.154 |
| ('holdout', 92) | 1024 |      0.858 |       -6.68  |
| ('holdout', 93) | 1088 |      0.856 |       -7.89  |
| ('holdout', 94) | 1188 |      0.854 |       -9.046 |
| ('holdout', 95) | 1323 |      0.868 |       -8.492 |
| ('holdout', 96) | 1208 |      0.872 |       -9.101 |
| ('holdout', 97) | 1555 |      0.89  |       -8.206 |
| ('train', 90)   | 1243 |      0.821 |       -8.571 |
| ('train', 91)   | 1482 |      0.827 |       -8.854 |
| ('train', 92)   | 1775 |      0.847 |       -7.788 |
| ('train', 93)   | 1434 |      0.84  |       -9.429 |
| ('train', 94)   | 1711 |      0.853 |       -9.07  |
| ('train', 95)   | 1982 |      0.869 |       -8.458 |
| ('train', 96)   | 1668 |      0.879 |       -8.38  |
| ('train', 97)   | 2114 |      0.819 |      -15.28  |

## Holdout by series prefix (top 15 by trades)

| cat   |   n |   mean_pnl_c |
|:------|----:|-------------:|
| NCAAF | 670 |       -9.852 |
| AAAGA | 593 |      -14.253 |
| NFLRE | 555 |       -6.516 |
| UEFAN | 450 |       -4.1   |
| NFLTD | 338 |       -1.059 |
| NFLFI | 250 |       -1.226 |
| NFLTE | 250 |       -9.613 |
| AFCON | 228 |       -7.909 |
| LALIG | 207 |       -0.311 |
| LIGAM | 199 |       -6.035 |
| CONCA | 190 |      -11.364 |
| INTLF | 183 |      -11.099 |
| NFL1H | 182 |       -0.306 |
| NFLRS | 174 |       -4.72  |
| BRASI | 154 |       -3.551 |

GATE (6h favourite, holdout): mean -8.195c/contract, clustered t -12.04, n 9251 over 711 series -> FAIL
