# Jan-Jul 2026 holdout (ETH hourly ranges, real trade prices 10-20 min after open)

4075 events, 10492 brackets that traded near the money. Rules frozen beforehand; nothing was tuned on this period. day_t = t-statistic with each day as one observation.

| rule                                   |   bets |   c_per_bet |   dollars_100 |   dollars_at_traded_size |   median_traded_size |   day_t |   days_with_bets | months_positive   |
|:---------------------------------------|-------:|------------:|--------------:|-------------------------:|---------------------:|--------:|-----------------:|:------------------|
| forward  (rolling, volview, 5c)        |    994 |        2.96 |       2940.66 |                   406.22 |                  7.5 |    2.06 |              207 | 6/7               |
| sweep    (fixed, shrink50, 2c)         |   1664 |        2.56 |       4266.94 |                   932.52 |                  8   |    2.35 |              211 | 6/7               |
| base     (fixed, none, 5c)             |   1456 |        4.06 |       5908.94 |                   998.57 |                  6   |    3.56 |              210 | 7/7               |
| walk-forward (re-picks settings daily) |   1899 |        2.86 |       5430.73 |                  1100.12 |                  5   |    2.78 |              177 | 6/8               |

Settings the walk-forward bot picked most often (scale, filter, margin): ('fixed', 'none', np.int64(2)) x59, ('rolling', 'none', np.int64(5)) x40, ('fixed', 'none', np.int64(5)) x23, ('rolling', 'none', np.int64(2)) x19, ('rolling', 'shrink50', np.int64(2)) x17

## Month by month

| m       |   forward |   sweep |   base |   walk-forward |
|:--------|----------:|--------:|-------:|---------------:|
| 2026-01 |       560 |    -201 |      9 |           -128 |
| 2026-02 |      -580 |     449 |    332 |            563 |
| 2026-03 |       583 |     451 |   1659 |           1006 |
| 2026-04 |       809 |    1610 |   1979 |           1717 |
| 2026-05 |      1262 |     807 |   1015 |            946 |
| 2026-06 |         4 |     598 |    516 |             65 |
| 2026-07 |       302 |     553 |    398 |           1315 |
| 2026-08 |       nan |     nan |    nan |            -53 |

(dollars at 100 contracts per bet)

## Compounding the self-tuning bot from $1,000

Each bet risks a fixed share of the bankroll at the start of its day. 'capped' = never more contracts than actually traded at that price (realistic); 'uncapped' = unlimited liquidity (what the edge alone would do).

| risk_per_bet   | liquidity   |   final_$ |    CAGR |   max_drawdown |   days |
|:---------------|:------------|----------:|--------:|---------------:|-------:|
| 1%             | capped      |   1168.7  |   0.365 |          0.118 |    183 |
| 1%             | uncapped    |   3217.28 |   9.285 |          0.199 |    183 |
| 2%             | capped      |   1602.92 |   1.563 |          0.137 |    183 |
| 2%             | uncapped    |   7551.44 |  55.398 |          0.378 |    183 |
| 5%             | capped      |   2179.9  |   3.732 |          0.287 |    183 |
| 5%             | uncapped    |  14141.2  | 196.101 |          0.805 |    183 |