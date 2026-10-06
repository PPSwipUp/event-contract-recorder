# Skill or luck? Closing-line test of Polymarket US day-of fills (B/C/D, PLAN_PMUS.md)

Data checks: settlement values seen [0.0, 0.12, 1.0] over 60 markets (missing 0); fills per variant {'B': 148, 'C': 98, 'D': 63}

## 1) Mark-out curve: cents per contract after the fill (+ = good for us), t clustered by market

| variant   |   fills |   mo_5m_c |   mo_5m_t |   mo_30m_c |   mo_30m_t |   mo_60m_c |   mo_60m_t |   mo_close_c |   mo_close_t |   mo_settle_c |   mo_settle_t |
|:----------|--------:|----------:|----------:|-----------:|-----------:|-----------:|-----------:|-------------:|-------------:|--------------:|--------------:|
| B         |     148 |     -3.15 |     -6.15 |      -2.62 |      -5.03 |      -2.49 |      -4.86 |        -2.49 |        -4.69 |          1.43 |          0.73 |
| C         |      98 |     -3.4  |     -4.56 |      -2.66 |      -4.12 |      -2.42 |      -3.55 |        -3    |        -3.42 |          4.61 |          1.73 |
| D         |      63 |     -3.83 |     -4.13 |      -3.1  |      -4.11 |      -2.77 |      -3.3  |        -3.71 |        -3.25 |          3.03 |          0.57 |

## 2) Expected P&L at the closing line vs realised at settlement (fills only, before rewards/rebate)

| variant   |   markets |   expected_at_close_$ |   realised_settle_$ |   luck_$ |   luck_z (indep., overstated) |
|:----------|----------:|----------------------:|--------------------:|---------:|------------------------------:|
| B         |        60 |                 -1842 |                1055 |     2898 |                          1.86 |
| C         |        41 |                 -1470 |                2260 |     3730 |                          2.75 |
| D         |        32 |                 -1168 |                 955 |     2122 |                          1.65 |

## 4) By side and price band: closing-line value vs settlement value (cents/contract)

|                         |   fills |   clv_c |   settle_c |
|:------------------------|--------:|--------:|-----------:|
| ('B', 'buy', '25-75c')  |      37 |   -0.26 |      -8.73 |
| ('B', 'buy', '<25c')    |      18 |   -2.61 |       4.17 |
| ('B', 'buy', '>75c')    |       5 |    2.7  |      -1.2  |
| ('B', 'sell', '25-75c') |      50 |   -4.5  |      15.82 |
| ('B', 'sell', '<25c')   |      36 |   -2.18 |      -7.78 |
| ('B', 'sell', '>75c')   |       2 |  -11    |     -23    |
| ('C', 'buy', '25-75c')  |      24 |   -0.79 |     -11.96 |
| ('C', 'buy', '<25c')    |      14 |   -3.36 |      15.36 |
| ('C', 'buy', '>75c')    |       4 |    1.63 |      -6.25 |
| ('C', 'sell', '25-75c') |      31 |   -5.34 |      25.03 |
| ('C', 'sell', '<25c')   |      23 |   -2.13 |      -7.96 |
| ('C', 'sell', '>75c')   |       2 |  -10    |     -22    |
| ('D', 'buy', '25-75c')  |      12 |   -0.29 |     -14.08 |
| ('D', 'buy', '<25c')    |      11 |   -3.68 |      -1.55 |
| ('D', 'buy', '>75c')    |       2 |    9.5  |      21.5  |
| ('D', 'sell', '25-75c') |      19 |   -7.95 |      30.05 |
| ('D', 'sell', '<25c')   |      18 |   -2.64 |     -11.94 |
| ('D', 'sell', '>75c')   |       1 |  -10    |     -22    |

## 4b) Variant C by prop type

| prop   |   fills |   clv_c |   settle_c |
|:-------|--------:|--------:|-----------:|
| outs   |      40 |   -4.01 |       8.65 |
| rbi    |      17 |   -1.88 |      -0.24 |
| sb     |      16 |   -4.69 |      -5.75 |
| hrr    |      11 |   -2.36 |       8.91 |
| i1     |       7 |   -0.5  |       8.57 |
| ha     |       6 |    0.42 |      -3.5  |
| tb     |       1 |    0.5  |      65    |

## 5) Are the closing prices themselves biased? (all 587 props of the day, outcome vs closing mid)
- Well calibrated: Brier 0.132 (flat 0.5 = 0.250); bands 0-10c hit 2.3% at 4.8c, 10-25c 15.4% at 17.6c, 25-50c 39.7% at 36.9c,
  50-75c 59.1% at 62.4c. Overall overs ran 1.9c rich (tb/hr/rbi/sb 2.7-4.8c) - a small known prop bias.
- 'outs' looks -26c biased, but that is 2 pitchers (antkay, camsch: closes 0.72/0.62, both 0/3) on correlated ladders
  (gte5/gte6/...); the other 2 pitchers went 2/3. n_independent = 2 events.
- Odd settlement: astatc-mlb-nyy-tb-2026-10-05-sb-cedmul-gte1 settled 0.12 (not 0/1) - fractional/void settlement, 1 market.

## Verdict: LUCK, not skill
- Fills lose to the closing line at every horizon (B -2.5c, C -3.0c, D -3.7c per contract; t -3.3 to -4.7, clustered by market),
  with no reversal: the early mark-out never recovers. Expected fill P&L at the close: B -$1,842, C -$1,470, D -$1,168.
- Realised settlement +$955 to +$2,260 = +$2.1k to +$3.7k of outcome luck, concentrated in selling 25-75c 'outs' overs
  of two pitchers who left early (one correlated event per game). The small real overs bias (~2-5c) is smaller than
  the 2.5-3.7c our fills give up, so even crediting it the fills are negative EV.
