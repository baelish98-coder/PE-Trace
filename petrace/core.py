# -*- coding: utf-8 -*-
"""
petrace.core - paths, disk-cached HTTP client with per-host pacing, IO helpers.

Design notes
------------
* Every network response is cached verbatim on disk, keyed by its request URL.
  Rebuilds never re-hit the network unless ``refresh=True`` is passed.
* Upstreams (eastmoney / danjuan) rate-limit aggressively; a per-host minimum
  interval plus bounded exponential backoff keeps long crawls reliable.
* No financial computation lives here - this module only moves and stores bytes.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

import requests
import urllib3

urllib3.disable_warnings()

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "cache"
LOG_DIR = ROOT / "logs"
WEB_DIR = ROOT / "web"
DATA_DIR = WEB_DIR / "data"
INDEX_DATA_DIR = DATA_DIR / "index"
# Parsed, ready-to-use series kept outside the HTTP cache, so a series survives
# an upstream outage even when the cached response itself expires or the
# request URL changes (a moving endDate makes every fetch a new cache key).
SNAP_DIR = CACHE_DIR / "snapshots"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

DEFAULT_HEADERS = {
    "User-Agent": UA,
    "Accept": "*/*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Connection": "keep-alive",
}


def ensure_dirs() -> None:
    for d in (CACHE_DIR, LOG_DIR, DATA_DIR, INDEX_DATA_DIR):
        d.mkdir(parents=True, exist_ok=True)


def setup_logging(verbose: bool = False) -> logging.Logger:
    ensure_dirs()
    logger = logging.getLogger("petrace")
    if logger.handlers:
        return logger
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)-5s %(message)s", "%H:%M:%S")
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)
    fh = logging.FileHandler(LOG_DIR / "petrace.log", encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    return logger


def write_json(path: Path, obj, *, indent: int | None = None) -> None:
    """Atomic JSON write (temp file + replace) so readers never see a partial file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        if indent is None:
            json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
        else:
            json.dump(obj, f, ensure_ascii=False, indent=indent)
    os.replace(tmp, path)


def read_json(path: Path, default=None):
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _snap_path(name: str) -> Path:
    safe = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in name)
    return SNAP_DIR / f"{safe}.json"


def save_snapshot(name: str, rows: list) -> None:
    """Remember a successfully parsed series under a stable, URL-independent
    name. Upstreams here go dark for hours (legulegu serves 504 site-wide,
    csindex trips its WAF); when that happens the last good copy keeps the
    page complete instead of silently dropping a series."""
    if not rows:
        return
    write_json(_snap_path(name), {"name": name, "fetched_at": time.time(),
                                  "rows": rows})
    # a copy in the legulegu dir would be redundant; snapshots/ is the one place


def load_snapshot(name: str) -> tuple[list, str | None]:
    """Return (rows, stamp_text). rows is [] when nothing was ever stored."""
    rec = read_json(_snap_path(name))
    if not rec or not rec.get("rows"):
        return [], None
    stamp = time.strftime("%Y-%m-%d %H:%M", time.localtime(rec["fetched_at"]))
    return rec["rows"], stamp


class HttpError(RuntimeError):
    pass


