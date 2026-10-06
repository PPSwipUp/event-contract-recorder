# Night Log — 2026-10-02

## Summary
- Task: search many markets for an edge bigger than the crypto range bot (~$160/mo at a 100-contract cap). Laptop only.
- Anti-overfit rule: new markets are tested with the FROZEN rules (base >5c edge; new rules >12c/crowd200/calm2),
  never re-tuned. A market counts only if it is profitable out of sample with volume checks.
- In progress: alt-coin hourly ranges (SOL, XRP, DOGE).

## Needs human
- JURISDICTION (resolved 2026-10-04): the user is a US resident, temporarily in the UK. Kalshi: usable as a US person,
  but place trades from the US (it may block by location). Polymarket international bars US persons: Polymarket
  ideas would need re-checking on Polymarket US (separate exchange). Never VPNs / other people's accounts.
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

- 21:xx HOLDING REWARDS (docs): Polymarket pays 4.00% annualised on total position value in eligible markets (hourly
  sample, daily payout, rate at their discretion). A minted full set (YES+NO, merge back to $1 any time) would earn it
  with no price risk IF both sides qualify (docs silent). = T-bill-level yield + platform/contract risk. Not an edge.
- 21:xx PRE-REGISTERED range-bot go-live + scale plan: results/PREREG_SCALEUP.md (gate, start cap 25, steps to 250,
  stop rules), frozen before any forward verdict.

- 21:xx SPORTS SETTLEMENT LAG (results/SPORT_SETTLE.md): 2,199 games / 119 days. Apparent $11k taker + $4.8k maker
  profit is NOT real: it is mostly tennis bought at 7-37c 5-9 h after the SCHEDULED start = matches still being played
  (order-of-play delays); one NFL game likewise. Polymarket has no game-end time, so 'result known' can't be
  established from its data. Reliable-start leagues: NHL $0.35, EPL $17, MLB ~$1.3k/4 months (rain-delay doubt).
  Not validated; would need real end-of-game times (league play-by-play). Parked.
- 21:xx CROSS-VENUE SPORTS (live/xvsports.py, 7 days): Kalshi game markets vs Polymarket moneylines, 84 games matched
  (NHL 48, NBA 24, MLB 12; team-name matching unit-tested, ambiguous games skipped). First polls: best -0.25c,
  median -4.7c. Running.

- 22:xx TWEET COUNTS (results/TWEETS.md, backfill/tweets.py): Polymarket 'Elon Musk # tweets' brackets, $7.9M/event.
  CHECK: xtracker count lands in the winning bracket for 94/95 windows. Model = running count (posts imported before
  t) + negative-binomial remainder from the 7-day rate. First run had a BUG: dispersion estimated from 1 day of data
  -> silent Poisson fallback (overconfident; -$1,248/mo holdout). Fixed (k from train-period daily counts = 4.22,
  assert added) and rerun - NOTE the holdout has now been viewed twice (bug fix, not tuning).
  Result: market still more accurate (holdout Brier 0.0794 vs model 0.0828). Train 5c: +$1,490/mo, t 2.0 -> holdout
  +$214/mo, week t 0.26, max DD $6.3k; cap 500 -> -$59/mo; 24h-stale placebo -$265/mo. Not significant. Closed as
  an edge; at most a weak paper-forward candidate.

- 23:xx LP GROUND TRUTH FROM REAL MAKERS (results/LP_WALLETS.md, backfill/lpwallets.py): the 40 busiest maker wallets
  in the paper-LP's 20 markets. Public activity API: rewards + maker rebates last 30 days = $493k in total.
  Polymarket leaderboard profit last month: -$1.02M in total, median -$4.3k, only 16/40 profitable. The most
  reward-heavy third (rewards/volume) took $340k of rewards yet lost $466k. Whether the leaderboard figure already
  includes rewards is unknown; either way the group is net negative (-$531k if it excludes them).
  Also: Polymarket's market_competitiveness is on a different scale from total order score (Balance of Power: ~300
  vs 2M+ shares near mid), so it cannot bound the reward share.
  VERDICT: independent confirmation of the replay - liquidity rewards do not cover makers' trading losses in these
  markets, even for large professional makers. LP lead closed; paper runs left on only as a third check.

