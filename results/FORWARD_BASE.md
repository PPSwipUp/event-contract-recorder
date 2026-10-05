# Forward test 2: baseline rule on BTC + ETH hourly ranges (frozen 2026-10-01)

Pre-registered: success = day-level t above 2 after at least 60 days.

Days: 3 · bets: 22 · total at 100 contracts: **$1** · day-level t: **0.01**

| series   |   days |   bets |   dollars_100 |
|:---------|-------:|-------:|--------------:|
| KXBTC    |      3 |     13 |         79.46 |
| KXETH    |      3 |      9 |        -78.4  |

| day        | series   |   events |   bets |   pnl_c |
|:-----------|:---------|---------:|-------:|--------:|
| 2026-10-02 | KXBTC    |       24 |      0 |    0    |
| 2026-10-02 | KXETH    |       24 |      1 |  -21.12 |
| 2026-10-03 | KXBTC    |       24 |      5 |   95.75 |
| 2026-10-03 | KXETH    |       24 |      4 |   12.13 |
| 2026-10-04 | KXBTC    |       24 |      8 |  -16.29 |
| 2026-10-04 | KXETH    |       24 |      4 |  -69.41 |