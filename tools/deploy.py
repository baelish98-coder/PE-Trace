"""Publish web/ to a free static host.

WHY THIS EXISTS
---------------
The site is pure static files (no backend, no secrets), but the data is rebuilt
**on this machine**: danjuan / csindex / sina / tencent all behave very
differently from outside mainland China, so the scheduled rebuild cannot be
moved to a US CI runner. The pipeline is therefore:

    local rebuild (tools/update.py)  ->  publish web/ only  ->  done

Measured from a Shanghai Mobile connection with no proxy (2026-10-10), which is
the number that matters for a China-facing site:

    host                            1 MB asset                       verdict
    ------------------------------  -------------------------------  ---------
    EdgeOne Makers (edgeone.cool)   0.31 s  (~3.3 MB/s)              best
    Netlify (netlify.app)           ~1.2-2.3 s TTFB                  ok
    GitHub Pages (185.199.x)        11.7-15.9 s (~55-87 KB/s)        slow
    Vercel (*.vercel.app)           timeout (000 after 20 s)         unusable
    Cloudflare Pages (*.pages.dev)  HTTP 522 on 3 of 4 test sites    unreliable

GitHub Pages is *reachable* from China but throttled to ~55 KB/s for large
files; this site's first load pulls a 1 MB ECharts bundle plus up to ~310 KB of
per-index JSON, so it would take the better part of a minute. EdgeOne Makers is
Tencent's own free tier and is explicitly marketed as "the world's first free
CDN with China access", which is why it is the default here.

TWO MODES
---------
1. ``--anonymous`` (default when no token is configured)
   Deploys with no account at all. Tencent creates a *temporary* project and
   returns an access URL carrying ``?eo_token=...&eo_time=...``. Good for a
   quick look, but:
     * the URL expires (the CLI prints a deadline, ~3 h),
     * every run creates a NEW project, so you accumulate junk projects,
     * the site is 401 without the token (or a cookie set by it).
   Claim the project to keep it:
       edgeone makers claim --sid <anonymousToken>
   or open ``claimUrl`` in a browser and sign in to Tencent Cloud.

2. ``--token <API_TOKEN>`` (production)
   Deploys to a named project you own, at a stable URL, with no expiry.
   Obtain the token in the EdgeOne Makers console (API Token page), then:
       setx EDGEONE_API_TOKEN "..."     # or pass --token / -t each time
   The token is read from ``EDGEONE_API_TOKEN`` when not given on the CLI, and
   is never written to disk by this script.

EXIT CODES
----------
    0  deployed
    1  deploy command failed
    2  edgeone CLI not found
    3  unexpected exception
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from petrace.core import ROOT, WEB_DIR, setup_logging  # noqa: E402

DEFAULT_PROJECT = "pe-trace"
TOKEN_ENV = "EDGEONE_API_TOKEN"


def _find_cli() -> str | None:
    """Locate the edgeone CLI. Installed globally by `npm i -g edgeone`."""
    for name in ("edgeone.cmd", "edgeone"):
        p = shutil.which(name)
        if p:
            return p
    # npm global prefix fallback: %APPDATA%\npm\edgeone.cmd
    appdata = os.environ.get("APPDATA")
    if appdata:
        cand = Path(appdata) / "npm" / "edgeone.cmd"
        if cand.exists():
            return str(cand)
    return None


def _run_cli(cli: str, args: list[str], log) -> tuple[int, str, str]:
    log.info("$ edgeone %s", " ".join(args))
    proc = subprocess.run(
        [cli, *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="tools.deploy",
        description="Publish web/ to Tencent EdgeOne Makers (free, China-accessible static hosting).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  python -m tools.deploy --anonymous        # quick throwaway URL, no account\n"
            "  python -m tools.deploy                    # uses $EDGEONE_API_TOKEN\n"
            "  python -m tools.deploy -t <token> -n pe-trace\n"
        ),
    )
    ap.add_argument("--dir", default=str(WEB_DIR), help="directory to publish (default: web/)")
    ap.add_argument("-n", "--name", default=DEFAULT_PROJECT, help=f"project name (default: {DEFAULT_PROJECT})")
    ap.add_argument("-t", "--token", default=None, help=f"API token (default: ${TOKEN_ENV})")
    ap.add_argument("--anonymous", action="store_true",
                    help="deploy without an account; URL expires and must be claimed to keep")
    ap.add_argument("--site", choices=["china", "global"], default="china",
                    help="region for anonymous deploys (default: china)")
    ap.add_argument("--env", choices=["production", "preview"], default="production")
    ap.add_argument("--dry-run", action="store_true", help="print the command without running it")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)

    log = setup_logging(args.verbose)
    target = Path(args.dir).resolve()

    if not target.is_dir():
        log.error("not a directory: %s", target)
        return 1

    files = [p for p in target.rglob("*") if p.is_file()]
    total = sum(p.stat().st_size for p in files)
    log.info("publishing %s (%d files, %.2f MB)", target, len(files), total / 1024 / 1024)

    # A site with no index.html cannot be served as a landing page.
    if not (target / "index.html").exists():
        log.error("refusing to publish: %s has no index.html", target)
        return 1

    token = args.token or os.environ.get(TOKEN_ENV) or None
    anonymous = args.anonymous or not token

    cli = _find_cli()
    if cli is None:
        log.error("edgeone CLI not found. install it with:  npm install -g edgeone")
        return 2

    argv_cli = ["makers", "deploy", str(target), "--json", "-e", args.env]
    if anonymous:
        argv_cli += ["--anonymous", "--site", args.site]
        log.warning("anonymous mode: the URL expires and must be claimed to keep "
                    "(edgeone makers claim --sid <token>)")
    else:
        argv_cli += ["-n", args.name, "-t", token]

    if args.dry_run:
        shown = [a if a != token else "<token>" for a in argv_cli]
        log.info("[dry-run] edgeone %s", " ".join(shown))
        return 0

    try:
        code, out, err = _run_cli(cli, argv_cli, log)
    except Exception as exc:  # pragma: no cover - defensive
        log.error("unexpected failure invoking the CLI: %s", exc)
        return 3

    if err.strip():
        # The CLI writes progress to stderr; only surface it on failure.
        log.debug("cli stderr: %s", err.strip()[:2000])

    if code != 0:
        log.error("deploy failed (exit %d)", code)
        for line in (err or out).strip().splitlines()[-25:]:
            log.error("  %s", line)
        return 1

    # The --json line may be preceded by human-readable progress lines.
    payload = None
    for line in reversed(out.strip().splitlines()):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                payload = json.loads(line)
                break
            except json.JSONDecodeError:
                continue

    if not payload:
        log.info("deploy finished, but no JSON result was parsed. raw tail:")
        for line in out.strip().splitlines()[-15:]:
            log.info("  %s", line)
        return 0

    url = payload.get("url", "")
    log.info("")
    log.info("  deployed OK")
    log.info("  URL        %s", url)
    log.info("  project    %s", payload.get("projectId", "-"))
    log.info("  deploy     %s", payload.get("deploymentId", "-"))
    if payload.get("claimUrl"):
        log.info("  claim      %s", payload["claimUrl"])
    if payload.get("expiresAt"):
        log.info("")
        log.warning("this anonymous deployment expires at %s and is deleted after that.",
                    payload["expiresAt"])
        log.warning("to keep it, run:  edgeone makers claim --sid %s", payload.get("anonymousToken", "<sid>"))
        log.warning("or set %s and redeploy to a permanent project.", TOKEN_ENV)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
