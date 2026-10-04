# Forward test 2: baseline rule on BTC + ETH hourly ranges (frozen 2026-10-01)

Pre-registered: success = day-level t above 2 after at least 60 days.

Days: 2 · bets: 10 · total at 100 contracts: **$87** · day-level t: **nan**

| series   |   days |   bets |   dollars_100 |
|:---------|-------:|-------:|--------------:|
| KXBTC    |      2 |      5 |         95.75 |
| KXETH    |      2 |      5 |         -8.99 |

| day        | series   |   events |   bets |   pnl_c |
|:-----------|:---------|---------:|-------:|--------:|
| 2026-10-02 | KXBTC    |       24 |      0 |    0    |
| 2026-10-02 | KXETH    |       24 |      1 |  -21.12 |
| 2026-10-03 | KXBTC    |       24 |      5 |   95.75 |
| 2026-10-03 | KXETH    |       24 |      4 |   12.13 |