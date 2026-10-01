# KXBTC: model vs Kalshi's traded prices, 2024-11 to 2026-10

11662 hourly events, 59837 markets near the money that traded 10-20 min after the open.

## 1. Who gives better probabilities: the model or the traded price? (lower is better)

|   year |   markets |   model_logloss |   market_logloss |   model_brier |   market_brier | more_accurate   |
|-------:|----------:|----------------:|-----------------:|--------------:|---------------:|:----------------|
|   2024 |       739 |          0.4059 |           0.4279 |        0.1273 |         0.1322 | model           |
|   2025 |     20657 |          0.4251 |           0.4337 |        0.1342 |         0.1371 | model           |
|   2026 |     38441 |          0.3548 |           0.3566 |        0.1069 |         0.1074 | model           |

Averaging the two (half model, half market): log loss 0.3789 vs market 0.3841 - if lower, the model adds information the market lacks.

## 2. Betting rules (real traded prices, Kalshi fees, 100 contracts per bet)

| rule                           |   bets |   c_per_bet |   dollars_100 |   day_t |   excl_AugSep26_bets |   excl_AugSep26_c_per_bet |   excl_AugSep26_dollars_100 |   excl_AugSep26_day_t |
|:-------------------------------|-------:|------------:|--------------:|--------:|---------------------:|--------------------------:|----------------------------:|----------------------:|
| forward (rolling, volview, 5c) |   2532 |        1.39 |       3516.01 |    1.53 |                 2248 |                      2.04 |                     4581.24 |                  2.14 |
| sweep (fixed, shrink50, 2c)    |  12447 |        5.78 |      71984.4  |   14.45 |                10564 |                      5.8  |                    61321.7  |                 13.56 |
| base (fixed, none, 5c)         |   4849 |        3.95 |      19172.4  |    6.11 |                 4249 |                      4.41 |                    18741.9  |                  6.35 |
| walk-forward self-tuning       |  12324 |        5.51 |      67879.8  |   13.78 |                10419 |                      5.51 |                    57458.4  |                 12.88 |

Dollars by year (100 contracts per bet):

|    y |   forward (rolling, volview, 5c) |   sweep (fixed, shrink50, 2c) |   base (fixed, none, 5c) |   walk-forward self-tuning |
|-----:|---------------------------------:|------------------------------:|-------------------------:|---------------------------:|
| 2024 |                              -46 |                           743 |                      464 |                        nan |
| 2025 |                             3458 |                         23016 |                    10992 |                      20534 |
| 2026 |                              104 |                         48225 |                     7716 |                      47345 |
