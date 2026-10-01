# KXETH: model vs Kalshi's traded prices, 2024-11 to 2026-10

9876 hourly events, 24302 markets near the money that traded 10-20 min after the open.

## 1. Who gives better probabilities: the model or the traded price? (lower is better)

|   year |   markets |   model_logloss |   market_logloss |   model_brier |   market_brier | more_accurate   |
|-------:|----------:|----------------:|-----------------:|--------------:|---------------:|:----------------|
|   2024 |       304 |          0.5037 |           0.5223 |        0.1673 |         0.1733 | model           |
|   2025 |      8996 |          0.5248 |           0.5348 |        0.175  |         0.1795 | model           |
|   2026 |     15002 |          0.4348 |           0.4431 |        0.14   |         0.143  | model           |

Averaging the two (half model, half market): log loss 0.4672 vs market 0.4780 - if lower, the model adds information the market lacks.

## 2. Betting rules (real traded prices, Kalshi fees, 100 contracts per bet)

| rule                           |   bets |   c_per_bet |   dollars_100 |   day_t |   excl_AugSep26_bets |   excl_AugSep26_c_per_bet |   excl_AugSep26_dollars_100 |   excl_AugSep26_day_t |
|:-------------------------------|-------:|------------:|--------------:|--------:|---------------------:|--------------------------:|----------------------------:|----------------------:|
| forward (rolling, volview, 5c) |   2059 |        3.31 |       6808.34 |    3.6  |                 1742 |                      3.83 |                     6669.58 |                  3.77 |
| sweep (fixed, shrink50, 2c)    |   5629 |        7.51 |      42268.9  |   10.95 |                 4846 |                      7.97 |                    38645.1  |                 10.59 |
| base (fixed, none, 5c)         |   3516 |        5.32 |      18701.7  |    6.71 |                 3080 |                      5.76 |                    17734.9  |                  6.83 |
| walk-forward self-tuning       |   5718 |        7.1  |      40588.3  |   10.55 |                 4885 |                      7.63 |                    37286.5  |                 10.41 |

Dollars by year (100 contracts per bet):

|    y |   forward (rolling, volview, 5c) |   sweep (fixed, shrink50, 2c) |   base (fixed, none, 5c) |   walk-forward self-tuning |
|-----:|---------------------------------:|------------------------------:|-------------------------:|---------------------------:|
| 2024 |                               13 |                           -55 |                      149 |                        nan |
| 2025 |                              919 |                          8134 |                     2920 |                       7485 |
| 2026 |                             5877 |                         34190 |                    15632 |                      33104 |
