"""Recorder for the F4E LIP forward twin (results/PLAN_LIP_F4E_FWD.md): lipgen_rec.GenRecorder with the family filter
(live/lipf4e_draw.py) instead of the seeded random draw.  Output root live/lipf4e/.  PAPER ONLY, public GET only, no keys.
Request budget (live bots share the IP): book sweeps are batched (100 tickers/request), api gap 0.8 s => <= 1.25 req/s here, the paper bot
adds <= 0.7 req/s (together <= 2 req/s).  keyframe_s=45: unchanged books are re-written every 45 s so the paper bot's 60 s accrual cap holds.
  .venv/bin/python -u live/lipalt_rec.py"""
from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kxlipbook as KL  # noqa: E402
import lipgen_draw as LD  # noqa: E402
import lipgen_rec as GR  # noqa: E402
import lipf4e_draw as AD  # noqa: E402

log = logging.getLogger("lipf4e_rec")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.path.join(HERE, "lipf4e"))
    ap.add_argument("--draw", default=AD.DRAW_FILE)
    ap.add_argument("--sweep", type=float, default=15.0)
    ap.add_argument("--max-seconds", type=float, default=None)
    ap.add_argument("--log", default=os.path.join(HERE, "lipf4e_rec.log"))
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.FileHandler(a.log), logging.StreamHandler(sys.stdout)])
    api = KL.Api(gap=0.8)
    api.s.headers["User-Agent"] = "lipf4e-readonly/1.0"
    draw = AD.FamilyDraw(a.draw)
    rows = LD.pull_programs(api)
    if rows is None:
        sys.exit("program pull failed")
    new = draw.maintain(rows, time.time())
    log.info("family programs live at start: %d (new %d)", len(draw.active), len(new))
    rec = GR.GenRecorder(api, a.root, draw, lambda s: AD.sub_of(s) or "?", lambda t: True, sweep_s=a.sweep, prog_every=180.0, keyframe_s=0.0)
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
