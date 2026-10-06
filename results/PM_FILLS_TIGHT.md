# Paper LP fills: pmlp_tight

## Logged fills (19)

| time_utc    | market                                   | side     |   price |   mid_before |   mo_5m_c |   mo_1h_c |   mo_24h_c | mo_settle_c   |   jump24h_before | jumpy(top decile)   |
|:------------|:-----------------------------------------|:---------|--------:|-------------:|----------:|----------:|-----------:|:--------------|-----------------:|:--------------------|
| 10-05 12:48 | Will the Fed increase interest rates by  | buy_yes  |    0.16 |        0.165 |       0.5 |       0.5 |        1.5 |               |           0.0004 | False               |
| 10-05 14:50 | Will there be no change in Fed interest  | buy_yes  |    0.82 |        0.825 |      -0.5 |      -3.5 |      nan   |               |           0.0013 | False               |
| 10-05 14:59 | Will there be no change in Fed interest  | sell_yes |    0.81 |        0.805 |       0.5 |       2.5 |      nan   |               |           0.0013 | False               |
| 10-05 14:56 | Will the Fed increase interest rates by  | buy_yes  |    0.19 |        0.195 |      -0.5 |       2.5 |      nan   |               |           0.0004 | False               |
| 10-05 15:29 | Will there be no change in Fed interest  | sell_yes |    0.78 |        0.775 |       0.5 |       0.5 |      nan   |               |           0.0021 | False               |
| 10-05 15:29 | Will the Fed increase interest rates by  | buy_yes  |    0.21 |        0.215 |       0.5 |       0.5 |      nan   |               |           0.0013 | False               |
| 10-05 15:41 | Will there be no change in Fed interest  | buy_yes  |    0.79 |        0.795 |      -0.5 |      -0.5 |      nan   |               |           0.0021 | False               |
| 10-05 16:30 | Will the Fed increase interest rates by  | sell_yes |    0.21 |        0.205 |      -0.5 |       0.5 |      nan   |               |           0.0037 | False               |
| 10-05 19:41 | Israel accuses Iran/proxies of plane sta | buy_yes  |    0.08 |        0.085 |       2.5 |       1.5 |      nan   |               |           0.0023 | False               |
| 10-05 19:46 | Israel accuses Iran/proxies of plane sta | sell_yes |    0.09 |        0.085 |       0.5 |      -0.5 |      nan   |               |           0.0023 | False               |
| 10-05 19:46 | Israel accuses Iran/proxies of plane sta | buy_yes  |    0.08 |        0.085 |       0.5 |       1.5 |      nan   |               |           0.0023 | False               |
| 10-05 19:51 | Israel accuses Iran/proxies of plane sta | sell_yes |    0.1  |        0.095 |       0.5 |       0.5 |      nan   |               |           0.0023 | False               |
| 10-05 19:54 | Israel accuses Iran/proxies of plane sta | buy_yes  |    0.09 |        0.095 |       0.5 |       0.5 |      nan   |               |           0.0023 | False               |
| 10-05 19:56 | Israel accuses Iran/proxies of plane sta | sell_yes |    0.07 |        0.065 |      -2.5 |      -2.5 |      nan   |               |           0.0023 | False               |
| 10-05 20:01 | Israel accuses Iran/proxies of plane sta | buy_yes  |    0.08 |        0.085 |       0.5 |       1.5 |      nan   |               |           0.0027 | False               |
| 10-06 06:35 | Israel accuses Iran/proxies of plane sta | buy_yes  |    0.09 |        0.1   |       1   |       1.5 |      nan   |               |           0.0031 | False               |
| 10-06 07:35 | Israel accuses Iran/proxies of plane sta | sell_yes |    0.1  |        0.09  |       1   |       1.5 |      nan   |               |           0.0044 | False               |
| 10-06 10:36 | Israel accuses Iran/proxies of plane sta | sell_yes |    0.09 |        0.085 |       0.5 |      -0.5 |      nan   |               |           0.0048 | False               |
| 10-06 11:43 | Will the Fed increase interest rates by  | sell_yes |    0.18 |        0.175 |       0.5 |       0.5 |      nan   |               |           0.0037 | False               |

Mean mark-out (cents/share, + = good for us): mo_5m_c +0.29 (n 19), mo_1h_c +0.45 (n 19), mo_24h_c +1.50 (n 1), mo_settle_c +nan (n 0)

## Fills before per-fill logging (reconstructed per market from state; no timestamps)

| market                                        |   fills |   buys |   sells |   net_shares |   avg_price(one-way only) |   mark_now | settled   |   pnl_$ |   jump24h_now | mid_in_0.10-0.90   |
|:----------------------------------------------|--------:|-------:|--------:|-------------:|--------------------------:|-----------:|:----------|--------:|--------------:|:-------------------|
| 2026 Balance of Power: D Senate, D House      |       1 |      1 |       0 |          500 |                     0.66  |      0.655 | False     |    -2.5 |        0      | True               |
| Will the Fed increase interest rates by 25 bp |       1 |      0 |       0 |            0 |                   nan     |      0.175 | False     |     0   |        0.0029 | True               |
| Any of the Cornell 7 charged with a felony se |       1 |      0 |       1 |         -500 |                     0.3   |      0.295 | False     |     2.5 |        0      | True               |
| Israel accuses Iran/proxies of plane stabbing |       4 |      1 |       3 |        -1000 |                   nan     |      0.09  | False     |    45   |        0.0052 | False              |
| Will the Democratic Party control the Senate  |       2 |      0 |       2 |        -1000 |                     0.655 |      0.645 | False     |    10   |        0.0004 | True               |
| Will Missouri enact a data center moratorium  |       1 |      1 |       0 |          500 |                     0.24  |      0.255 | False     |     7.5 |        0.0004 | True               |

Total marked P&L of these positions: $+62.50
