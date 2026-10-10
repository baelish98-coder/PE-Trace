# -*- coding: utf-8 -*-
"""
tools/serve.py - static file server for the PE-Trace page.

Why not just ``python -m http.server``:

``http.server`` sends no ``Cache-Control`` header at all, so browsers apply
*heuristic* caching (roughly 10% of the file's age) and may serve a stale
``app.js`` / ``style.css`` **without revalidating**. That bit us during
development: an edited ``app.js`` sat on disk while the page kept running the
old copy, so a fix looked like it had not worked.

That is worse in normal use, because this project's whole point is that the
data under ``web/data/**`` is refreshed by a scheduled job. A reader who leaves
the tab open and reloads must get the new numbers, never a cached copy.

So we send:

* ``no-cache`` for html/js/css/json - the browser may keep a copy but MUST
  revalidate with ``If-Modified-Since`` before using it. Unchanged files come
  back as a tiny 304, so this costs almost nothing.
* ``no-store`` for data json - never write it to disk at all.

Usage
-----
    python -m tools.serve                    # http://127.0.0.1:8791/
    python -m tools.serve --port 8080
    python -m tools.serve --open             # also launch the default browser
"""
from __future__ import annotations

import argparse
import functools
import http.server
import os
import socketserver
import sys
import threading
import webbrowser

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from petrace.core import WEB_DIR  # noqa: E402

NO_STORE_EXT = (".json",)
NO_CACHE_EXT = (".html", ".js", ".css", ".json", ".mjs")


class Handler(http.server.SimpleHTTPRequestHandler):
    quiet = False

    def end_headers(self) -> None:
        path = self.path.split("?", 1)[0].lower()
        # "/" is served as index.html, so a bare directory path is HTML too
        is_html_like = path.endswith("/") or path.endswith(NO_CACHE_EXT)
        if path.endswith(NO_STORE_EXT):
            self.send_header("Cache-Control", "no-store")
        elif is_html_like:
            # must revalidate, but a 304 makes that cheap
            self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()

    def log_message(self, fmt: str, *args) -> None:
        if not self.quiet:
            super().log_message(fmt, *args)


class Server(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Serve the PE-Trace page")
    ap.add_argument("--port", type=int, default=8791)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--root", default=str(WEB_DIR),
                    help="directory to serve (default: web/)")
    ap.add_argument("--open", action="store_true",
                    help="open the page in the default browser")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    root = os.path.abspath(args.root)
    if not os.path.isdir(root):
        print(f"[serve] no such directory: {root}")
        return 2
    if not os.path.exists(os.path.join(root, "data", "manifest.json")):
        print("[serve] warning: web/data/manifest.json is missing - run "
              "`python -m petrace.build` (or `python -m tools.update`) first")

    Handler.quiet = args.quiet
    handler = functools.partial(Handler, directory=root)
    url = f"http://{args.host}:{args.port}/"
    try:
        with Server((args.host, args.port), handler) as httpd:
            print(f"[serve] {root}")
            print(f"[serve] {url}   (Ctrl+C to stop)")
            if args.open:
                threading.Timer(0.5, lambda: webbrowser.open(url)).start()
            httpd.serve_forever()
    except OSError as e:
        print(f"[serve] cannot bind {args.host}:{args.port} - {e}")
        return 1
    except KeyboardInterrupt:
        print("\n[serve] stopped")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
