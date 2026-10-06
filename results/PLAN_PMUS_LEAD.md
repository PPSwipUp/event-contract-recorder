# Plan (frozen 2026-10-06 ~10:15 BST, before any 6-7 Oct day-of data is analysed): related-market early warning

Question: do a game's LEADER markets (moneyline `aec-`, run spreads `asc-`, totals `tsc-`) move before its props jump,
early enough that pulling quotes on a leader move turns the variant-C fills from negative to positive value?

Data: live/pmusrec books every 30 s in the day-of window (6 h before first pitch / puck drop) of the games of
2026-10-06 and 2026-10-07 (MLB: LAD-ATL x2, MIL-SD, CLE-CWS, TB-NYY; NHL games reported separately).  The 2026-10-05
games were already seen and are used only as a code sanity check, not as evidence.

## Rule tested
- C_lead = variant C of PLAN_PMUS.md (thinnest 20% of markets per game, 500 contracts one tick behind the best price,
  stop at first pitch) PLUS: when any leader market of that game has moved >= 2c in mid since the previous snapshot,
  pull ALL of that game's quotes for 10 minutes.  Same scoring, fills proxy, rebate and settlement as PMUS_DAY.

## Measures
1. Prediction: P(some follower market of the game moves >= 3c in the next snapshot | a leader moved >= 2c now) vs the
   same probability with no leader move (lift).
2. Fills: count and closing-line value (cents/contract, t clustered by market) for C vs C_lead.
3. Money: rewards + rebate + fills valued at the closing line (outcome-free), per game, C vs C_lead.

## Gate (on the 6-7 Oct MLB games only)
PASS if C_lead's fills have closing-line value > 0 AND its outcome-free net (3.) is positive in the majority of games.
Otherwise the related-market warning does not rescue the LP: closed.  Settlement P&L reported but never used to judge.
Limit stated up front: 30-s snapshots cannot see a lead shorter than ~30 s.
