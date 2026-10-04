# Crypto-lead 15m: fair-value model vs market mid (Phase 1 of PLAN_CRYPTOLEAD.md)

Windows scored: 3948 ({'holdout': 1380, 'train': 2568})

|                 |     n |   model_brier |   market_brier |   median_spread_c |
|:----------------|------:|--------------:|---------------:|------------------:|
| ('holdout', 3)  |  6889 |        0.1376 |         0.1344 |                 9 |
| ('holdout', 7)  |  6686 |        0.1157 |         0.1102 |                 8 |
| ('holdout', 11) |  6276 |        0.0874 |         0.0785 |                 7 |
| ('train', 3)    | 12262 |        0.1407 |         0.1407 |                 9 |
| ('train', 7)    | 11725 |        0.1202 |         0.1176 |                 8 |
| ('train', 11)   | 11271 |        0.092  |         0.089  |                 7 |

Holdout overall: model Brier 0.1144 vs market 0.1086 -> GATE FAIL (needs model <= market + 0.002)
## Robustness (window-level bootstrap, 2,000 resamples; diff = model Brier - market Brier)
- train  : 2,568 windows, diff -0.0031, 95% CI [-0.0054, -0.0008]  (model slightly better before 09-20)
- holdout: 1,380 windows, diff +0.0058, 95% CI [+0.0041, +0.0077]  (CI excludes the +0.002 tolerance)
- holdout days where the model beat the market: 3 of 15
- The market got sharper after 09-20 (or the 3-day bootstrap model stopped fitting); either way it is worse than
  the crowd on the pre-registered holdout. Gap widens late in the window (minute 11: +0.009), where the market
  sees second-level prices and the CF 60-s TWAP mechanics that a 1-min model does not.

## Deviations / fixes (all made before any valid result was seen)
- HYPE prices from Bybit spot HYPEUSDT instead of Hyperliquid: Hyperliquid candleSnapshot serves only the latest
  5,000 1-min candles (3.5 days), which silently dropped 92% of windows in a first run (327 windows, also FAIL).
- Fixed close_ts unit bug (pandas datetime64[us] -> wrong epoch) and capped retry back-off.

## Verdict: GATE FAIL -> per PLAN_CRYPTOLEAD.md, Phase 2 (fair-value-guarded paper MM) is NOT built. Line closed.
