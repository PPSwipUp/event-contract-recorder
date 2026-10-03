# Night Log — 2026-10-02

## Summary
- Task: search many markets for an edge bigger than the crypto range bot (~$160/mo at a 100-contract cap). Laptop only.
- Anti-overfit rule: new markets are tested with the FROZEN rules (base >5c edge; new rules >12c/crowd200/calm2),
  never re-tuned. A market counts only if it is profitable out of sample with volume checks.
- In progress: alt-coin hourly ranges (SOL, XRP, DOGE).

## Needs human
- live/watcher.py now refuses to signal when the vol forecast has collapsed (frozen price feed). Review the
  one-line guard (min_sig) before relying on the watcher.
- Market-making edge FAILED the realistic simulation (all scenarios lose; root cause = print-price fill assumption in
  maker.py). Do NOT trade it. Paper run (live/papermaker.py) also negative so far.

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

- 18:xx maker OOS on SOL/XRP (frozen 8c): model fills +6.3c / +4.8c per contract (no-model +1.7c / -0.4c), but
  small $ ($276 / $198 over ~4 months) and weak t (1.25 / 0.86). Same sign = mild support. results/MAKER_ALT.md.
- 18:xx BTC/ETH split of the $1,740/mo (1c better, full fill, max 25): BTC $1,505/mo t 3.7 (May $5.5k; ex-May ~$1.0k),
  ETH $235/mo t 1.3. Paper run: 7 ETH fills in first 20 min, all selling YES into rising prices; scoring at 16:10 UTC.

- 18:xx user asked to scale #1. Started full-hour trade collection (fullhour.py): KXBTC 2026 every 4th hour, 10 mkts;
  KXBTCD (above/below) 2026 every 8th hour, 6 mkts. Will run maker.py logic with the FROZEN 8c margin (pure OOS).

- 19:xx KXBTCD maker interim (Jan-Mar, every 8th hour): ~0 at 25% fill, -1.1c at 1c-better -> no edge overall.
  By minute: 10-30 min +2.4..+3.7c, 40-60 min -2.3..-3.1c (informed flow near settlement).
- 19:xx user asked for a realistic market-impact simulator. Built simmaker.py (event-driven replay of real tape +
  1-min book, our orders inserted, latency, queue/competition prob, caps, maker fees, settlement). Data: simdata.py
  (Aug-Sep, every 2nd hour, BTC+ETH ranges) collecting.
- DECISION (pre-registered before sim data seen): secondary variant "quote only minutes 0-35", from KXBTCD Jan-Mar.

- 19:xx paused full-hour KXBTC collection after Apr (resumable: rerun same fullhour.py command) to give simdata the
  Kalshi rate limit. Adversarial review workflow on simmaker.py running (5 lenses + 2 refuters each).

- 20:xx adversarial review of simmaker.py (43 agents): 15 confirmed findings (results/SIM_MAKER_REVIEW.txt). Fixed:
  tz crash; fills when OTHER traders' orders cross our stale quote (taker prints through + next-minute book cross,
  CROSS_FILL 0.5/1.0); pick-off of whole order when prints go >=3c through; per clock hour (BTC+ETH same close counted
  once); capital by close; days from data; max_dd from $0; day_t on all days; ex-best-day / ex-28Sep / top-5-hour
  share / weekly-bootstrap CI; paired same-day tests vs no-model and placebo; non-independence note; UTC-hour table.
  Sampling bias (odd UTC hours only) -> simdata --offset 1 --even-weeks-only pass chained after current download.
  Synthetic unit test passes (latency gate, first-in-queue fill, next-minute cross pick-off, fee rounding).

- 20:xx SIM RESULT (partial, Aug 1-Sep 20, 598 clock hours): market making LOSES in every scenario: base -3.9c/contract,
  -$18.6k/mo if every hour, day t -11.7; no-model -1.6c; placebo -3.2c; model worse than no-model (paired t -4.7);
  every minute bucket negative incl. 10-20 (-3.1c). 0-35 min variant -2.8c. Suspect: 60-s refresh -> stale pick-offs.
  Running simdiag.py to split losses by fill rule and compare with the old naive fill rule.

- 21:xx LOSS DECOMPOSITION (simdiag): even the NAIVE fill rule (only same-side takers, print-sized, no pick-offs)
  loses -4.9c/contract (all minutes) and -4.1c (min 10-20) in the sim, vs +4.5c in maker.py on the same period.
  Root cause: maker.py filled us at the taker's PRINT price; the overpaying prints are mostly sweeps through thin
  books, and you only get that price if you were already resting at that exact level. Quoting at the touch (or
  joining at model+8c) captures the adverse part without the windfall. Paper run agrees: -$14.37 after 2 hours.
  VERDICT: market-making lead is an artifact -> DEAD (no-model quoting also loses -1.6c, so books are defended).
  Full-data sim chained (data_local/final_sim.sh) for the record.

