# -*- coding: utf-8 -*-
"""tools/scheduler.py - keep the snapshot fresh without Task Scheduler.

WHY A RESIDENT PROCESS
----------------------
This account runs under a UAC-filtered token: ``BUILTIN\\Administrators`` is
present only as "Group used for deny only" at Medium integrity, so both
``schtasks`` (``ERROR: Access is denied.``) and ``Register-ScheduledTask``
(``CimException: 拒绝访问。``) fail no matter how the task is scoped. What *is*
writable is the per-user Startup folder and the ``HKCU\\...\\Run`` key.

So instead of registering a scheduled task we drop a launcher in Startup and
keep one long-lived process that sleeps between runs. This is also the more
honest design for this workload: the data can only be refreshed from this
machine (China-only upstreams), it has to be refreshed on the machine's own
clock and calendar, and a missed window must be recovered on next boot rather
than skipped - all of which this loop handles explicitly:

* **Catch-up on start.** If the machine was asleep or off at the scheduled
  minute, the manifest is behind the most recent possible close, so we run
  immediately instead of waiting a full day.
* **Weekday-only.** Markets are shut at the weekend, so Saturday/Sunday are
  skipped; ``tools.update``'s ``--smart`` guard remains the second line of
  defence against running before the upstream has published.
* **Sleep in slices.** Long sleeps are broken into short intervals so the log
  records a heartbeat and a ``--stop-file`` can end the process promptly.
* **Never dies on a bad run.** An unexpected exception is logged and the loop
  continues; only an explicit stop file or a fatal import error ends it.

Usage
-----
    python -m tools.scheduler --once              # single cycle, for testing
    python -m tools.scheduler                     # resident loop (18:30 CST)
    python -m tools.scheduler --install-startup   # register in the Startup folder
    python -m tools.scheduler --uninstall-startup # remove it again

Exit codes: 0 ok | 1 fatal | 2 startup registration failed
"""
from __future__ import annotations

import argparse
import atexit
import json
import logging
import os
import sys
import time
from datetime import datetime, time as dtime, timedelta, timezone
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from petrace.core import LOG_DIR, ROOT, ensure_dirs, read_json, setup_logging  # noqa: E402
from tools import autoupdate as autoupdate_mod  # noqa: E402
from tools.update import _latest_possible_close  # noqa: E402

CN_TZ = timezone(timedelta(hours=8))
HEARTBEAT = LOG_DIR / "scheduler.heartbeat.json"
PID_FILE = LOG_DIR / "scheduler.pid"
STOP_FILE = LOG_DIR / "scheduler.stop"
STARTUP_NAME = "PE-Trace Scheduler.vbs"
DEFAULT_HOUR, DEFAULT_MINUTE = 18, 30
SLEEP_SLICE = 300          # seconds between heartbeat writes
RUN_TIMEOUT_LOG = "run finished"


def _now_cn() -> datetime:
    return datetime.now(CN_TZ)


def _pid_alive(pid: int) -> bool:
    """True if a live process still owns ``pid``.

    ``os.kill(pid, 0)`` is NOT a valid liveness probe on Windows: CPython maps
    a non-console signal to ``TerminateProcess``, so "checking" would kill the
    very process being inspected. ``OpenProcess`` +
    ``GetExitCodeProcess`` is the read-only equivalent and needs no elevation
    for a same-user process.
    """
    if os.name != "nt":
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        return True
    import ctypes
    from ctypes import wintypes

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    STILL_ACTIVE = 259
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.OpenProcess.restype = wintypes.HANDLE
    handle = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
    if not handle:
        return False
    try:
        code = wintypes.DWORD()
        if not k32.GetExitCodeProcess(handle, ctypes.byref(code)):
            return False
        return code.value == STILL_ACTIVE
    finally:
        k32.CloseHandle(handle)


def _acquire_singleton(log: logging.Logger) -> bool:
    """False when another scheduler already holds the slot.

    The Startup launcher fires on every logon, so without this guard a machine
    that is logged into several times would accumulate one daemon per logon,
    each waking at 18:30 and racing on web/data and the git index.
    """
    prev = read_json(PID_FILE, {}) or {}
    pid = prev.get("pid")
    if isinstance(pid, int) and pid != os.getpid() and _pid_alive(pid):
        log.info("another scheduler is already running (pid %d); exiting", pid)
        return False
    try:
        PID_FILE.write_text(
            json.dumps({"pid": os.getpid(),
                        "started_at": _now_cn().isoformat(timespec="seconds")},
                       ensure_ascii=False, indent=1),
            encoding="utf-8")
    except OSError:
        pass
    return True


