# Kalshi monthly BTC max/min vs volatility model (2026)

Entries (first trade per market/side/day, strike not yet hit): 5763; k = 0.60

Brier (lower better): model 0.0784 vs traded price 0.0764

## Margin picked on Jan-Apr

|   margin_c |   train_bets |   train_c_per_bet |   train_total_$ |   train_per_month_$ | train_months_pos   |   train_day_t |   train_avg_contracts |
|-----------:|-------------:|------------------:|----------------:|--------------------:|:-------------------|--------------:|----------------------:|
|          3 |          419 |              0.98 |             222 |                  56 | 2/4                |          0.24 |                  85.5 |
|          5 |          285 |              1.3  |             208 |                  52 | 2/4                |          0.29 |                  85   |
|          8 |          176 |              1.12 |              66 |                  16 | 2/4                |          0.11 |                  85.1 |
|         12 |           68 |              8.81 |             589 |                 147 | 2/4                |          1.65 |                  89.2 |
|         20 |            3 |             60.19 |             101 |                  51 | 2/2                |          1.37 |                  48.3 |

Chosen 12c

## Holdout May-Sep (run once)

|   cap |   bets |   c_per_bet |   total_$ |   per_month_$ | months_pos   |   day_t |   avg_contracts |
|------:|-------:|------------:|----------:|--------------:|:-------------|--------:|----------------:|
|   100 |     86 |       -5.58 |      -234 |           -47 | 3/5          |   -0.59 |            77.6 |
|   500 |     86 |       -5.58 |     -1504 |          -301 | 3/5          |   -0.9  |           299.3 |

### Holdout by series / side

|                        |   bets |   c_per_bet |
|:-----------------------|-------:|------------:|
| ('KXBTCMAXMON', 'no')  |     28 |       14.28 |
| ('KXBTCMINMON', 'no')  |     57 |      -14.24 |
| ('KXBTCMINMON', 'yes') |      2 |      -38.12 |