- 10-03 laptop rebooted overnight: /tmp venv gone -> persistent .venv in repo. Full sim (1,081 hours, all UTC hours)
  confirmed market making loses (-3.5c/contract); paper run final -$69.38 (174 fills, hour t -3.25). Lead closed.
- 10-03 scout workflow failed (Claude spend limit). Scouted inline: WEATHER daily-high markets are deep (NY ~182k,
  LA ~580k, MIA ~159k contracts/day, history to 2021) and free point-in-time data exists (Open-Meteo previous-runs
  forecasts, Mesonet ASOS obs, NWS CLI truth). Added dohfix.py (only bypasses DNS when EE block IP seen).
  Started weatherdata.py (6 cities, 2025-01..2026-09, trades in 10-11 and 14-15 local windows).

- 10-03 WEATHER RESULT: market far more accurate (Brier 2026 2pm 0.078 vs model 0.162); every 2025 config loses;
  chosen (5c, 10am) loses -$1,032/mo on 2026, all 6 cities negative. Closed (results/WEATHER.md).
  Only alive lead: original crypto range taker bot (forward tests, ~early Dec).

## 2026-10-03 (user away): nowcast markets, Kalshi vs Polymarket, then range bot
- 13:xx nowcast survey: by volume AAA gas daily (KXAAAGASD ~300-400k contracts/day) and weekly (KXAAAGASW ~1M/wk)
  dwarf TSA weekly (~20k/wk) and jobless claims (~10k/wk). Settlement values (expiration_value) give AAA daily truth
  from 2026-03-26.
- 13:xx GAS DAILY (results/GAS.md): linear nowcast (last 3 changes + UGA returns), rolling refit. Every Apr-Jun config
  loses; holdout Jul-Oct -$663/mo, no better than zero-change placebo. Market much sharper in the evening window
  (Brier 0.067 vs model 0.153). Closed.
- 13:xx GAS WEEKLY (results/GAS_WEEKLY.md): every Apr-Jun config loses; holdout +$80/mo but zero-change placebo
  +$223/mo -> noise. Closed.
- 14:xx TSA WEEKLY (results/TSA.md): known days + last-year x recent ratio. Train 2023-25 +$14/mo t 1.1; holdout 2026
  -$17/mo. Market more accurate. Closed (tiny capacity anyway).
- DECISION: jobless claims not tested: the only good predictor is economists' consensus (no free point-in-time
  history) and capacity ~10k contracts/week. Revert: write a claims test if a consensus source turns up.

- 14:xx KALSHI vs POLYMARKET (history, backfill/xvenuedata.py): same contract = PM "BTC/ETH above $K on <date>"
  (Binance 1-min close at noon ET) vs Kalshi KXBTCD/KXETHD noon hourly "above K-0.01". 61 days x 2 assets, last
  hour before noon. Settlement agreed 1181/1182 markets. PM minute price vs Kalshi mid: equally accurate (Brier
  0.129 vs 0.131). Lead-lag (trade Kalshi at next-minute ask when PM differs by 3-12c): loses train and test.
  Apparent "arbs" in 28% of minutes = PM history prices are not quotes (stale/mid) -> can't judge arbs from history.
- 14:xx started live/xvlive.py: polls both venues' real order books every 5 s, 11:00-12:00 ET daily for 10 days,
  logs best locked package per strike (PM YES + Kalshi NO, PM NO + Kalshi YES) with sizes and both fees to
  live/xvlive.jsonl. caffeinate -i for 10 h keeps today's run alive.
- 14:xx started (F) Polymarket weekly/monthly "what price will BTC/ETH hit" (PM volume $40-170M/month, far bigger
  than Kalshi) with the FROZEN touch model (k, z from data before any of these markets).
- 14:xx started (G) range-bot upgrade idea: Deribit implied vol index (DVOL) as an extra input to the next-hour vol
  forecast (backfill/dvol.py; fit 2025, score 2026).
- DECISION: Polymarket taker fee taken as 0.07*p*(1-p) per share (the event's feeSchedule says rate 0.07, exponent
  1; exact formula unverified, this is the conservative reading). Revert: change pm_fee/fee_c in xvlive.py/pmtouch.py.

- 14:xx (G) DVOL RESULT (results/DVOL.md): adds nothing to the next-hour vol forecast out of sample (BTC log-rv MSE
  0.1175 -> 0.1174, ETH worse). Closed. Side finding: a frozen Coinbase feed (2026-05-08 05-07 UTC, zero-move hours)
  collapses the ppc forecast ~1000x -> any live bot would see fake huge edges. Added a guard to live/watcher.py: no
  signals while next-hour vol < 0.2 x its median (backtests unaffected: no bets came from those hours).