class HttpClient:
    """Disk-cached HTTP GET with per-host pacing, bounded retries and a TTL.

    ``max_age`` (seconds, None = never expire) is what makes a scheduled
    rebuild actually refresh instead of re-reading yesterday's bytes. Every
    upstream URL here is *fixed* - danjuan is ``?day=all``, csindex pins
    ``endDate=20500101``, sina pins ``datalen=6000`` - so a cache key never
    changes and an untimed cache would serve the same response forever.

    When a TTL-expired entry cannot be refreshed, the old bytes are returned
    and the URL is recorded in ``stale_urls``: degrading to slightly old data
    beats silently dropping a whole PE series from the page.

    A host that fails ``breaker_after`` times in a row is treated as down for
    the rest of the run: without this, a WAF-blocked upstream costs a full
    retry-and-backoff cycle (~22s) on every single index, turning a 2-minute
    rebuild into a 15-minute one for data we already have snapshotted.
    """

    def __init__(self, *, min_interval: float = 0.7, timeout: float = 25.0,
                 retries: int = 4, offline: bool = False, logger=None,
                 breaker_after: int = 3, max_age: float | None = None):
        self.min_interval = min_interval
        self.timeout = timeout
        self.retries = retries
        self.offline = offline
        self.log = logger or logging.getLogger("petrace")
        self.breaker_after = breaker_after
        self.max_age = max_age
        self._last: dict[str, float] = {}
        self._fails: dict[str, int] = {}
        self._down: set[str] = set()
        self._session = requests.Session()
        self._session.headers.update(DEFAULT_HEADERS)
        self.stats = {"hit": 0, "miss": 0, "error": 0, "skipped": 0, "stale": 0}
        # urls served from an expired cache entry because the refresh failed
        self.stale_urls: list[str] = []

    # ---------------------------------------------------------------- cache
    @staticmethod
    def _key(url: str) -> str:
        return hashlib.sha1(url.encode("utf-8")).hexdigest()

    def _cache_path(self, url: str) -> Path:
        k = self._key(url)
        return CACHE_DIR / k[:2] / f"{k}.json"

    def _read_cache(self, url: str):
        p = self._cache_path(url)
        if not p.exists():
            return None
        try:
            with p.open("r", encoding="utf-8") as f:
                rec = json.load(f)
        except Exception:
            return None
        if rec.get("url") != url:
            return None
        return rec

    def _write_cache(self, url: str, text: str) -> None:
        p = self._cache_path(url)
        p.parent.mkdir(parents=True, exist_ok=True)
        rec = {"url": url, "fetched_at": time.time(), "text": text}
        tmp = p.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(rec, f, ensure_ascii=False)
        os.replace(tmp, p)

    # ------------------------------------------------------------- fetching
    def _pace(self, host: str) -> None:
        last = self._last.get(host)
        if last is not None:
            wait = self.min_interval - (time.time() - last)
            if wait > 0:
                time.sleep(wait)
        self._last[host] = time.time()

    def get_text(self, url: str, *, headers=None, refresh: bool = False) -> str:
        # Read the cache even under --refresh: not to serve as a hit, but so a
        # failed re-fetch can still degrade to the previous good response.
        rec = self._read_cache(url)
        fallback, fallback_age = None, 0.0
        if rec is not None:
            fallback = rec["text"]
            fallback_age = time.time() - float(rec.get("fetched_at") or 0)
            if not refresh and (self.max_age is None or fallback_age <= self.max_age):
                self.stats["hit"] += 1
                return rec["text"]

        if self.offline:
            if fallback is not None:
                self.stats["stale"] += 1
                self.stale_urls.append(url)
                return fallback
            raise HttpError(f"offline mode and no cache entry for {url}")

        host = urlsplit(url).netloc
        if host in self._down:
            if fallback is not None:
                self.stats["stale"] += 1
                self.stale_urls.append(url)
                return fallback
            self.stats["skipped"] += 1
            raise HttpError(f"host {host} marked down ({self.breaker_after} "
                            f"consecutive failures); no cache entry for {url}")

        last_err = None
        for attempt in range(self.retries):
            self._pace(host)
            try:
                r = self._session.get(url, headers=headers, timeout=self.timeout,
                                      verify=False)
                if r.status_code == 200:
                    self._write_cache(url, r.text)
                    self.stats["miss"] += 1
                    self._fails.pop(host, None)
                    return r.text
                last_err = f"HTTP {r.status_code}"
            except Exception as e:
                last_err = f"{type(e).__name__}: {str(e)[:120]}"
            time.sleep(min(1.5 * (2 ** attempt), 12.0))
        self.stats["error"] += 1
        fails = self._fails[host] = self._fails.get(host, 0) + 1
        if fails >= self.breaker_after:
            self._down.add(host)
            self.log.warning("host %s unreachable x%d; skipping it for this run",
                             host, fails)
        if fallback is not None:
            self.log.warning("refresh failed for %s (cached %.1fh ago); "
                             "serving the stale copy", url, fallback_age / 3600.0)
            self.stats["stale"] += 1
            self.stale_urls.append(url)
            return fallback
        raise HttpError(f"GET failed after {self.retries} tries: {url} :: {last_err}")

    def get_json(self, url: str, *, headers=None, refresh: bool = False):
        return json.loads(self.get_text(url, headers=headers, refresh=refresh))
