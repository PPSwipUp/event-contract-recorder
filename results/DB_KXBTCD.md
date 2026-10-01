# KXBTCD: model vs Kalshi's traded prices, 2024-11 to 2026-10

11924 hourly events, 90017 markets near the money that traded 10-20 min after the open.

## 1. Who gives better probabilities: the model or the traded price? (lower is better)

|   year |   markets |   model_logloss |   market_logloss |   model_brier |   market_brier | more_accurate   |
|-------:|----------:|----------------:|-----------------:|--------------:|---------------:|:----------------|
|   2024 |      1161 |          0.5109 |           0.5148 |        0.1682 |         0.1725 | model           |
|   2025 |     32957 |          0.3999 |           0.3987 |        0.1262 |         0.1263 | market          |
|   2026 |     55899 |          0.3593 |           0.3492 |        0.1112 |         0.1097 | market          |

Averaging the two (half model, half market): log loss 0.3682 vs market 0.3694 - if lower, the model adds information the market lacks.

## 2. Betting rules (real traded prices, Kalshi fees, 100 contracts per bet)

| rule                           |   bets |   c_per_bet |   dollars_100 |   dollars_at_traded_size |   day_t |   excl_AugSep26_bets |   excl_AugSep26_c_per_bet |   excl_AugSep26_dollars_100 |   excl_AugSep26_dollars_at_traded_size |   excl_AugSep26_day_t |
|:-------------------------------|-------:|------------:|--------------:|-------------------------:|--------:|---------------------:|--------------------------:|----------------------------:|---------------------------------------:|----------------------:|
| forward (rolling, volview, 5c) |   3467 |        0.61 |       2130.49 |                  1361.95 |    0.77 |                 2976 |                      0.87 |                     2600.73 |                                1904.15 |                  1.02 |
| sweep (fixed, shrink50, 2c)    |  10878 |        0.2  |       2152.02 |                   508.21 |    0.42 |                 9662 |                      0.53 |                     5120.64 |                                1353.49 |                  1.06 |
| base (fixed, none, 5c)         |   8881 |        0.38 |       3354.3  |                   460.39 |    0.74 |                 7894 |                      0.7  |                     5564.93 |                                 951.75 |                  1.31 |
| walk-forward self-tuning       |  12152 |        0.57 |       6886.22 |                  2057.57 |    1.42 |                11633 |                      0.54 |                     6299.02 |                                2489.48 |                  1.33 |

Dollars by year (100 contracts per bet):

|    y |   forward (rolling, volview, 5c) |   sweep (fixed, shrink50, 2c) |   base (fixed, none, 5c) |   walk-forward self-tuning |
|-----:|---------------------------------:|------------------------------:|-------------------------:|---------------------------:|
| 2024 |                              407 |                           236 |                      653 |                        nan |
| 2025 |                             1687 |                          8816 |                     6639 |                       7092 |
| 2026 |                               36 |                         -6900 |                    -3938 |                       -206 |
