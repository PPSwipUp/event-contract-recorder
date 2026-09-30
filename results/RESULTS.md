# Volatility model vs Kalshi's real hourly range prices

## KXBTC

40 hourly events, 7412 brackets, 2026-09-28 to 2026-09-30; vol model trained from 2026-09-20.

Brackets with a live quote 1 h before: 0%. Median spread 2c.

Accuracy of the probabilities (Brier score, lower is better) on quoted brackets: ppc 0.0226, last 0.0261, day 0.0289, **market 0.0261**

| vol   |   margin_c |   order_size |   trades |   cents_per_trade |   se |   return_on_cost |
|:------|-----------:|-------------:|---------:|------------------:|-----:|-----------------:|
| ppc   |          2 |            1 |        1 |             54    |  nan |            1.227 |
| ppc   |          2 |          100 |        1 |             54.27 |  nan |            1.233 |
| ppc   |          5 |            1 |        0 |            nan    |  nan |          nan     |
| ppc   |          5 |          100 |        0 |            nan    |  nan |          nan     |
| ppc   |         10 |            1 |        0 |            nan    |  nan |          nan     |
| ppc   |         10 |          100 |        0 |            nan    |  nan |          nan     |
| last  |          2 |            1 |        0 |            nan    |  nan |          nan     |
| last  |          2 |          100 |        0 |            nan    |  nan |          nan     |
| last  |          5 |            1 |        0 |            nan    |  nan |          nan     |
| last  |          5 |          100 |        0 |            nan    |  nan |          nan     |
| last  |         10 |            1 |        0 |            nan    |  nan |          nan     |
| last  |         10 |          100 |        0 |            nan    |  nan |          nan     |
| day   |          2 |            1 |        0 |            nan    |  nan |          nan     |
| day   |          2 |          100 |        0 |            nan    |  nan |          nan     |
| day   |          5 |            1 |        0 |            nan    |  nan |          nan     |
| day   |          5 |          100 |        0 |            nan    |  nan |          nan     |
| day   |         10 |            1 |        0 |            nan    |  nan |          nan     |
| day   |         10 |          100 |        0 |            nan    |  nan |          nan     |

## KXETH

40 hourly events, 11740 brackets, 2026-09-28 to 2026-09-30; vol model trained from 2026-09-20.

Brackets with a live quote 1 h before: 0%. Median spread 4c.

Accuracy of the probabilities (Brier score, lower is better) on quoted brackets: ppc 0.0988, last 0.0988, day 0.0935, **market 0.0939**

| vol   |   margin_c |   order_size |   trades |   cents_per_trade |   se |   return_on_cost |
|:------|-----------:|-------------:|---------:|------------------:|-----:|-----------------:|
| ppc   |          2 |            1 |        0 |               nan |  nan |              nan |
| ppc   |          2 |          100 |        0 |               nan |  nan |              nan |
| ppc   |          5 |            1 |        0 |               nan |  nan |              nan |
| ppc   |          5 |          100 |        0 |               nan |  nan |              nan |
| ppc   |         10 |            1 |        0 |               nan |  nan |              nan |
| ppc   |         10 |          100 |        0 |               nan |  nan |              nan |
| last  |          2 |            1 |        0 |               nan |  nan |              nan |
| last  |          2 |          100 |        0 |               nan |  nan |              nan |
| last  |          5 |            1 |        0 |               nan |  nan |              nan |
| last  |          5 |          100 |        0 |               nan |  nan |              nan |
| last  |         10 |            1 |        0 |               nan |  nan |              nan |
| last  |         10 |          100 |        0 |               nan |  nan |              nan |
| day   |          2 |            1 |        0 |               nan |  nan |              nan |
| day   |          2 |          100 |        0 |               nan |  nan |              nan |
| day   |          5 |            1 |        0 |               nan |  nan |              nan |
| day   |          5 |          100 |        0 |               nan |  nan |              nan |
| day   |         10 |            1 |        0 |               nan |  nan |              nan |
| day   |         10 |          100 |        0 |               nan |  nan |              nan |
