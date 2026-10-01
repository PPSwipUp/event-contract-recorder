# KXETH: model vs Kalshi's traded prices, 2024-11 to 2026-10

9876 hourly events, 24302 markets near the money that traded 10-20 min after the open.

## 1. Who gives better probabilities: the model or the traded price? (lower is better)

|   year |   markets |   model_logloss |   market_logloss |   model_brier |   market_brier | more_accurate   |
|-------:|----------:|----------------:|-----------------:|--------------:|---------------:|:----------------|
|   2024 |       304 |          0.5091 |           0.5223 |        0.1687 |         0.1733 | model           |
|   2025 |      8996 |          0.5255 |           0.5348 |        0.1754 |         0.1795 | model           |
|   2026 |     15002 |          0.4418 |           0.4431 |        0.1421 |         0.143  | model           |

Averaging the two (half model, half market): log loss 0.4696 vs market 0.4780 - if lower, the model adds information the market lacks.

## 2. Betting rules (real traded prices, Kalshi fees, 100 contracts per bet)

| rule                           |   bets |   c_per_bet |   dollars_100 |   dollars_at_traded_size |   day_t |   excl_AugSep26_bets |   excl_AugSep26_c_per_bet |   excl_AugSep26_dollars_100 |   excl_AugSep26_dollars_at_traded_size |   excl_AugSep26_day_t |
|:-------------------------------|-------:|------------:|--------------:|-------------------------:|--------:|---------------------:|--------------------------:|----------------------------:|---------------------------------------:|----------------------:|
| forward (rolling, volview, 5c) |   1754 |        2.1  |       3688.57 |                   620.44 |    1.95 |                 1525 |                      2.56 |                     3898.41 |                                 829.96 |                  2.17 |
| sweep (fixed, shrink50, 2c)    |   3018 |        1.47 |       4450.66 |                    36.99 |    1.85 |                 2678 |                      1.88 |                     5036.47 |                                 397.81 |                  2.21 |
| base (fixed, none, 5c)         |   2688 |        2.79 |       7487.99 |                  1096.28 |    3.19 |                 2389 |                      3.06 |                     7300.1  |                                1047.23 |                  3.27 |
| walk-forward self-tuning       |   3872 |        2.76 |      10679.2  |                  2637.32 |    3.8  |                 3643 |                      3.17 |                    11550.3  |                                2756.62 |                  4.32 |

Dollars by year (100 contracts per bet):

|    y |   forward (rolling, volview, 5c) |   sweep (fixed, shrink50, 2c) |   base (fixed, none, 5c) |   walk-forward self-tuning |
|-----:|---------------------------------:|------------------------------:|-------------------------:|---------------------------:|
| 2024 |                               77 |                            96 |                       10 |                        nan |
| 2025 |                              983 |                           927 |                      986 |                       5184 |
| 2026 |                             2628 |                          3428 |                     6492 |                       5495 |
