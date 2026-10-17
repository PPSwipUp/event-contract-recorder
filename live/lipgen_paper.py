"""PAPER-ONLY general-LIP forward bot (results/PLAN_LIP_GENERAL_FWD.md).  Thin wrapper over live/nfllip_paper.py (same touch strategy,
klb rules, queue-aware fills, official snapshot share, conventions) reading live/lipgen/ written by live/lipgen_rec.py.  Adds:
  * per-program-WINDOW accounting: a {"k":"win"} line when a window ends (raw reward at multiplier 1.0, recorded seconds, window seconds,
    fills, inventory).  The $1-minimum is applied at report time at the chosen multiplier (paid = m*raw if m*raw >= 1 else 0).
  * settlement marking: once a window has ended and the ticker holds inventory, public GET /markets?tickers= every 10 min until
    settled -> {"k":"settle"} with pnl against the settlement value (inventory is marked to mid until then).
No orders, no keys.   .venv/bin/python -u live/lipgen_paper.py --root live/lipgen --out live/lipgen_paper.jsonl
"""
from __future__ import annotations

import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kxlipbook as KL  # noqa: E402
import nfllip_paper as NP  # noqa: E402

MIN_PAID = 1.0                                   # Kalshi: a program window paying < $1 pays nothing
SETTLE_EVERY = 600.0


class AnySeries:
    def __contains__(self, _):
        return True                              # recorder only writes drawn programs, so no series filter is needed


class TkG(NP.Tk):
    """Tk + per-window reward / recorded-seconds counters (window = the program's [s0, s1))."""

    def __init__(self, prog):
        super().__init__(prog)
        self.win_reward, self.win_cov, self.win_fills0, self.closed = 0.0, 0.0, 0, False

    def on_book(self, ts, now, yl, nl):
        p, r0 = self.p, self.reward
        if self.prev_ts is not None:
            self.win_cov += max(0.0, min(min(ts, p["s1"]), self.prev_ts + NP.MAX_DT) - max(self.prev_ts, p["s0"]))
        out = super().on_book(ts, now, yl, nl)
        self.win_reward += self.reward - r0
        return out

    def on_trade(self, ts, yp, np_, c, taker):
        if self.closed or ts >= self.p["s1"]:            # quotes are cancelled when the window ends: no fills on stale quotes
            return []
        return super().on_trade(ts, yp, np_, c, taker)

    def finish(self, now):
        """accrue the tail of the last snapshot up to s1 (<= MAX_DT, only if the last book is recent), return the window record."""
        p = self.p
        if self.prev_ts is not None and not self.closed:
            tail = max(0.0, min(p["s1"], self.prev_ts + NP.MAX_DT) - max(self.prev_ts, p["s0"]))
            if self.prev_share and tail:
                add = p["pool"] * self.prev_share * tail / (p["s1"] - p["s0"])
                self.reward += add
                self.win_reward += add
            self.win_cov += tail
        self.closed = True
        return {"k": "win", "ts": round(now, 3), "ticker": p["ticker"], "s0": p["s0"], "s1": p["s1"], "pool": p["pool"],
                "raw": round(self.win_reward, 6), "rec_s": round(self.win_cov, 1), "win_s": p["s1"] - p["s0"],
                "fills": self.fills - self.win_fills0, "inv": list(self.inv), "cost": list(self.cost)}

    def reopen(self, prog):
        self.p, self.win_reward, self.win_cov, self.win_fills0, self.closed = prog, 0.0, 0.0, self.fills, False
        self.prev_ts, self.prev_share = None, 0.0           # never accrue across windows


def settle_pnl(inv, cost, sv):
    """realised pnl of the paper inventory at yes-settlement value sv (0..1): yes pays sv, no pays 1-sv."""
    return inv[0] * sv - cost[0] + inv[1] * (1 - sv) - cost[1]


def settlement_value(m):
    """yes payout per contract from a market row, or None while unsettled."""
    if (m.get("status") or "") not in ("settled", "finalized"):
        return None
    sv = KL.fnum(m.get("settlement_value_dollars"))
    if sv is not None and m.get("settlement_value_dollars") not in ("", None):
        return sv
    return {"yes": 1.0, "no": 0.0}.get(m.get("result"))


class GenBot(NP.Bot):
    def __init__(self, a, api=None, clock=time.time):
        NP.Tk = TkG                                       # Bot.sweep builds Tk objects through the module name
        super().__init__(a, api, clock)
        self.settled, self.t_settle = {}, 0.0

    def roll_windows(self, now):
        if now - self.t_prog >= 60:
            self.t_prog = now
            self.progs = NP.active_programs(self.a.root, self.a.series, now)
            for tk, p in self.progs.items():
                if tk not in self.T:
                    self.T[tk] = TkG(p)
        for tk, t in self.T.items():
            cur = self.progs.get(tk)
            if not t.closed and (now >= t.p["s1"] or (cur and (cur["s0"], cur["s1"]) != (t.p["s0"], t.p["s1"]))):
                self.w(t.finish(now))
            if t.closed and cur and cur["s0"] <= now < cur["s1"] and (cur["s0"], cur["s1"]) != (t.p["s0"], t.p["s1"]):
                t.reopen(cur)

    def settle(self, now):
        if now - self.t_settle < SETTLE_EVERY:
            return
        self.t_settle = now
        todo = sorted(tk for tk, t in self.T.items() if t.closed and tk not in self.settled and sum(t.inv) > 0)
        for i in range(0, len(todo), 100):
            d = self.api.get("/markets", {"tickers": ",".join(todo[i:i + 100]), "limit": 100})
            for m in (d or {}).get("markets") or []:
                sv = settlement_value(m)
                if sv is None:
                    continue
                t = self.T[m["ticker"]]
                pnl = settle_pnl(t.inv, t.cost, sv)
                self.settled[m["ticker"]] = pnl
                self.w({"k": "settle", "ts": round(now, 3), "ticker": m["ticker"], "result": m.get("result"), "sv": sv,
                        "inv": list(t.inv), "cost": list(t.cost), "pnl": round(pnl, 6)})
        self.out.flush()

    def sweep(self):
        now = self.now()
        self.roll_windows(now)
        super().sweep()
        self.settle(now)
        self.out.flush()

    def summary(self):
        o = super().summary()
        o["settled"] = len(self.settled)
        o["settled_pnl"] = round(sum(self.settled.values()), 4)
        for tk, t in self.T.items():                       # per-ticker inventory state for the daily summary (unsettled marks)
            if sum(t.inv) > 0 and tk not in self.settled:
                self.w({"k": "tk", "ts": o["ts"], "ticker": tk, "inv": list(t.inv), "cost": list(t.cost), "mid": t.mid,
                        "mark": round(t.mark_pnl(), 6)})
        self.out.flush()
        return o


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.path.join(HERE, "lipgen"))
    ap.add_argument("--out", default=os.path.join(HERE, "lipgen_paper.jsonl"))
    ap.add_argument("--max-seconds", type=float, default=None)
    ap.add_argument("--sweep", type=float, default=15.0)
    ap.add_argument("--summary-every", type=float, default=3600.0)
    a = ap.parse_args()
    a.series = AnySeries()
    api = KL.Api(gap=0.4)
    api.s.headers["User-Agent"] = "lipgen-readonly/1.0"
    GenBot(a, api).run(a.max_seconds)


if __name__ == "__main__":
    main()