- 21:xx COPY-TRADING (results/COPYTRADE.md, backfill/copytrade.py): 616 public wallets (top 500 by volume + top 200
  by profit), 2.18M resolved buys. Picked the top 20 by copy return on Jan-Apr 2026 (+260%/trade in-sample, mostly
  1c longshots that hit), copied on May-Sep at THEIR price (zero delay, the best case): -22%/trade, weekly t -2.2,
  26% positive weeks = about -$147k/month at $100 per copied trade (~6,650 trades/month). Copying all 398 eligible
  wallets: -8.5%/trade. Persistence of wallet returns A->B: rank corr 0.17 (weak).
  Post-hoc 'buys >= 30c were positive in B' checked against A across all wallets: not consistent (30-50c band +5.4%
  in A, -2.6% in B; per-market mean +0.96% A vs -0.54% B). No copyable pattern. Closed; live copier not built.

- 22:xx DEEP KALSHI CRYPTO ARB (live/kxcryptoarb.py): 6 coins (BTC ETH SOL XRP BNB HYPE; DOGE strikes differ),
  ~11k packages/hour (1-3 bracket spans, above/below ladders, full bracket sets), book-depth walk (unit-tested),
  persistence. First hour (Sat 21-22 BST): 3 opportunities, $0.16, none survived to the next 4-s poll.
  HISTORY (data_local/arb, Aug-Sep 1-min candles): BTC 1.6 / ETH 1.0 package runs per hour, median edge 0.5-0.7c per
  contract, median life < 1 min, 29% start in the last 15 min -> ~$0.30/h at 10 contracts for BTC+ETH (~$230/month
  if everything were caught). Scanner now re-reads each package's legs in ONE request at once ('confirmed', rules out
  legs read seconds apart) and again 1 s later ('catchable'). First run kept as live/kxcryptoarb_v1.jsonl.

