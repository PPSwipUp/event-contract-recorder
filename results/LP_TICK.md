# Liquidity provider: fill loss vs reaction time (tick data, 20 markets, 2.2 online hours, 184 trades)

Join best bid/ask, 500 shares, back-of-queue fills, rewards excluded.

|   reaction_ms |   fills |   fill_pnl_$ |   per_online_hour_$ |
|--------------:|--------:|-------------:|--------------------:|
|           100 |       2 |          -25 |              -11.15 |
|           500 |       4 |          -35 |              -15.6  |
|          1000 |       4 |          -35 |              -15.6  |
|          3000 |       4 |          -35 |              -15.6  |
|         15000 |       4 |          -35 |              -15.6  |
|         60000 |       4 |          -35 |              -15.6  |

Break-even: the reaction time at which |fill loss per hour| falls below the reward income per hour (paper estimate from live/pmlp_tight.jsonl, an upper bound).
