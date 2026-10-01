# Jan-Jul 2026 holdout (ETH hourly ranges, real trade prices 10-20 min after open)

4075 events, 10492 brackets that traded near the money. Rules frozen beforehand; nothing was tuned on this period. day_t = t-statistic with each day as one observation.

| rule                                   |   bets |   c_per_bet |   dollars_100 |   day_t |   days_with_bets | months_positive   |
|:---------------------------------------|-------:|------------:|--------------:|--------:|-----------------:|:------------------|
| forward  (rolling, volview, 5c)        |   1109 |        3.58 |       3967.08 |    2.78 |              205 | 6/7               |
| sweep    (fixed, shrink50, 2c)         |   3125 |        9.59 |      29957.8  |   10.48 |              211 | 7/7               |
| base     (fixed, none, 5c)             |   1969 |        6.86 |      13502.9  |    6.92 |              212 | 6/8               |
| walk-forward (re-picks settings daily) |   2520 |        9.49 |      23905.9  |    9.39 |              181 | 7/7               |

Settings the walk-forward bot picked most often (scale, filter, margin): ('fixed', 'shrink50', np.int64(2)) x104, ('rolling', 'shrink50', np.int64(2)) x42, ('fixed', 'shrink50', np.int64(5)) x23, ('fixed', 'none', np.int64(2)) x6, ('rolling', 'shrink50', np.int64(5)) x4

## Month by month

| m       |   forward |   sweep |   base |   walk-forward |
|:--------|----------:|--------:|-------:|---------------:|
| 2026-01 |       335 |    3697 |   1909 |            169 |
| 2026-02 |      -428 |    2512 |    -63 |           2051 |
| 2026-03 |      1253 |    9423 |   3610 |           8696 |
| 2026-04 |       805 |    4426 |   3101 |           4426 |
| 2026-05 |       827 |    3239 |   1225 |           2946 |
| 2026-06 |       768 |    2792 |   1530 |           1928 |
| 2026-07 |       407 |    3868 |   2235 |           3690 |
| 2026-08 |       nan |     nan |    -43 |            nan |

(dollars at 100 contracts per bet)