- 14:xx (F) Polymarket trade API caps offset at 10,000; rewrote the pager to walk back in time with `end`. Re-downloading.

- 15:xx (F) PM TOUCH RESULT (results/PM_TOUCH.md): 2.6M taker trades, 2,394 markets (Jul 2025-Sep 2026). Market
  slightly more accurate than the frozen model in 2026 (Brier 0.0725 vs 0.0762 BTC). Margin 12c picked on 2025 (+$39/mo,
  t 0.25) -> 2026 holdout -$368/mo, week t -2.0. Extra pre-registered check, longshot bias (buy NO when YES <= 3-15c):
  loses in train and holdout after the fee. Closed.

- 15:xx (H) PM DAILY ABOVE-$K AT NOON (results/PM_ABOVE.md): 8.4k markets, 77k entries (Oct 2025-Oct 2026). Frozen
  vol model is exactly as accurate as the traded price (Brier 0.0879 vs 0.0876 BTC). Margin 8c picked on Oct-Jan
  (-$217/mo already) -> holdout -$166/mo. Closed. The crowd on these longer-horizon contracts is efficient.

- 15:xx (I) PM DAILY PRICE RANGES (results/PM_RANGE.md): the range bot's idea on Polymarket's daily noon ranges
  (366 BTC events, ~$650k each). Market slightly more accurate than the model in both halves. Margin 12c picked on
  Sep-Jan (+$55/mo, t 0.54) -> holdout -$166/mo, t -2.2, 1/9 months positive. Closed.

- 16:xx LIVE CROSS-VENUE (day 1, first 35 min): 1,236 package quotes across 5 matched strikes, best locked package
  -0.5c after fees, zero positive. Books on the two venues are kept in line. Recorder keeps running 10 days.
- 16:xx EXECUTION BOT (lead #1, ships OFF): live/executor.py follows watcher signals, sends ONE immediate-or-cancel
  limit order per signal via Kalshi's V2 endpoint (/portfolio/events/orders; side bid=YES, ask=NO, price on the YES
  scale). Limits: 100 contracts/order, 3 orders/event, $150/day at risk (persisted), signals >2 s old ignored, no
  repeat per market/side, kill switch live/STOP. Dry-run by default; --live needs the user's key. Dry-run test on
  synthetic signals: all limits behaved (stale, duplicate, budget cut 9 contracts, kill switch, NO->YES price).
- 16:xx POLYMARKET MAKER INCOME: docs confirm crypto taker fee = 0.07*p*(1-p) per share (our assumption was right),
  maker rebate = 20% of taker fees (fills only), and LIQUIDITY REWARDS = daily per-market pools paid for resting
  quotes within v cents of mid, scored ((v-s)/v)^2 x size each minute. 19,280 rewarded markets, ~$176k/day of pools.
  Snapshot scan (backfill/pmrewards.py): 500 shares/side in the top 20 markets ~ $50/day (too good -> needs checks).
- 16:xx PAPER LP started: live/pmlp.py, 20 long-dated markets (>14 days to end, mid 0.10-0.90), 200 shares/side at
  mid +/- max(tick, v/3), reward share vs real book each minute, PESSIMISTIC fills (any taker print at/through our
  quote fills us fully at our price), inventory capped 2x, P&L = rewards + mark-to-market. Log live/pmlp.jsonl.
- DECISION: paper-LP market filter excludes anything ending within 14 days (sports games, short crypto) because
  resolution jumps are where liquidity providers get run over. Revert: change horizon in pmlp.choose().

- 16:xx PAPER LP variant 2 started: one tick from mid, 500 shares/side (live/pmlp_tight.jsonl), same 20 markets.
  Snapshot sensitivity: 200 sh @ v/3 ~ $30/day; 500 sh @ 1 tick ~ $178/day (before fill losses).
- 16:xx CAVEAT: Polymarket's published market_competitiveness does not match my book-snapshot competitor score
  (corr 0.08, different scale; 8,177 markets in that feed, $56k/day). The paper reward accrual is an ESTIMATE of
  the scoring; true earnings can only be confirmed with a real (small) account. Treat paper rewards as an upper bound.

