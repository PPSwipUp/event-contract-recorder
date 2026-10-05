# Settlement lag on Polymarket sports game markets

Games (volume > $1k): 2199 over ~119 days; trades after start+5h and before settlement: 6359
Median time from start+5h to settlement: -1.3 h

RISK: markets where a token traded >= 99c after the cutoff and then LOST: 1

## TAKER: buy the known winner

trades 595, shares 87,524, profit $11,554 = $97.1/day; median lock-up 1.2 h

| price          |   n |   shares |   profit |
|:---------------|----:|---------:|---------:|
| (0.0, 0.9]     | 196 |    34650 |    11081 |
| (0.9, 0.97]    |  47 |     4812 |      265 |
| (0.97, 0.99]   |  55 |     8899 |      159 |
| (0.99, 0.995]  |   7 |      143 |        1 |
| (0.995, 0.999] | 290 |    39020 |       49 |

| tag    |   n |    profit |   med_px |
|:-------|----:|----------:|---------:|
| mlb    |  35 |   206.18  |    0.97  |
| nfl    |   7 |   741.595 |    0.9   |
| nhl    |  59 |     0.351 |    0.999 |
| tennis | 494 | 10605.7   |    0.989 |

|          |   2026-09 |   2026-10 |
|:---------|----------:|----------:|
| profit_$ |     10256 |      1298 |

## MAKER: resting bid on the known winner

trades 289, shares 80,664, profit $4,757 = $40.0/day; median lock-up 1.0 h

| price          |   n |   shares |   profit |
|:---------------|----:|---------:|---------:|
| (0.0, 0.9]     |  41 |     8101 |     3502 |
| (0.9, 0.97]    |  15 |    25815 |     1130 |
| (0.97, 0.99]   |  32 |     5902 |       72 |
| (0.99, 0.995]  |  19 |     1806 |       14 |
| (0.995, 0.999] | 182 |    39039 |       39 |

| tag    |   n |   profit |   med_px |
|:-------|----:|---------:|---------:|
| epl    |  58 |   16.748 |    0.999 |
| mlb    |  15 | 1146.08  |    0.968 |
| nfl    |  10 |    0.607 |    0.999 |
| nhl    |  25 |   45.428 |    0.987 |
| soccer |   1 |    0.005 |    0.999 |
| tennis | 180 | 3548.36  |    0.999 |

|          |   2026-08 |   2026-09 |   2026-10 |
|:---------|----------:|----------:|----------:|
| profit_$ |        17 |      4403 |       337 |
