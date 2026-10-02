# KXBTC15M (15-min up/down) vs volatility model, Aug-Sep 2026

Minute quotes used: 73138; events 5786; k = 0.59; median spread 1.00c

Brier on all minute quotes (lower better): model 0.1541 vs Kalshi mid 0.1496

## Margin chosen on August

|   margin_c |   aug_bets |   aug_c_per_bet |   aug_pred_edge_c |   aug_total_$ |   aug_day_t |   aug_win |
|-----------:|-----------:|----------------:|------------------:|--------------:|------------:|----------:|
|          1 |       2931 |           -2.01 |              4.62 |         -5894 |       -2.94 |     0.526 |
|          2 |       2890 |           -1.46 |              5.27 |         -4230 |       -2.07 |     0.514 |
|          3 |       2779 |           -1.11 |              6.14 |         -3082 |       -1.62 |     0.494 |
|          5 |       2432 |           -1.14 |              8.16 |         -2761 |       -2.02 |     0.454 |
|          8 |       1846 |           -1.17 |             11.19 |         -2163 |       -1.6  |     0.408 |

Chosen: 8c

## September (run once)

| bot                        |   bets |   c_per_bet |   pred_edge_c |   total_$ |   day_t |   win |
|:---------------------------|-------:|------------:|--------------:|----------:|--------:|------:|
| model                      |   1539 |        1.45 |         10.97 |      2228 |    1.29 | 0.442 |
| placebo: spot 5 min staler |   2848 |       -3.74 |         20.49 |    -10652 |   -4.29 | 0.355 |
