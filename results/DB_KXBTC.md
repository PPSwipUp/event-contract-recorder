# KXBTC: model vs Kalshi's traded prices, 2024-11 to 2026-10

11662 hourly events, 59837 markets near the money that traded 10-20 min after the open.

## 1. Who gives better probabilities: the model or the traded price? (lower is better)

|   year |   markets |   model_logloss |   market_logloss |   model_brier |   market_brier | more_accurate   |
|-------:|----------:|----------------:|-----------------:|--------------:|---------------:|:----------------|
|   2024 |       739 |          0.4099 |           0.4279 |        0.128  |         0.1322 | model           |
|   2025 |     20657 |          0.4268 |           0.4337 |        0.1345 |         0.1371 | model           |
|   2026 |     38441 |          0.3571 |           0.3566 |        0.1074 |         0.1074 | market          |

Averaging the two (half model, half market): log loss 0.3800 vs market 0.3841 - if lower, the model adds information the market lacks.

## 2. Betting rules (real traded prices, Kalshi fees, 100 contracts per bet)

| rule                           |   bets |   c_per_bet |   dollars_100 |   dollars_at_traded_size |   day_t |   excl_AugSep26_bets |   excl_AugSep26_c_per_bet |   excl_AugSep26_dollars_100 |   excl_AugSep26_dollars_at_traded_size |   excl_AugSep26_day_t |
|:-------------------------------|-------:|------------:|--------------:|-------------------------:|--------:|---------------------:|--------------------------:|----------------------------:|---------------------------------------:|----------------------:|
| forward (rolling, volview, 5c) |   2288 |        2.74 |       6264.13 |                  2162.71 |    2.91 |                 2062 |                      2.91 |                     5993.84 |                                1723.19 |                  2.97 |
| sweep (fixed, shrink50, 2c)    |   4570 |        1.76 |       8025.91 |                  3482.93 |    2.94 |                 4016 |                      2.15 |                     8639.49 |                                3073.82 |                  3.41 |
| base (fixed, none, 5c)         |   3546 |        2.67 |       9461.5  |                  2864.98 |    3.74 |                 3200 |                      3.15 |                    10088.5  |                                2677.59 |                  4.18 |
| walk-forward self-tuning       |   6995 |        1.26 |       8801.36 |                  2351.34 |    2.7  |                 6872 |                      1.24 |                     8494.48 |                                2283.99 |                  2.64 |

Dollars by year (100 contracts per bet):

|    y |   forward (rolling, volview, 5c) |   sweep (fixed, shrink50, 2c) |   base (fixed, none, 5c) |   walk-forward self-tuning |
|-----:|---------------------------------:|------------------------------:|-------------------------:|---------------------------:|
| 2024 |                               94 |                           556 |                      507 |                        nan |
| 2025 |                             4439 |                          6550 |                     5502 |                       4242 |
| 2026 |                             1730 |                           920 |                     3453 |                       4559 |
