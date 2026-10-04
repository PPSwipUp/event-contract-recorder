# Kalshi CPI m/m ladders vs Cleveland Fed nowcast (PLAN_CPI.md)

Releases with a nowcast: 45 (train 24, holdout 21); entries 450
Train nowcast error (actual - nowcast): mean -0.068, sd 0.113

nowcast train: bets 58 over 21 releases, mean -1.66c/contract, clustered t -0.46, median print size 25
nowcast holdout: bets 73 over 21 releases, mean +0.27c/contract, clustered t 0.07, median print size 18
nowcast holdout Brier (YES-taker entries): model 0.1107 vs entry price 0.0594

placebo: previous month's CPI train: bets 78 over 23 releases, mean -4.94c/contract, clustered t -1.27, median print size 45
placebo: previous month's CPI holdout: bets 100 over 21 releases, mean -9.10c/contract, clustered t -4.15, median print size 34
placebo: previous month's CPI holdout Brier (YES-taker entries): model 0.2407 vs entry price 0.0594

GATE (nowcast, holdout): mean +0.27c/contract, t 0.07 -> FAIL
