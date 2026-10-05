# DVOL as an extra input to the next-hour volatility forecast

Fit on 2025, scored on 2026-01..09. log_rv = a + b*log(ppc) [+ c*log(DVOL hourly)].

| asset   | model      | coef                  |   test_mse_logrv |   test_qlike |   n_test |
|:--------|:-----------|:----------------------|-----------------:|-------------:|---------:|
| BTC     | ppc        | [-0.122, 0.979]       |           0.1175 |       9.9108 |     6612 |
| BTC     | dvol only  | [2.596, 1.554]        |           0.3176 |      -9.8129 |     6612 |
| BTC     | ppc + dvol | [0.204, 0.967, 0.073] |           0.1174 |       7.2125 |     6612 |
| ETH     | ppc        | [-0.237, 0.954]       |           0.1315 |      -4.1688 |     6612 |
| ETH     | dvol only  | [10.988, 3.29]        |           0.4757 |      -8.3617 |     6612 |
| ETH     | ppc + dvol | [0.873, 0.94, 0.241]  |           0.1323 |      -4.6983 |     6612 |
