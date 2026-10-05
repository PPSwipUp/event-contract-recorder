# Overnight drift: buy at the close, sell at the next open (Massive daily bars, ~2 years)

Cost per round trip shown as 0 / 2 / 4 bp (two crossings of a ~1 bp ETF spread; commission-free broker). First year = train, second = holdout (nothing fitted).

| etf   | period   |   cost_bp |   days |   night_bp_mean |     t |   annual_% |   day_bp_mean |   buy_hold_annual_% |
|:------|:---------|----------:|-------:|----------------:|------:|-----------:|--------------:|--------------------:|
| SPY   | train    |         0 |    246 |            1.91 |  0.4  |        4.8 |          4.22 |                15.4 |
| SPY   | train    |         2 |    246 |           -0.09 | -0.02 |       -0.2 |          4.22 |                15.4 |
| SPY   | train    |         4 |    246 |           -2.09 | -0.44 |       -5.3 |          4.22 |                15.4 |
| SPY   | holdout  |         0 |    252 |            5.82 |  1.72 |       14.7 |         -0.38 |                13.7 |
| SPY   | holdout  |         2 |    252 |            3.82 |  1.13 |        9.6 |         -0.38 |                13.7 |
| SPY   | holdout  |         4 |    252 |            1.82 |  0.54 |        4.6 |         -0.38 |                13.7 |
| QQQ   | train    |         0 |    246 |            4.18 |  0.72 |       10.5 |          4.3  |                21.4 |
| QQQ   | train    |         2 |    246 |            2.18 |  0.38 |        5.5 |          4.3  |                21.4 |
| QQQ   | train    |         4 |    246 |            0.18 |  0.03 |        0.5 |          4.3  |                21.4 |
| QQQ   | holdout  |         0 |    252 |            8.15 |  1.55 |       20.5 |          0.26 |                21.2 |
| QQQ   | holdout  |         2 |    252 |            6.15 |  1.17 |       15.5 |          0.26 |                21.2 |
| QQQ   | holdout  |         4 |    252 |            4.15 |  0.79 |       10.4 |          0.26 |                21.2 |
| IWM   | train    |         0 |    246 |            2.98 |  0.47 |        7.5 |          1.05 |                10.1 |
| IWM   | train    |         2 |    246 |            0.98 |  0.16 |        2.5 |          1.05 |                10.1 |
| IWM   | train    |         4 |    246 |           -1.02 | -0.16 |       -2.6 |          1.05 |                10.1 |
| IWM   | holdout  |         0 |    252 |            5.88 |  1.24 |       14.8 |         -0.23 |                14.3 |
| IWM   | holdout  |         2 |    252 |            3.88 |  0.82 |        9.8 |         -0.23 |                14.3 |
| IWM   | holdout  |         4 |    252 |            1.88 |  0.4  |        4.7 |         -0.23 |                14.3 |
