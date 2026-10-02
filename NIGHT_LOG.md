# Night Log — 2026-10-02

## Summary
- Task: search many markets for an edge bigger than the crypto range bot (~$160/mo at a 100-contract cap). Laptop only.
- Anti-overfit rule: new markets are tested with the FROZEN rules (base >5c edge; new rules >12c/crowd200/calm2),
  never re-tuned. A market counts only if it is profitable out of sample with volume checks.
- In progress: alt-coin hourly ranges (SOL, XRP, DOGE).

## Needs human
- Market-making edge passed backtest fake-checks (~$1-3.5k/mo, Sharpe ~4-5 on 2026 holdout). It is NOT proven live:
  a 48 h read-only paper run is going (live/papermaker.py, laptop must stay awake). Do not trade on it yet.

## Timeline
- 10:xx survey: Kalshi alt-coin hourly ranges exist only since Jul 2026 and are thin (median contracts/event:
  SOL 668, XRP 353, HYPE 237, DOGE 102, BNB 91 vs BTC 30,827, ETH 4,565). Daily SHIB range since 2024.

- 11:xx started (A) alt-coin range collection (SOL/XRP/DOGE, Jun-Sep 2026) and (B) KXBTC15M 15-min up/down
  test (Aug train / Sep holdout, 1-min candles, spot 1 min stale). KXBTC15M trades ~1.7M contracts per 15 min,
  spread 0.1c -> capacity is no issue if an edge exists.
- 11:xx (C) Polymarket hourly BTC up/down: 2026 markets have taker fees enabled and ~$25k volume/hour -> lower
  priority than Kalshi 15m; only test if (B) shows an edge.

- 11:xx (D) FX hourly series (KXEURUSDAH etc.): no settled markets. Gold/silver/WTI hourly = above/below type
  (no edge on crypto above/below), thin (gold ~2.7k, WTI ~150 contracts/event). Parked.

- 12:xx (A) collected: SOL 9.9k trades, XRP 7.9k trades (Jun-Sep 2026); DOGE 0 trades (collector found no events
  near the money - not chased, market too thin anyway). Scoring with frozen rules.
- 12:xx (B) first run crashed (some markets lack floor_strike) - fixed to skip them, rerunning. Data re-fetched.

- 13:xx (A) RESULT: SOL base -$59/mo, new rules ~$0-3/mo; XRP base +$55/mo (Sharpe 1.6, 4 months only), new rules
  $0-16/mo. Combined at best ~$50-70/mo, below the BTC/ETH bot. Thin markets. Line A closed (results/ALT_RANGES.md).

- 14:xx user: continue on other markets. Started (B2) KXETH15M test, and (E) monthly BTC max/min touch markets
  (KXBTCMAXMON / KXBTCMINMON, Jan-Sep 2026, ~1-2M contracts per month each). Model = reflection touch prob,
  k/z frozen from pre-2026 hourly data; margin on Jan-Apr, holdout May-Sep. Only ~9 months -> weak evidence by month.

- 14:xx (E) RESULT: monthly max/min - market slightly more accurate than model (Brier 0.0764 vs 0.0784). Margin 12c
  picked on Jan-Apr (+$147/mo, t 1.65, only 2/4 months +) -> holdout May-Sep -$47/mo (cap 100), -$301/mo (cap 500).
  No edge. Line E closed (results/TOUCH.md).

- 15:xx (B) RESULT KXBTC15M: market more accurate (Brier 0.1496 vs model 0.1541). Aug: every margin loses
  (8c: -$2.2k, t -1.6); Sep holdout +$2.2k but t 1.29 and opposite sign to Aug -> noise. Spot is SAME-INSTANT as the
  quote (docstring corrected - it said 1 min stale), so even zero-latency at minute resolution gives no reliable edge.
  Placebo 5 min stale: -$10.7k (market follows spot fast). Line B (BTC) closed; ETH run still going.

- 15:xx (F) started market-making test (maker.py): sell to takers who overpay per the frozen model, on all
  database trades (BTC+ETH ranges, 10-20 min after open). 25%/50% fill of each trade, maker fee charged, margin on
  2024-25, holdout 2026. Placebo: join the taker instead.

- 16:xx (F) RESULT (unverified, too good): holdout 2026 $1.0k-2.8k/mo, Sharpe ~4.7-4.9, 8/9 months, margin 8c chosen
  on 2024-25 (train 14/14 months). Placebo join-taker -8.8c. Running fake-checks (makercheck.py): no-model, random,
  5-min stale spot, fill 10%, breakdowns. DO NOT trust until these pass.

- 17:xx (F) FAKE-CHECKS (results/MAKER_CHECKS.md): model 4.5c/contract t 4.05 vs no-model 0.4c (t 1.75), random
  0.6c; 5-min-stale spot 2.8c (t 4.06, edge mostly vol pricing not speed); fill 10% still $530/mo t 3.97; both
  coins +, all trade sizes +, 8/9 months +. Queue-first variant (post 1c better, full fill, max 25): $1,740/mo t 3.9;
  2c better: $1,341/mo. PASSES backtest checks. Real-world risk = competing makers / queue -> needs live paper test.
- 17:xx started live/papermaker.py (48 h, read-only): quotes 1c inside the live book when model edge > maker fee+8c,
  fills only from real taker trades >1 s after quote. Score with live/paperscore.py.

- 17:xx (B) KXETH15M RESULT: no edge (Aug all margins lose; Sep -$1.9k). Line B closed.
- 17:xx running maker OOS check on SOL/XRP ranges (frozen 8c margin).

## Decisions
- DECISION: maker fills assumed = 25% (and 50%) of each real taker trade at that price; true queue position is
  unknown. Revert: change FILL in maker.py.
- DECISION: "edge larger in profits" = more $/month after volume caps than the existing bot. Revert: n/a.
- DECISION: test candidates in order of closeness to the proven edge: (A) alt-coin hourly ranges, (B) 15-min crypto
  up/down (latency / stale price), (C) Polymarket crypto up/down, (D) FX hourly ranges. Stop a line when it fails.

## Verification
(pending)

## Left to do
1. A: collect SOL/XRP/DOGE range trades Jul-Sep 2026, run frozen rules.
2. B: 15-min up/down with 1-min candles + Coinbase.
3. C: Polymarket crypto up/down history.
4. D: FX hourly ranges (Massive forex if free).