def next_run(now: datetime, hour: int, minute: int) -> datetime:
    """The next weekday occurrence of hour:minute at or after ``now``."""
    cand = datetime.combine(now.date(), dtime(hour, minute), tzinfo=now.tzinfo)
    if cand <= now:
        cand += timedelta(days=1)
    while cand.weekday() >= 5:              # Sat=5, Sun=6
        cand += timedelta(days=1)
    return cand


def _write_heartbeat(payload: dict) -> None:
    try:
        tmp = HEARTBEAT.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=1),
                       encoding="utf-8")
        os.replace(tmp, HEARTBEAT)
    except OSError:
        pass


def _sleep_until(target: datetime, log: logging.Logger,
                 stop_file: Path, heartbeat: dict) -> bool:
    """Sleep in slices until ``target``. False if the stop file appeared."""
    while True:
        if stop_file.exists():
            log.info("stop file present; exiting")
            return False
        remaining = (target - _now_cn()).total_seconds()
        if remaining <= 0:
            return True
        chunk = min(SLEEP_SLICE, remaining)
        heartbeat["next_run"] = target.isoformat(timespec="seconds")
        heartbeat["sleeping_until"] = (
            _now_cn() + timedelta(seconds=chunk)).isoformat(timespec="seconds")
        _write_heartbeat(heartbeat)
        time.sleep(chunk)


def run_once(log: logging.Logger, args, heartbeat: dict,
             persist: bool = True) -> int:
    log.info("-" * 60)
    log.info("cycle start (as_of guard: latest possible close %s)",
             _latest_possible_close(_now_cn()))
    argv = ["--max-age", str(args.max_age), "--min-interval", str(args.min_interval)]
    if args.force:
        argv.append("--force")
    if args.ensure_proxy:
        argv.append("--ensure-proxy")
    if args.quiet:
        argv.append("--quiet")
    t0 = time.time()
    try:
        rc = autoupdate_mod.main(argv)
    except Exception as e:                       # noqa: BLE001
        log.exception("cycle raised %s: %s", type(e).__name__, e)
        rc = 99
    log.info("cycle done rc=%d in %.1fs (%s)", rc, time.time() - t0, RUN_TIMEOUT_LOG)
    heartbeat["last_run"] = _now_cn().isoformat(timespec="seconds")
    heartbeat["last_rc"] = rc
    heartbeat["last_duration_sec"] = round(time.time() - t0, 1)
    man = read_json(ROOT / "web" / "data" / "manifest.json") or {}
    heartbeat["as_of"] = man.get("as_of")
    heartbeat["runs"] = int(heartbeat.get("runs", 0)) + 1
    # ``--once`` is a diagnostic: it must not clobber the resident daemon's
    # heartbeat with a pid that dies seconds later.
    if persist:
        _write_heartbeat(heartbeat)
    return rc


def _startup_dir() -> Path:
    appdata = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    return (Path(appdata) / "Microsoft" / "Windows" / "Start Menu"
            / "Programs" / "Startup")


def _pythonw() -> str:
    """Prefer pythonw.exe so the launcher never flashes a console."""
    exe = Path(sys.executable)
    cand = exe.with_name("pythonw.exe")
    return str(cand if cand.exists() else exe)


def install_startup(log: logging.Logger, ensure_proxy: bool) -> int:
    d = _startup_dir()
    if not d.is_dir():
        log.error("startup folder not found: %s", d)
        return 2
    extra = " --ensure-proxy" if ensure_proxy else ""
    vbs = (
        "' PE-Trace scheduler launcher (generated by tools/scheduler.py)\n"
        "' Remove with: python -m tools.scheduler --uninstall-startup\n"
        'Set sh = CreateObject("WScript.Shell")\n'
        f'sh.CurrentDirectory = "{ROOT}"\n'
        f'sh.Run """{_pythonw()}"" -m tools.scheduler --quiet{extra}", 0, False\n'
    )
    target = d / STARTUP_NAME
    target.write_text(vbs, encoding="utf-8")
    log.info("installed startup launcher: %s", target)
    log.info("  interpreter: %s", _pythonw())
    log.info("  working dir: %s", ROOT)
    return 0


