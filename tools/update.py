# -*- coding: utf-8 -*-
"""
tools/update.py - unattended refresh entry point for scheduled runs.

Why this exists instead of just calling ``petrace.build`` from a scheduler:

1. **TTL refresh.** Every upstream URL here is fixed (danjuan ``?day=all``,
   csindex ``endDate=20500101``, sina ``datalen=6000``), so cache keys never
   change. A scheduled rebuild without a TTL would re-read the same bytes
   forever; with ``--refresh`` it would re-crawl all 52 indices every time.
   Here we pass a TTL (default 6h) so a run re-fetches only what has expired,
   and a failed refresh falls back to the stale copy.

2. **Skip when the market has nothing new.** Running before the trading day
   settles just burns upstream requests and risks tripping the csindex WAF for
   data that cannot have changed. With ``--smart`` the job exits early when the
   last run happened after the most recent possible close.

3. **No overlapping runs.** A second invocation while one is in flight would
   interleave writes into web/data. A lock file makes the second run exit
   immediately.

4. **Non-zero exit on real failure**, so Task Scheduler / cron can alert.
   A run that succeeds but finds no new data still exits 0 - "no new data" is
   not an error, and the manifest records it as ``freshness.advanced=false``.

Usage
-----
    python -m tools.update                 # TTL refresh, skip if already fresh
    python -m tools.update --force         # always fetch, ignore the smart skip
    python -m tools.update --max-age 0     # full refresh (like build --refresh)
    python -m tools.update --quiet

Exit codes: 0 ok (incl. "nothing new") | 1 build failed | 2 lock held | 3 unexpected
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from petrace import build as build_mod  # noqa: E402
from petrace.core import DATA_DIR, LOG_DIR, ensure_dirs, read_json  # noqa: E402

LOCK = LOG_DIR / "update.lock"
CN_TZ = timedelta(hours=8)
# A-share close is 15:00 CST; the latest daily PE cannot exist before ~18:00
# CST (upstreams publish after settlement). A run after this hour on a weekday
# is assumed to already have the newest possible bar.
SETTLE_HOUR = 18


def _now_cn() -> datetime:
    return datetime.now(timezone.utc).astimezone(timezone(CN_TZ))


def _latest_possible_close(now: datetime) -> str:
    """The most recent date whose close could already be published."""
    d = now.date()
    if now.hour < SETTLE_HOUR:
        d = d - timedelta(days=1)
    while d.weekday() >= 5:          # Sat=5, Sun=6
        d = d - timedelta(days=1)
    return d.isoformat()


def _should_skip(now: datetime) -> tuple[bool, str]:
    man = read_json(DATA_DIR / "manifest.json")
    if not man:
        return False, "no previous manifest"
    target = _latest_possible_close(now)
    as_of = man.get("as_of")
    if not as_of:
        return False, "previous manifest has no as_of"
    if str(as_of) >= target:
        return True, (f"as_of {as_of} already covers the latest possible close "
                      f"{target}")
    return False, f"as_of {as_of} is behind the latest possible close {target}"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Scheduled PE-Trace refresh")
    ap.add_argument("--max-age", type=float, default=6.0, metavar="HOURS",
                    help="cache TTL in hours; 0 forces a full re-fetch (default 6)")
    ap.add_argument("--min-interval", type=float, default=0.7)
    ap.add_argument("--force", action="store_true",
                    help="ignore the 'nothing new' skip")
    ap.add_argument("--no-lock", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    ensure_dirs()
    now = _now_cn()

    if not args.no_lock:
        if LOCK.exists():
            age = time.time() - LOCK.stat().st_mtime
            if age < 3600:
                print(f"[update] another run is in progress "
                      f"(lock is {age / 60:.0f} min old); exiting")
                return 2
            print(f"[update] removing stale lock ({age / 60:.0f} min old)")
            LOCK.unlink()
        LOCK.write_text(f"{os.getpid()} {now.isoformat()}\n", encoding="utf-8")

    try:
        if not args.force:
            skip, why = _should_skip(now)
            if skip:
                print(f"[update] skip: {why}")
                return 0
            if not args.quiet:
                print(f"[update] running: {why}")

        build_argv = ["--min-interval", str(args.min_interval)]
        # 0 is a meaningful TTL ("everything expired") - test `is not None`.
        if args.max_age is not None:
            build_argv += ["--max-age", str(args.max_age)]
        else:
            build_argv += ["--refresh"]
        rc = build_mod.main(build_argv)
        if rc != 0:
            print(f"[update] build returned {rc}")
            return 1

        man = read_json(DATA_DIR / "manifest.json") or {}
        fr = man.get("freshness") or {}
        hits = (man.get("http") or {})
        print(f"[update] ok | as_of={man.get('as_of')} "
              f"| advanced={fr.get('advanced')} | stale={fr.get('stale_responses')} "
              f"| with_pe={man.get('counts', {}).get('with_pe')}"
              f"/{man.get('counts', {}).get('total')} | http={hits}")
        return 0
    except Exception as e:                       # noqa: BLE001
        print(f"[update] FAILED: {type(e).__name__}: {e}")
        return 3
    finally:
        if not args.no_lock and LOCK.exists():
            try:
                LOCK.unlink()
            except OSError:
                pass


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
