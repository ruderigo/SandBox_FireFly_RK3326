"""When a message was sent, from its sender's clock unless that clock is plainly
wrong (as the Android FireFly guards it): a board 30 years early (its 2000
epoch left in) corrected; before 2024 or a day ahead: when it arrived; a
message held for days by a propagation node keeps its time.
   python3 tests/run_times.py"""
import os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from firefly.core import sane_time, EPOCH_2000
ok = True
def check(c, w):
    global ok; print(("  PASS " if c else "  FAIL ") + w); ok = ok and bool(c)
now = time.time()
near = lambda a, b: abs(a - b) < 1
check(near(sane_time(now - 30, now), now - 30), "a right clock: kept")
check(near(sane_time(now - 30 - EPOCH_2000, now), now - 30), "30 years early (a board's 2000 epoch): corrected")
check(near(sane_time(12345, now), now), "a 1970 clock: when it arrived")
check(near(sane_time(EPOCH_2000 + 60, now), now), "a handheld that booted at 2000-01-01: when it arrived")
check(near(sane_time(now + 3 * 86400, now), now), "days ahead: when it arrived")
check(near(sane_time(now + 600, now), now + 600), "minutes ahead (clocks differ a little): kept")
check(near(sane_time(now - 3 * 86400, now), now - 3 * 86400), "held 3 days by a propagation node: kept")
check(near(sane_time(None, now), now) and near(sane_time("x", now), now), "no time at all: when it arrived")
print("all passed" if ok else "FAILURES")
sys.exit(0 if ok else 1)