def uninstall_startup(log: logging.Logger) -> int:
    target = _startup_dir() / STARTUP_NAME
    if target.exists():
        target.unlink()
        log.info("removed startup launcher: %s", target)
    else:
        log.info("no startup launcher at %s", target)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="PE-Trace resident scheduler")
    ap.add_argument("--at", default=f"{DEFAULT_HOUR:02d}:{DEFAULT_MINUTE:02d}",
                    metavar="HH:MM", help="daily run time, China time (default 18:30)")
    ap.add_argument("--max-age", type=float, default=6.0, metavar="HOURS")
    ap.add_argument("--min-interval", type=float, default=0.7)
    ap.add_argument("--force", action="store_true",
                    help="passed through: ignore the 'nothing new' skip")
    ap.add_argument("--ensure-proxy", action="store_true",
                    help="start Clash Verge if 7897 is down (keeps Vercel reachable)")
    ap.add_argument("--once", action="store_true",
                    help="run a single cycle now and exit")
    ap.add_argument("--install-startup", action="store_true")
    ap.add_argument("--uninstall-startup", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    ensure_dirs()
    log = setup_logging(verbose=not args.quiet)

    if args.install_startup:
        return install_startup(log, args.ensure_proxy)
    if args.uninstall_startup:
        return uninstall_startup(log)

    try:
        hh, mm = (int(x) for x in args.at.split(":"))
        assert 0 <= hh <= 23 and 0 <= mm <= 59
    except (ValueError, AssertionError):
        log.error("bad --at value %r (want HH:MM)", args.at)
        return 1

    # Claim the singleton slot BEFORE writing the heartbeat: a second instance
    # must not overwrite the running daemon's heartbeat with its own pid.
    if args.once:
        # Diagnostic run: keep the resident daemon's heartbeat/pid files intact.
        log.info("=" * 60)
        log.info("scheduler one-shot (pid %d)", os.getpid())
        run_once(log, args, {}, persist=False)
        return 0

    if not _acquire_singleton(log):
        return 0
    # Best-effort tidy-up. A hard kill skips this, which is fine: the next
    # start finds a dead pid and simply takes the slot over.
    atexit.register(lambda: PID_FILE.unlink(missing_ok=True))

    heartbeat = read_json(HEARTBEAT, {}) or {}
    heartbeat["pid"] = os.getpid()
    heartbeat["started_at"] = _now_cn().isoformat(timespec="seconds")
    heartbeat["schedule"] = f"{hh:02d}:{mm:02d} Asia/Shanghai, weekdays"
    heartbeat.setdefault("runs", 0)
    _write_heartbeat(heartbeat)

    log.info("=" * 60)
    log.info("scheduler up (pid %d); daily at %02d:%02d Asia/Shanghai, weekdays",
             os.getpid(), hh, mm)

    # Catch-up: a laptop that was shut at the scheduled minute must not skip a
    # whole day, so run immediately when the snapshot is behind.
    now = _now_cn()
    man = read_json(ROOT / "web" / "data" / "manifest.json") or {}
    as_of = man.get("as_of")
    target = _latest_possible_close(now)
    if as_of and str(as_of) < target:
        log.info("catch-up: as_of %s is behind %s; running now", as_of, target)
        run_once(log, args, heartbeat)
    elif not as_of:
        log.info("no manifest yet; running now")
        run_once(log, args, heartbeat)
    else:
        log.info("up to date (as_of %s >= %s); waiting for the next slot",
                 as_of, target)

    while True:
        nxt = next_run(_now_cn(), hh, mm)
        log.info("next run: %s", nxt.isoformat(timespec="seconds"))
        heartbeat["next_run"] = nxt.isoformat(timespec="seconds")
        _write_heartbeat(heartbeat)
        if not _sleep_until(nxt, log, STOP_FILE, heartbeat):
            return 0
        run_once(log, args, heartbeat)


if __name__ == "__main__":
    # Under pythonw.exe both std streams are None. Guard the reconfiguration
    # explicitly: calling .reconfigure() on None raises AttributeError, and
    # because stderr is None too the process would die with no message at all
    # (the exact failure mode the Startup launcher would hit at every logon).
    if sys.stdout is not None:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if sys.stderr is not None:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
