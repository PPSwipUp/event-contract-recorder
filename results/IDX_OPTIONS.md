# Kalshi S&P daily ranges vs SPX same-day options (40 sampled 2026 days)

Kalshi entries with an options price at the same minute: 1180

## Who is more accurate? (Brier, lower is better)

options: 0.1492   Kalshi traded price: 0.1442

Average gap options minus Kalshi (cents, same side): -0.66; absolute gap median 2.85c, 90th pct 10.00c

## Relative value: margin picked on the first half

|   margin_c |   first_half_bets |   first_half_c_per_bet |   first_half_total_$ |   first_half_day_t |   first_half_days |
|-----------:|------------------:|-----------------------:|---------------------:|-------------------:|------------------:|
|          2 |                80 |                  -5.23 |                 -284 |              -1.01 |                15 |
|          5 |                44 |                   0.15 |                  -47 |              -0.22 |                13 |
|          8 |                23 |                   1.26 |                   16 |               0.13 |                12 |
|         12 |                13 |                  -2.24 |                   19 |               0.19 |                 8 |

Chosen margin 5c. Second half (run once): {'bets': 22, 'c_per_bet': np.float64(-23.93), 'total_$': -181, 'day_t': np.float64(-1.38), 'days': 10}

Locked-in arbitrage, option half-spread $0.05/leg (= 2c per contract), all days, margin 0: {'bets': 130, 'c_per_bet': np.float64(-8.16), 'total_$': -446, 'day_t': np.float64(-1.24), 'days': 31}
Locked-in arbitrage, option half-spread $0.10/leg (= 4c per contract), all days, margin 0: {'bets': 77, 'c_per_bet': np.float64(-15.32), 'total_$': -590, 'day_t': np.float64(-1.98), 'days': 26}
Locked-in arbitrage, option half-spread $0.15/leg (= 6c per contract), all days, margin 0: {'bets': 58, 'c_per_bet': np.float64(-15.22), 'total_$': -420, 'day_t': np.float64(-2.14), 'days': 23}
Note: the "locked-in" lines hold the Kalshi side to settlement after subtracting the option cost; they test whether the
gaps that look big enough to cover option costs are real.  They lose, and the options-implied probabilities are LESS
accurate than Kalshi's own prices (Brier 0.149 vs 0.144): with minute trade prices, most apparent gaps are measurement
noise in the options price, not mispricing on Kalshi.  No evidence of a usable S&P arbitrage.
