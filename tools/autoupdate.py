# -*- coding: utf-8 -*-
"""tools/autoupdate.py - refresh the data and publish it to GitHub Pages.

WHY THIS EXISTS
---------------
The site's data can only be rebuilt on this machine: danjuan / csindex / sina /
tencent are China-only upstreams, so a GitHub Actions cron runner in the US
cannot fetch them (it would time out, or worse, silently produce gaps). The only
workable pipeline is therefore:

    scheduled local rebuild  ->  commit web/data  ->  push  ->  Pages workflow

That is what this script does, end to end:

1. ``tools.update`` refreshes the snapshot layer with a TTL (see that module for
   why a TTL is mandatory when every upstream URL is fixed) and has already
   decided whether anything new is even possible today.
2. If the manifest reports ``freshness.advanced=false`` (a weekend, a holiday,
   or an upstream that has not published yet), the working tree is restored and
   nothing is committed. Without that guard every run would add a
   "generated_at moved" commit and re-trigger the Pages build for no reason.
3. Otherwise ``web/data`` is committed and pushed. The Pages workflow is keyed
   on ``web/**``, so pushing *is* publishing - no deploy step here.

TWO TRANSPORT QUIRKS THIS HANDLES
---------------------------------
* The repo has ``http.proxy = http://127.0.0.1:7897`` configured. When that port
  is dead, git fails with "Failed to connect ... over proxy"; when it is alive,
  schannel fails the TLS handshake through it. github.com is reachable directly
  from here, so every git call below passes ``-c http.proxy=`` to bypass it.
* Auth is a classic PAT in ``.secrets/gh_token.txt``, injected as a one-shot
  ``http.extraheader`` instead of being written into the git config, so no
  credential helper ever persists it.

Exit codes: 0 ok (incl. "no new data") | 1 refresh failed | 2 publish failed | 3 unexpected
"""
from __future__ import annotations

import argparse
import base64
import os
import shutil
import socket
import subprocess
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from petrace.core import DATA_DIR, ROOT, ensure_dirs, read_json, setup_logging  # noqa: E402
from tools import update as update_mod  # noqa: E402

GIT_BRANCH = "main"
TOKEN_FILE = ROOT / ".secrets" / "gh_token.txt"
CLASH_EXE = Path(r"C:\Program Files\Clash Verge\clash-verge.exe")
PROXY_PORT = 7897
DATA_PATHSPEC = "web/data"


def _port_open(port: int, host: str = "127.0.0.1", timeout: float = 0.5) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        return s.connect_ex((host, port)) == 0


def ensure_proxy(log, wait_s: int = 60) -> bool:
    """Make sure the local proxy is up.

    This matters for reachability, not for the build: ``*.vercel.app`` is only
    routed when this proxy is running (Steam++'s SNI whitelist resets it
    otherwise), and Windows has it configured as the system proxy, so a dead
    listener there takes the browser's Vercel access down with it.
    """
    if _port_open(PROXY_PORT):
        log.info("proxy: 127.0.0.1:%d already listening", PROXY_PORT)
        return True
    if not CLASH_EXE.exists():
        log.warning("proxy: %d is down and %s is missing", PROXY_PORT, CLASH_EXE)
        return False
    log.info("proxy: starting %s", CLASH_EXE)
    try:
        subprocess.Popen(
            [str(CLASH_EXE)],
            creationflags=getattr(subprocess, "DETACHED_PROCESS", 0),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError as e:
        log.warning("proxy: could not start clash-verge: %s", e)
        return False
    import time
    for _ in range(wait_s):
        if _port_open(PROXY_PORT):
            log.info("proxy: up after %ds", _)
            return True
        time.sleep(1)
    log.warning("proxy: still down after %ds", wait_s)
    return False


def _git(args: list[str], log, timeout: int = 180) -> tuple[int, str]:
    """Run git with the dead-proxy config bypassed and one-shot auth."""
    cmd = [shutil.which("git") or "git", "-c", "http.proxy="]
    if TOKEN_FILE.exists():
        tok = TOKEN_FILE.read_text(encoding="utf-8").strip()
        if tok:
            b64 = base64.b64encode(f"x-access-token:{tok}".encode()).decode()
            cmd += ["-c", f"http.extraheader=Authorization: Basic {b64}"]
    cmd += args
    log.info("$ git %s", " ".join(a for a in args if "Authorization" not in a))
    p = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True,
                       timeout=timeout, encoding="utf-8", errors="replace")
    out = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, out


def publish(log, force: bool = False) -> int:
    """Commit and push web/data if it really changed. 0 ok, 2 failed."""
    rc, out = _git(["status", "--porcelain", DATA_PATHSPEC], log)
    if rc != 0:
        log.error("publish: git status failed:\n%s", out)
        return 2
    if not out.strip():
        log.info("publish: web/data is unchanged; nothing to push")
        return 0
    log.info("publish: changed files:\n%s", out)

    for step in (["add", DATA_PATHSPEC],
                 ["commit", "-m", f"data: refresh snapshot ({force and 'forced' or 'scheduled'})"],
                 ["push", "origin", GIT_BRANCH]):
        rc, out = _git(step, log)
        if rc != 0:
            log.error("publish: git %s failed:\n%s", step[0], out)
            return 2
        if out:
            log.info("publish: %s", out.splitlines()[-1] if out else "")
    log.info("publish: pushed to origin/%s - the Pages workflow will redeploy",
             GIT_BRANCH)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Refresh + publish PE-Trace data")
    ap.add_argument("--max-age", type=float, default=6.0, metavar="HOURS",
                    help="cache TTL handed to tools.update (default 6)")
    ap.add_argument("--min-interval", type=float, default=0.7)
    ap.add_argument("--force", action="store_true",
                    help="ignore tools.update's 'nothing new' skip")
    ap.add_argument("--force-publish", action="store_true",
                    help="commit even when freshness.advanced is false")
    ap.add_argument("--no-publish", action="store_true",
                    help="refresh only; leave the working tree dirty")
    ap.add_argument("--ensure-proxy", action="store_true",
                    help="start Clash Verge if 7897 is not listening")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    ensure_dirs()
    log = setup_logging(verbose=not args.quiet)
    log.info("=" * 72)
    log.info("autoupdate start")

    if args.ensure_proxy:
        ensure_proxy(log)

    upd_argv = ["--max-age", str(args.max_age),
                "--min-interval", str(args.min_interval)]
    if args.force:
        upd_argv.append("--force")
    if args.quiet:
        upd_argv.append("--quiet")
    rc = update_mod.main(upd_argv)
    if rc != 0:
        log.error("refresh failed (tools.update rc=%d)", rc)
        return 1

    man = read_json(DATA_DIR / "manifest.json") or {}
    fresh = man.get("freshness") or {}
    advanced = bool(fresh.get("advanced"))
    log.info("manifest: as_of=%s advanced=%s stale=%s with_pe=%s/%s",
             man.get("as_of"), advanced, fresh.get("stale_responses"),
             (man.get("counts") or {}).get("with_pe"),
             (man.get("counts") or {}).get("total"))

    if args.no_publish:
        log.info("--no-publish: stopping before commit")
        return 0

    if not advanced and not args.force_publish:
        rc, out = _git(["checkout", "--", DATA_PATHSPEC], log)
        if rc == 0:
            log.info("no new data this run; reverted the regenerated manifest")
        else:
            log.warning("could not revert %s:\n%s", DATA_PATHSPEC, out)
        return 0

    return publish(log, force=args.force_publish)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
