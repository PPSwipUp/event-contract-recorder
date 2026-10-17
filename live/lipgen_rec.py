"""Recorder for the general-LIP forward paper test (results/PLAN_LIP_GENERAL_FWD.md).  Same output layout and book/tape/meta code as
live/kxlipbook.py (reused by subclassing; kxlipbook.py itself is untouched), but the universe is the seeded program draw in
live/lipgen_draw.jsonl (made once by live/lipgen_draw.py --init) instead of the hard-coded NFL/commodity series.
Public GET only.  Output root live/lipgen/.  Every fetched book is written every sweep (keyframe_s=0) so the paper bot's 60 s
accrual cap never truncates quiet books.
  .venv/bin/python -u live/lipgen_rec.py            # run forever
"""
from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
import time
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kxlipbook as KL  # noqa: E402
import lipgen_draw as LD  # noqa: E402

log = logging.getLogger("lipgen_rec")


class GenRecorder(KL.Recorder):
    def __init__(self, api, root, draw, cat_of_series, open_ok, **kw):
        kw.setdefault("keyframe_s", 0.0)
        super().__init__(api, root, **kw)
        self.draw, self.cat_of, self.open_ok = draw, cat_of_series, open_ok
        self.drawn_tickers = {p["market_ticker"] for p in draw.drawn.values()}
        orig = self.out.write

        def write(stream, ts, obj):                      # tape: only drawn markets (the feed filter is series-level)
            if stream == "tape" and obj.get("t") not in self.drawn_tickers:
                return
            orig(stream, ts, obj)
        self.out.write = write
        self._sync_tracked()

    def _sync_tracked(self):
        KL.TRACKED.clear()                               # poll_tape's series filter, module global in kxlipbook
        KL.TRACKED.update(KL.series_of(t) for t in self.drawn_tickers)

    # ---- universe = the draw ---------------------------------------------------------------------------------------
    def refresh_programs(self):
        t = self.now()
        rows = LD.pull_programs(self.api)
        if rows is None:
            self.c["prog_fail"] += 1
            return
        for p in self.draw.maintain(rows, t, self.cat_of, self.open_ok):
            log.info("REPLACE -> %s (%s) %s", p["market_ticker"], p["cat"], p["id"])
            self.c["replaced"] += 1
        by_id = {r["id"]: r for r in rows}
        act = {}
        for pid, p in self.draw.active.items():
            r = by_id.get(pid, p)
            self.drawn_tickers.add(r["market_ticker"])
            if self.prog.get(pid) != r:
                self.prog[pid] = r
                self.out.write("meta", t, {"k": "prog", "ts": t, "row": r})
                self.c["prog_rows"] += 1
            a, b = KL.iso_ts(r["start_date"]), KL.iso_ts(r["end_date"])
            if a is not None and b is not None and a <= t < b:
                act[r["market_ticker"]] = (a, b)
        self.prog_active = act
        self.prog = {k: v for k, v in self.prog.items() if (KL.iso_ts(v["end_date"]) or 1e18) > t - 86400}
        self._sync_tracked()
        self.c["prog_ok"] += 1

    def discover(self):
        self.open15 = {}

    def refresh_meta(self):
        tk = sorted(self.prog_active)
        for i in range(0, len(tk), 100):
            d = self.api.get("/markets", {"tickers": ",".join(tk[i:i + 100]), "limit": 100})
            if d is None:
                self.c["meta_fail"] += 1
                continue
            for m in d.get("markets") or []:
                self.write_meta(m, force=True)

    def heartbeat(self):
        t, c = self.now(), self.c
        log.info("HB utc=%s sweeps=%d fail=%d books=%d/%d written=%d tape=%d prog_rows=%d replaced=%d univ=%d req=%d err=%d "
                 "last_ok_age=%ds consec_fail=%d day_gz_MB=%.2f", datetime.fromtimestamp(t, timezone.utc).strftime("%H:%M:%S"),
                 c["sweeps"], c["sweeps_fail"], c["books_ok"], c["books_req"], c["books_written"], c["tape_written"],
                 c["prog_rows"], c["replaced"], len(self.universe()), self.api.n_req, self.api.n_err, int(t - self.last_ok),
                 self.consec_fail, self.out.day_bytes(t) / 1e6)
        self.c = type(c)()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.path.join(HERE, "lipgen"))
    ap.add_argument("--draw", default=LD.DRAW_FILE)
    ap.add_argument("--sweep", type=float, default=15.0)
    ap.add_argument("--max-seconds", type=float, default=None)
    ap.add_argument("--log", default=os.path.join(HERE, "lipgen_rec.log"))
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.FileHandler(a.log), logging.StreamHandler(sys.stdout)])
    draw = LD.Draw(a.draw)
    if not draw.initialised:
        sys.exit("no draw in %s: run lipgen_draw.py --init first (the draw must be saved before recording)" % a.draw)
    api = KL.Api(gap=0.4)
    api.s.headers["User-Agent"] = "lipgen-readonly/1.0"
    rec = GenRecorder(api, a.root, draw, LD.CatCache(api), LD.OpenCheck(api), sweep_s=a.sweep, prog_every=600.0)
    for sg in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sg, lambda *_: setattr(rec, "stop", True))
    while True:
        try:
            rec.run(a.max_seconds)
            break
        except Exception:
            log.exception("run loop crashed; restarting in 10 s")
            time.sleep(10)
            rec.out.close()


if __name__ == "__main__":
    main()
