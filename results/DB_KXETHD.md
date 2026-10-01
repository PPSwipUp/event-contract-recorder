# KXETHD: model vs Kalshi's traded prices, 2024-11 to 2026-10

11140 hourly events, 38951 markets near the money that traded 10-20 min after the open.

## 1. Who gives better probabilities: the model or the traded price? (lower is better)

|   year |   markets |   model_logloss |   market_logloss |   model_brier |   market_brier | more_accurate   |
|-------:|----------:|----------------:|-----------------:|--------------:|---------------:|:----------------|
|   2024 |       401 |          0.5903 |           0.6091 |        0.2003 |         0.2044 | model           |
|   2025 |     12585 |          0.4686 |           0.4782 |        0.1517 |         0.1555 | model           |
|   2026 |     25965 |          0.3296 |           0.3252 |        0.1009 |         0.1001 | market          |

Averaging the two (half model, half market): log loss 0.3722 vs market 0.3776 - if lower, the model adds information the market lacks.

## 2. Betting rules (real traded prices, Kalshi fees, 100 contracts per bet)

| rule                           |   bets |   c_per_bet |   dollars_100 |   dollars_at_traded_size |   day_t |   excl_AugSep26_bets |   excl_AugSep26_c_per_bet |   excl_AugSep26_dollars_100 |   excl_AugSep26_dollars_at_traded_size |   excl_AugSep26_day_t |
|:-------------------------------|-------:|------------:|--------------:|-------------------------:|--------:|---------------------:|--------------------------:|----------------------------:|---------------------------------------:|----------------------:|
| forward (rolling, volview, 5c) |   1611 |       -0.14 |       -221.29 |                 -1125.21 |   -0.13 |                 1157 |                      0.85 |                      984.42 |                               -1069.52 |                  0.69 |
| sweep (fixed, shrink50, 2c)    |   5802 |        0.38 |       2203.28 |                  -985.76 |    0.74 |                 3748 |                      0.55 |                     2064.37 |                               -1662.41 |                  0.85 |
| base (fixed, none, 5c)         |   4194 |        0.63 |       2647.48 |                  -473.7  |    0.98 |                 2943 |                      1.58 |                     4652.73 |                                   2.25 |                  2    |
| walk-forward self-tuning       |   4787 |        0.78 |       3722.36 |                   579.93 |    1.41 |                 3867 |                      1.24 |                     4813.01 |                                 774.84 |                  2.01 |

Dollars by year (100 contracts per bet):

|    y |   forward (rolling, volview, 5c) |   sweep (fixed, shrink50, 2c) |   base (fixed, none, 5c) |   walk-forward self-tuning |
|-----:|---------------------------------:|------------------------------:|-------------------------:|---------------------------:|
| 2024 |                             -121 |                            15 |                      -95 |                        nan |
| 2025 |                              526 |                          1746 |                     2961 |                       4168 |
| 2026 |                             -626 |                           442 |                     -218 |                       -446 |
