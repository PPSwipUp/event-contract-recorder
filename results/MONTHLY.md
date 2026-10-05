# Monthly backtest: volatility model vs Kalshi hourly ranges (bets at a 5c margin, <=100 contracts)

## Month by month

| series   |   min_after_open | month   |   bets |   cents_per_bet |    se |   share_fillable |   dollars_at_real_size |
|:---------|-----------------:|:--------|-------:|----------------:|------:|-----------------:|-----------------------:|
| KXBTC    |                1 | 2026-07 |      8 |            7.39 | 13.43 |             1    |                 -11.58 |
| KXBTC    |                1 | 2026-08 |     65 |            1.19 |  4.71 |             0.77 |                 109.1  |
| KXBTC    |                1 | 2026-09 |    106 |           30.84 |  3.09 |             0.96 |                3437.87 |
| KXBTC    |                5 | 2026-07 |     21 |           -7.87 |  9.6  |             1    |                 -20.52 |
| KXBTC    |                5 | 2026-08 |    106 |           -6.91 |  4.06 |             0.8  |                -122.28 |
| KXBTC    |                5 | 2026-09 |     40 |            0.31 |  6.73 |             0.8  |                 -95.79 |
| KXBTC    |               15 | 2026-07 |     23 |          -11.85 |  8.65 |             0.83 |                -195.06 |
| KXBTC    |               15 | 2026-08 |    165 |           -1.71 |  3.32 |             0.73 |                -176.74 |
| KXBTC    |               15 | 2026-09 |     88 |           -0.18 |  4.51 |             0.78 |                -556.91 |
| KXETH    |                1 | 2026-07 |     15 |          -21.38 |  7.22 |             0.53 |                 -64.56 |
| KXETH    |                1 | 2026-08 |    101 |            0.65 |  4.18 |             0.61 |                 -80.38 |
| KXETH    |                1 | 2026-09 |     69 |            0.78 |  4.66 |             0.59 |                 173.69 |
| KXETH    |                5 | 2026-07 |     23 |          -18.04 |  6.54 |             0.61 |                -190.54 |
| KXETH    |                5 | 2026-08 |    134 |           -0.04 |  3.76 |             0.57 |                 207.56 |
| KXETH    |                5 | 2026-09 |     82 |            4.84 |  4.85 |             0.5  |                 118.43 |
| KXETH    |               15 | 2026-07 |     30 |          -15.78 |  5.83 |             0.53 |                -182.26 |
| KXETH    |               15 | 2026-08 |    150 |            2.47 |  3.41 |             0.32 |                  10.47 |
| KXETH    |               15 | 2026-09 |    138 |            3.8  |  3.85 |             0.37 |                 213.01 |

## Totals and concentration

| series   |   min_after_open |   bets |   cents_per_bet |   t_stat |   dollars_total |   days_with_bets |   share_of_profit_from_top_5_days |   dollars_without_top_5_days |   months_positive |   months |
|:---------|-----------------:|-------:|----------------:|---------:|----------------:|-----------------:|----------------------------------:|-----------------------------:|------------------:|---------:|
| KXBTC    |                1 |    179 |          19.022 |    6.862 |        3535.38  |               35 |                             1.045 |                     -159.772 |                 3 |        3 |
| KXBTC    |                5 |    167 |          -5.298 |   -1.624 |        -238.587 |               47 |                           nan     |                     -686.739 |                 1 |        3 |
| KXBTC    |               15 |    276 |          -2.066 |   -0.809 |        -928.711 |               59 |                           nan     |                    -1257.74  |                 0 |        3 |
| KXETH    |                1 |    185 |          -1.087 |   -0.369 |          28.752 |               50 |                            12.218 |                     -322.54  |                 2 |        3 |
| KXETH    |                5 |    239 |          -0.098 |   -0.035 |         135.45  |               55 |                             2.999 |                     -270.809 |                 1 |        3 |
| KXETH    |               15 |    318 |           1.324 |    0.552 |          41.223 |               62 |                             9.694 |                     -358.41  |                 2 |        3 |

## How fast would you have needed to be? (bets 1 min after open)

Share of bets where others were still buying at our price or better N seconds after the market opened.

| series   |   bets |   bets_with_trade_data |   after_5s |   median_contracts_after_5s |   after_15s |   median_contracts_after_15s |   after_30s |   median_contracts_after_30s |   after_60s |   median_contracts_after_60s |
|:---------|-------:|-----------------------:|-----------:|----------------------------:|------------:|-----------------------------:|------------:|-----------------------------:|------------:|-----------------------------:|
| KXBTC    |    179 |                    174 |      0.888 |                     8604.53 |       0.888 |                      6871.16 |       0.888 |                         4961 |       0.86  |                       4830   |
| KXETH    |    185 |                    137 |      0.6   |                      120    |       0.584 |                       120    |       0.557 |                          100 |       0.378 |                         21.5 |

## Network latency to Kalshi from a GitHub (Azure, US) runner

```
resolves to: 52.85.193.129 52.85.193.52 52.85.193.85 52.85.193.29 
connect 0.004460s  tls 0.025433s  first byte 0.051192s
connect 0.004660s  tls 0.025570s  first byte 0.034605s
connect 0.004480s  tls 0.024906s  first byte 0.032847s
connect 0.005507s  tls 0.033798s  first byte 0.042632s
connect 0.009880s  tls 0.030787s  first byte 0.040917s
52.85.193.129 [('GLOBAL', 'AMAZON'), ('GLOBAL', 'CLOUDFRONT')]
52.85.193.52 [('GLOBAL', 'AMAZON'), ('GLOBAL', 'CLOUDFRONT')]
52.85.193.29 [('GLOBAL', 'AMAZON'), ('GLOBAL', 'CLOUDFRONT')]
52.85.193.85 [('GLOBAL', 'AMAZON'), ('GLOBAL', 'CLOUDFRONT')]
```
