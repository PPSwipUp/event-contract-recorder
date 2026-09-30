# Volatility model vs Kalshi's real hourly range prices

## KXBTC

87 hourly events, 16032 brackets, 2026-09-26 to 2026-09-30; vol model trained from 2026-05-01.

Brackets with a live quote 1 h before: 0%. Median spread 3c.

Accuracy of the probabilities (Brier score, lower is better) on quoted brackets: ppc 0.0361, last 0.0357, day 0.0359, **market 0.0373**

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

## KXETH

87 hourly events, 25320 brackets, 2026-09-26 to 2026-09-30; vol model trained from 2026-05-01.

Brackets with a live quote 1 h before: 0%. Median spread 5c.

Accuracy of the probabilities (Brier score, lower is better) on quoted brackets: ppc 0.0680, last 0.0710, day 0.0692, **market 0.0623**

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
