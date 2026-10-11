# -*- coding: utf-8 -*-
"""Boundary tests for tools/scheduler.py next_run (weekday + time rollover)."""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.scheduler import CN_TZ, next_run  # noqa: E402

CASES = [
    ("2026-10-11T10:00", "Sat, before time -> Mon 18:30"),
    ("2026-10-11T19:00", "Sat, after time  -> Mon 18:30"),
    ("2026-10-12T10:00", "Mon, before time -> Mon 18:30"),
    ("2026-10-12T18:29", "Mon, 1 min before -> Mon 18:30"),
    ("2026-10-12T18:30", "Mon, exactly at  -> Tue 18:30"),
    ("2026-10-12T19:00", "Mon, after time  -> Tue 18:30"),
    ("2026-10-16T20:00", "Fri, after time  -> Mon 18:30"),
    ("2026-10-17T00:01", "Sat, midnight    -> Mon 18:30"),
]

ok = True
for s, note in CASES:
    dt = datetime.fromisoformat(s).replace(tzinfo=CN_TZ)
    n = next_run(dt, 18, 30)
    weekend = n.weekday() >= 5
    flag = "BAD" if weekend else "ok "
    if weekend:
        ok = False
    print(f"{flag} {s} {dt.strftime('%a')} -> "
          f"{n.isoformat(timespec='minutes')} {n.strftime('%a')}   # {note}")

print("\nall targets are weekdays:", ok)
raise SystemExit(0 if ok else 1)