- 18:xx LP VALIDATION (results/PM_LP_REPLAY.md, backfill/pmlpreplay.py): 60-day replay of the paper LP's quoting on
  its 20 markets with real taker trades and 1-min midpoints, tick-correct quotes, two queue bounds.
  Flaws found in the paper LP: (1) quotes were off the tick grid (mid of a 1c spread is a half-cent), (2) fills
  assumed front of queue although 20k-2M shares sit at the touch in the big markets. Book mirroring and the
  size-adjusted midpoint were fine.
  RESULT per active day (rewards = today's share, assumed constant):
    wide (v/3, 200/side):  back queue -$21/day (t -2.1), front -$20/day
    touch (500/side):      back queue -$88/day (t -2.7, max DD $5.5k); front +$306/day = impossible queue position
  Losses concentrate in new, thin, news-driven markets (data-centre moratoriums, Cornell 7, Israel/Iran) where
  price trends and inventory piles up; liquid markets (Senate, Balance of Power, Fed) roughly break even but their
  reward share is pennies (huge competing depth). Rewards are big exactly where makers get run over.
  VERDICT: as designed, liquidity rewards do not beat fill losses. Paper runs restarted with realistic rules (tick
  grid, back-of-queue fills); old logs kept as live/pmlp*_v1_offgrid.jsonl.

- 18:xx LADDER AT CREATION (results/PM_LADDER.md): +/-5 levels x 100 shares posted at each market's first price,
  front of queue until each level's first fill, back afterwards. 20 markets (13 listed 2-4 days ago). Fill P&L
  -$400/day vs rewards (upper bound) +$63/day -> net -$336/day; 17/20 markets lose. Ending inventory is one-sided
  (price runs through the ladder and fills every level on the way). Front-of-queue fills = 156 of 574: priority is
  used up fast. Closed. (The new_listing flag in that report is unreliable; the 2-4 day markets ARE new listings.)
- 18:xx started live/pmgap.py: top-of-book every 3 s on 40 markets for 4 days, to test 'be first inside a
  freshly widened spread'. 71% of snapshots 1-tick spread, ~10% 2-tick.

- 19:xx SETTLEMENT LAG (results/SETTLE.md, backfill/settle.py): PM daily BTC/ETH noon markets keep trading ~2 h after
  the Binance candle fixes the result. 6,248 markets, 376 days. CHECK: Binance-implied result = PM result in
  6,248/6,248 (no settlement risk seen). Taker (buy the winner after 12:02): $13.3k over the year, but $10k is ONE
  event (ETH 2026-04-20, a whale sold the winner at 59-83c 25 min after noon) - windfalls, not a stream; Sep 2026 $0.
  Maker (rest a bid on the winner): $18.2k/yr, 81% of it at 99.9c (0.1c/share, behind existing queues); by month
  falling from $3.6k (Nov 2025) to $55-186 (Jul-Sep 2026) -> competed away. Real, verified, but now ~$0-5/day.
  Possible follow-up: same structure in sports/other categories (bigger volume, own result sources).

- 19:xx INTERNAL ARBITRAGE, BOTH VENUES (live/kxevarb.py, live/pmevarb.py; read-only, 48 h runs):
  Kalshi: every open mutually exclusive event (4,825 events, 38k markets). Safe ALL_NO packages: 3 = $0.17.
  ALL_YES 'hits' ($3.7k nominal) are all non-exhaustive sets (e.g. next Pope: someone unlisted can win) -> not arbs.
  Earlier crypto range-vs-above/below scanner: 38 packages in 7 h = $8 (~$1.2/h), confirms the old estimate.
  Polymarket: 14k events / 232k books. First run reported $3.1k of 'safe' ladder arbs -> VALIDATION found two scanner
  bugs ((LOW) price markets treated as upward ladders; '$2B' parsed as $2). Fixed + unit-tested: 3 safe ladders = $0.90.
  ALL_YES hits checked by hand: missing outcomes (a football match with the away-win market closed, candidate lists
  without 'Other'). A few two-way races (Hochul v Blakeman in Nassau, D v R white-vote winner) are near-arbs at 1-4c
  with small third-outcome risk and a month of capital lock-up: ~$5 each. Verdict: both venues keep exclusive sets
  and ladders tight; scanners keep running for rare transients. Buggy first log kept as live/pmevarb_v1_buggy.jsonl.

- 20:xx PPC JUMP TEST (results/PM_JUMP.md): 129 long-dated rewarded markets, 6 months hourly, test = last 30%.
  Jump (next-hour move >= 3c) AUC: ppc 0.751, last-hour 0.750, past-24h mean 0.853 -> PPC LOSES to the simple
  placebo; not wired in. (First run crashed: prices-history allows <= 15 days per request; fixed.)
- 20:xx LP + CALM FILTER (pre-registered: no quotes while past-24h mean hourly move >= 0.00958, frozen from the
  first 70% of the jump data): halves losses but still negative - wide -$10/day (t -1.7), touch -$49/day (t -2.7).
  Polymarket liquidity-rewards LP: CLOSED unless the realistic paper runs disagree.

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
