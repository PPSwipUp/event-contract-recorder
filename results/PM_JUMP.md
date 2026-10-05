# Does PPC predict Polymarket price jumps (liquidity-provider risk)?

129 markets, 133563 test market-hours, jumps (next-hour |dp| >= 3c): 1441 (1.08%)

| forecast | jump AUC | jumps caught by pulling riskiest 10% | log-move MSE |
|---|---|---|---|
| ppc | 0.751 | 50.2% | 0.964 |
| last | 0.750 | 52.7% | 0.748 |
| day | 0.853 | 65.7% | 0.754 |

Market-level: Spearman(mean forecast, jump rate) ppc 0.920, day 0.926
