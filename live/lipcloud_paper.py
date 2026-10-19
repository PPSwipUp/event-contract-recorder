"""CLOUD-ONLY paper bot launcher for the lipcloud.yml twin (GitHub Actions).  PAPER ONLY, public GET only, no keys, no orders.
Runs the unchanged laptop strategy classes (lipgen_paper.GenBot over nfllip_paper) but persists the paper state to --state every sweep
and restores it at start, so inventory / rewards / per-window accounting carry across the chained ~5.4 h chunks.
Restore is deliberately conservative: queue position (cur quotes, hist, rest), the previous book (prev_ts: no reward is accrued across the
gap) and the trade-tape cursor (trades in the unrecorded gap are NOT replayed) are reset, so a chunk boundary behaves like "the bot
re-joined the back of the queue now".  Persisted: per-ticker inventory/cost, reward, fills, window counters + closed flag, settled map.
  python -u live/lipcloud_paper.py --kind gen|alt --root out/lipgen_cloud --out out/lipgen_paper_cloud.jsonl --state state/lipgen_paper_state.json
Request pacing identical to the laptop bots (gen: gap 0.4 s; alt: gap 1.4 s)."""
from __future__ import annotations

import argparse
import json
import os
import signal
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kxlipbook as KL  # noqa: E402
import lipgen_paper as GP  # noqa: E402

KINDS = {"gen": (0.4, "lipgen-readonly/1.0"), "alt": (1.4, "lipalt-readonly/1.0"), "f2": (1.4, "lipf2-readonly/1.0"), "f4e": (1.4, "lipf4e-readonly/1.0")}   # f2: PLAN_LIP_F2_FWD, f4e: PLAN_LIP_F4E_FWD
TK_FIELDS = ("p", "inv", "cost", "reward", "fills", "mid", "win_reward", "win_cov", "win_fills0", "closed")


def dump_state(bot):
    return {"v": 1, "settled": bot.settled, "T": {tk: {f: getattr(t, f) for f in TK_FIELDS} for tk, t in bot.T.items()}}


def load_state(bot, st):
    bot.settled = dict(st.get("settled") or {})
    for tk, d in (st.get("T") or {}).items():
        t = GP.TkG(d["p"])                                   # fresh queue state / prev_ts None / last_book_ts None
        for f in TK_FIELDS[1:]:
            setattr(t, f, list(d[f]) if isinstance(d[f], list) else d[f])
        bot.T[tk] = t


class CloudBot(GP.GenBot):
    def __init__(self, a, api, state_path):
        super().__init__(a, api)
        self.state_path = state_path
        if state_path and os.path.exists(state_path):
            try:
                load_state(self, json.load(open(state_path)))
                print("restored paper state: %d tickers, %d settled" % (len(self.T), len(self.settled)), flush=True)
            except (OSError, ValueError, KeyError) as e:     # corrupt state: start clean rather than die (logged)
                print("STATE RESTORE FAILED", type(e).__name__, e, flush=True)
                self.T, self.settled = {}, {}
        else:
            print("no paper state: starting clean", flush=True)

    def save(self):
        if not self.state_path:
            return
        tmp = self.state_path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(dump_state(self), f, separators=(",", ":"))
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.state_path)

    def sweep(self):
        super().sweep()
        self.save()                                          # every sweep: a window close is never lost to a crash


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", choices=sorted(KINDS), required=True)
    ap.add_argument("--root", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--state", required=True)
    ap.add_argument("--max-seconds", type=float, default=None)
    ap.add_argument("--sweep", type=float, default=15.0)
    ap.add_argument("--summary-every", type=float, default=3600.0)
    a = ap.parse_args()
    a.series = GP.AnySeries()
    gap, ua = KINDS[a.kind]
    api = KL.Api(gap=gap)
    api.s.headers["User-Agent"] = ua
    bot = CloudBot(a, api, a.state)

    def stop(*_):
        bot.save()
        sys.exit(0)
    for sg in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sg, stop)
    bot.run(a.max_seconds)
    bot.save()


if __name__ == "__main__":
    main()