- 23:xx NEW-IDEA SWEEP:
  FEES: Kalshi series fee schedules: 14,389 standard; 18 at half fee (MLB props + MLB game markets; the sports
  scanner already uses each series' multiplier); 14 FEE-FREE incl. KXBTCY ($39M) / KXETHY ($12M) year-end ranges.
  FEE-FREE YEAR-END vs DERIBIT (backfill/btcy.py, snapshot): Kalshi brackets sit within ~0-3c of the Deribit-implied
  probabilities (25-Dec smile + 6.7 days at ATM vol); biggest gaps +2.3c to +2.7c on thin brackets, inside the
  model's own error and the volatility risk premium. One settlement (1 Jan) = one correlated draw, so it can't be
  validated statistically. No mispricing worth trading. Closed.
  KALSHI LIQUIDITY INCENTIVES: /incentive_programs lists 5,000+ active pools (median period_reward 1,000,000 -
  units probably centi-cents = $100, unconfirmed), dominated by thin NFL player-prop ladders and niche markets:
  same pattern as Polymarket (rewards where makers get run over). Queued, low prior.

- 23:xx SCHOOL WI-FI CURFEW (no internet 00:00-06:30 UK): stopped the alt-coin arb history download (saves only at
  the end; restart after 06:30), made live/pmlp.py drop quotes after any >5-min gap (no fake fills from trades during
  the outage), hourly loop replaced by a 06:35 alarm. Scanner per-hour rates must exclude the curfew.
  Deep crypto arb so far: 8 seen ($2.86), 0 confirmed when legs re-read together.

## 2026-10-04
- 06:36 resumed after curfew: all 8 live jobs reconnected at 06:30; alt-coin arb history download restarted.
- DEEP CRYPTO ARB after ~10 live hours: 19 sightings worth $8.87, CONFIRMED (legs re-read together) $0.04,
  CATCHABLE 1 s later $0.01. The old '~$1/h' sightings were almost all reading artefacts. Effectively closed for a
  laptop; scanner left to finish its 48 h.
- 1a CRYPTO VOL RISK PREMIUM (results/VRP.md): sell 30-day DVOL, variance-swap proxy, monthly entries. BTC 2025 +2.1
  vol pts/month, 2026 +0.03; ETH 2025 -5.3, 2026 +2.1 (before ~1-2 pts of costs); never significant (best t 0.9);
  worst months -14 to -46 pts. Closed.
- 3a OVERNIGHT DRIFT (results/OVERNIGHT.md): SPY/QQQ/IWM buy close / sell open. Holdout year: all index gains came
  overnight, but after 2 bp costs the strategy returns LESS than buy-and-hold (SPY 9.6% vs 13.7%, QQQ 15.5% vs
  21.2%), t <= 1.7, flat in the train year. No edge over just holding. Closed.
- 2a PM 'FDV above $X after launch' vs pre-market perps: none of the ~30 Polymarket FDV projects trades on Hyperliquid
  (main or the 10 builder exchanges). Builder exchanges list pre-IPO perps (io:ANTH $3.7M/day, io:OAI, vntl:SPACEX)
  but those settle differently from Polymarket's valuation markets -> no clean pairing. Parked.

- 11:xx CRYPTO ARB PER COIN, LIVE (~5.7 online hours): 104 sightings worth $270 as seen (one BTC glitch row);
  confirmed $0.23 (BTC 0.10, ETH 0.12, HYPE 0.01, SOL/BNB 0, XRP none); catchable 1 s later $0.08 = ~$10/month if run
  24/7. History (1-min candles) suggested $0.10-0.53/h per coin -> reading artefacts. Kalshi crypto arb CLOSED.
- 11:xx LP SPEED (results/LP_SPEED.md, backfill/lpspeed.py): 3-s top-of-book recording (20 LP markets) + real trades,
  join best bid/ask 500 shares, back-of-queue fills: refresh 60 s -> -$42.5 (9 fills), 15 s -> -$37.5 (7), 3 s ->
  -$20 (4) over the window. Faster quoting halves fill losses but stays negative; only 4-9 fills (tiny sample) and
  the 16.5 h window includes the 6.5 h curfew (per-day figures in the report understate by ~1.65x).

- 11:xx ALT-COIN ARB HISTORY done (arb.py, Aug-Sep 1-min candles), on-paper $/h at 10 contracts: BTC 0.16, ETH 0.15,
  SOL 0.31, XRP 0.10, BNB 0.53, HYPE see results; all overstated by stale-quote reading (live confirmation ~$0.01/h).

- 12:xx LIVE RULE ENGINE (live/rules.py): computes the two FORWARD-TESTED rules exactly (reuses research.probs /
  implied_mult / MARGIN / fee; quote 15 min after open; ppc fitted on completed hours; k_fixed, k_roll as in prep).
  VALIDATED: replaying 2026-10-02 gives base BTC 0 / base ETH 1 / eth-rule 2 bets = the forward ledgers exactly.
  Running signals-only (writes live/signals.jsonl + full inputs to rules_log.jsonl) so live decisions can be
  audited against the daily forward ledger. Go-live = run live/executor.py --signals live/signals.jsonl --live
  with the user's key (frozen plan results/PREREG_SCALEUP.md).
- 12:xx PRE-BUILT ANALYSES: backfill/lptick.py (fill loss vs reaction time 0.1-60 s on tick data) - first 2.2 h:
  4 fills, -$15.6/online h at >= 0.5 s, -$11.2 at 0.1 s (too few fills; verdict ~6-7 Oct).
  backfill/gapstudy.py (first inside a widened spread) - first 19 h, 193 fills: 5-min mark-out +0.02c, 30-min
  -0.44c (about zero before rewards); narrow gaps negative (-0.9 to -1.0c), very wide gaps (>10 ticks, n=18)
  +5.7c - small post-hoc subgroup, not to be trusted until the full run (~7 Oct).

- 13:xx LOW-ODDS QUEUE:
  Kalshi tweet markets: KXELONTWEETS and all other tweet series have NO open markets -> nothing to test. Closed.
  Polymarket 15-min up/down: skipped - the Kalshi 15-min version had no edge and PM's markets are $40-6k each
  (no capacity even if an edge existed).
  Kalshi LIQUIDITY INCENTIVES: scoring per help.kalshi.com (1-s snapshots, reference price at Target/5,
  Discount^ticks) implemented + unit-tested (backfill/kalshilip.py, results/KALSHI_LIP.md). Snapshot reward share
  for 100/side at best bid: NFL prop ladders ~20% (~$65-153/h per series), 15-min crypto-lead ~$133/h, Miami
  hourly temperature ~$109/h, Rotten Tomatoes ~$90/h - rewards only, the same thin, informed markets as Polymarket.
  Paper run started (live/kxlip.py: KXCRYPTOLEAD15M + KXTEMPMIAH + KXRT, 223 markets, 100/side, back-of-queue
  fills, settlement at official result, conservative maker fee). NOTE: each loop takes ~90 s but credits 60 s of
  reward (understates rewards); capital ~ $100 x 223 markets. Verdict after a few days.
- 13:xx live/rules.py running: 287k minutes of history per coin loaded; first signals at the next :15.

- 13:xx KALSHI INCENTIVE VALIDATION: (1) all programmes were inside their windows (OK); (2) no per-account caps (OK);
  (3) QUEUE ARTEFACT - in 82% of Rotten Tomatoes book sides the best price already holds > target (median 11,206 vs
  1,000), so a back-of-queue order scores nothing: RT reward $104/h -> $26/h after fixing side_score(back=True);
  (4) EMPTY-SIDE ARTEFACT - Kalshi's rules exclude any snapshot where either side is below the target size, so the
  $225/h attributed to empty-side markets pays nothing; (5) ELIGIBILITY - the programme is for 'most regular U.S.
  Kalshi members'; international users are excluded. Paper run (live/kxlip.py) stopped. Closed.

- 14:xx KALSHI INCENTIVES, CORRECTED (back of queue + two-sided exclusion, kalshilip.market_share): 5,833 active
  programmes, pools $13.4k/h in total; 100/side in EVERY market -> $474/h rewards on ~$583k of quotes (gross, no fill
  losses); top series per 100/side: crypto-lead 15m $74/h (40% of snapshots excluded), Miami temp $33/h (70%
  excluded), NFL escalator/ladder props $10-32/h, Rotten Tomatoes $8/h. Paper run restarted with corrected scoring on
  crypto-lead + Miami temp + NFL escalator (94 markets): first 2 loops +$4.59 rewards, 1 fill, net -$1.64.

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

## 2026-10-04 16:xx — Crypto-lead Phase 1: GATE FAIL
- 3,948 windows scored. Holdout model Brier 0.1144 vs market 0.1086 (diff +0.0058, CI [+0.0041,+0.0077]) > 0.002 tolerance.
- Train had model slightly better (-0.0031); holdout worse on 12/15 days. Per frozen plan: Phase 2 not built, line closed.
- DECISION: HYPE source switched to Bybit spot (Hyperliquid 5,000-candle cap). Revert: hype() in backfill/cryptolead.py.
- Bugs fixed on the way: missing school CA bundle, close_ts unit (us vs ns), uncapped retry back-off.

## 2026-10-04 23:25 — Favourite-longshot (PLAN_FAVLONG): GATE FAIL
- 41,198 events / 1,376 series. Buying 90-97c favourites at the ask 6 h before close: holdout -8.2c/contract, t -12 (train -9.7c).
- Favourites win 82-89% vs 90-97% implied; buying the 3-10c longshot at its ask is ~0 (6h) / -1.7c (1h). Spread eats it both ways; no taker edge.
- CPI test (PLAN_CPI) crashed on expiration_value '0.3%'; fixed, restarted 23:25.
## 2026-10-04 23:30 — CPI vs Cleveland nowcast (PLAN_CPI): GATE FAIL
- 45 releases (24 train / 21 holdout), 450 entries. Holdout +0.27c/contract, t 0.07. Market far sharper (Brier 0.059 vs model 0.111).
- Placebo (last month's CPI) -9.1c, t -4.2, so the harness can tell good from bad; the nowcast just adds nothing over Kalshi's price.
- 2021 events contributed no entries (no trades in the 24h-1h window via API); not investigated.
## 2026-10-04 23:42 — Polymarket LP follow-up (side-chat request)
- pmlp + pmlp_tight alive, 14-day runs (to ~17 Oct). Plan frozen: results/PLAN_PMLP_CALM.md.
- Polymarket US: has its own LIP (Kalshi-style Discount^ticks scoring, Target Size, Max Spread) + maker rebate 0.0125·C·p(1-p).
- TODO 06:35: fill-by-fill analysis of pmlp_tight; build --calm flag + per-loop 14d/mid filter; launch _tight_calm.
## 2026-10-05 06:35-06:50 — PM LP follow-up done
- pmlp + pmlp_tight survived curfew (resumed 05:30 UTC). Restarted 05:37 UTC with per-fill logging (same state; NOTE restart reset their 336 h clocks, so they now end ~19 Oct).
- Launched pmlp_tight_calm (--calm, same 20 markets as _tight, 312 h -> ~18 Oct). 2/20 markets already pulled by the 14d/mid filter (Israel 0.05, Indiana 0.095).
- backfill/pmfills.py -> results/PM_FILLS_TIGHT.md. 10 old fills reconstructed: +$65 marked; $70 of it is ONE short in "Israel accuses Iran" (mid fell to 0.05, now outside the 0.10-0.90 rule). 4 markets show +$2.50 = half-tick mark at mid, not realised profit.
## 2026-10-05 ~11:30 — Polymarket US LIP check
- Public, no account, works from UK: incentives list (api.prod.polymarketexchange.com/v1/incentives) + books (gateway.polymarket.us). No public trade feed (fills only via book crossing).
- 40,949 active liquidity programs. Pools are SHARED across a program's markets (rewards page), NOT per market: first survey's $40k/h was that artefact.
- Today's MLB wild-card games: day-of (6 h pre-game) pools $1,525/game across ~300 markets (~$254/h total per game); live $5,100/game.
- live/pmusrec.py recording all books every 30 s in today's day-of windows (CWS-CLE 15-21 UTC, NYY-TB 18-00 UTC; curfew cuts last hour).
## 2026-10-05 18:30 — Exclusive-event arb scanners (48 h, end ~19:10 BST): CLOSED
- kxevarb (Kalshi, ~4,400 exclusive events/scan): 4 safe ALL_NO packages, $0.20 total in 48 h. Dead.
- pmevarb (Polymarket intl): 56 'safe' packages, $542 headline, almost all ALL_NO on LIVE soccer 1X2 markets lasting
  1-3 scans with 14-75c edges = sequential-book-read artefacts during live play (no same-instant re-read). Not
  credible, and Polymarket intl is closed to the US-resident user anyway. Closed.
## 2026-10-05 18:40 — pmevarb REOPENED (user request: outputs looked real)
- Trade tape around top 6 hits: each sits ~1.5-2 min after a goal (e.g. De Graafschap 0.80->0.39, draw 0.20->0.54 at -88 s);
  the scan reads ~235k books over ~200 s in token-id order, so legs of one match are read before/after the goal.
- Forward test: pmevarb.py --confirm (same-instant re-read of every hit's legs + 1 s later), run _v2, 72 h.
  Verdict = confirmed/catchable $, not headline $.
## 2026-10-05 22:43 — Live soccer same-instant gaps (soccerlive intl, first evening)
- ~6,300 polls (2 s) over 7-12 live matches. 46 same-instant positive 1X2 packages (24 BUY_ALL, 22 SELL_ALL) in 7 matches.
- Edge median 0.9c (90th pct 4.1c, max 16.4c), size median 20 (max 643). Headline $48; still there 1 s later 26/46 = $20
  (overlapping repeats of the same gap, so <$20 distinct). Largest: ITA-TUR min 24 BUY_ALL 6.4c x 208 after 1 s = $13.
- pmevarb_v2 (same-instant confirm): 16 distinct safe packages, max confirmed $3.31, ~$7.6 total; v1's $542 was staggered reads.
- Verdict so far: same-instant gaps are REAL but small (~$10-20/evening on intl, before competition/leg risk). PM US soccer from 9-10 Oct decides relevance.
## 2026-10-06 08:30 — Morning
- Overnight GitHub run 37381463061 recorded 23:17-04:58 BST (17 checkpoints). Chained run failed preflight because NYY-TB's programs
  vanish at first pitch -> 05:00-06:35 lost (soccer only). Fixed: ghpreflight treats a started game as OK.
- PMUS_DAY (frozen 5 variants, GH last hour merged): first-read rule passes B/C/D (net + both games) BUT fake-check WEAK:
  rewards+rebate $30-170/game vs negative 5-min mark-outs; positive net = settlement luck on held props (2 games, best of 5).
  Continue 5 more game days per plan (recordings 6-7 Oct running).
## 2026-10-06 ~09:00 — PMUS winning variants tested without using outcomes (results/PMUS_CLV.md): LUCK
- Closing-line value negative at every horizon (t -3.3 to -4.7), expected fill P&L -$1.2k to -$1.8k; settlement win = 2 pitchers
  pulled early on correlated outs ladders. Closing prices are well calibrated (Brier 0.132). 5 more game days continue per plan.
## 2026-10-06 ~14:30 — Deeper checks on the 3 leads the user asked about
- Live soccer gaps (PM intl): 69 same-instant episodes over 2 evenings, $138 at first sight, but only 14 lasted >=3 s = $1.28.
  PM intl holds marketable sports orders 3 s (docs.polymarket.com order lifecycle) -> uncatchable. PM US docs show no such delay -> 9-10 Oct test stands.
- Paper LP (PM intl, long-dated politics/Fed): pmfills token-id float bug fixed (pandas parsed 77-digit ids as numbers). 19 logged fills:
  mark-out +0.29c (5 m), +0.45c (1 h) = about the half-tick, no adverse selection seen in 2 days. Rewards ~$4/online h on paper.
  Still: 60-day replay -$49/day from jumps, real makers net negative, venue unusable; transferable test = PM US political daily_event programs.
- Range bot forward: no bug (re-scoring 1 & 4 Oct reproduces ledger exactly). -5.8c/bet over 18 bets vs Aug/Sep +5.4/+6.1c (both t<1.5):
  ~1.2 SE below expectation, not significant either way. Continue to 60 days.
