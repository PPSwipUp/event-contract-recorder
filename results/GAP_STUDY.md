# Fresh-price-level study (40 markets, 19.1 h of 3-s books incl. curfew gaps)

Snapshots with spread >= 2 ticks: 33.6%; fills on our improving orders: 193

Mark-out per share (cents; positive = good fill):

|       |   mk1_c |   mk5_c |   mk30_c |
|:------|--------:|--------:|---------:|
| count |  193    |  193    |   189    |
| mean  |    0.24 |    0.02 |    -0.44 |
| std   |    5.44 |    6.25 |     7.13 |
| min   |  -24.5  |  -33.5  |   -29    |
| 25%   |   -0.5  |   -0.5  |    -3.5  |
| 50%   |    0    |    0    |    -0.5  |
| 75%   |    1.5  |    1.5  |     1.5  |
| max   |   30    |   29.5  |    25    |

$ at 100 shares per fill, 5-min mark-out: 4.00

by spread width:

| spread_ticks   |   n |   mk5 |
|:---------------|----:|------:|
| (1, 2]         |  83 | -0.89 |
| (2, 4]         |  56 | -1.04 |
| (4, 10]        |  36 |  0.93 |
| (10, 1000]     |  18 |  5.72 |
