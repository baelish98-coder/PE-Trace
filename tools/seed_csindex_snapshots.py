# -*- coding: utf-8 -*-
"""Seed the snapshot layer from whatever csindex data already sits in the HTTP
cache.  The live host is currently WAF-blocked, so the cache is the only copy.

Run: python tools/seed_csindex_snapshots.py
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from petrace.core import CACHE_DIR, load_snapshot, save_snapshot  # noqa: E402


def main() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")
    best: dict[str, list] = {}
    for p in CACHE_DIR.rglob("*.json"):
        if "snapshots" in p.parts:
            continue
        try:
            rec = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        url = rec.get("url", "")
        if "perf/index-perf" not in url:
            continue
        code = (parse_qs(urlsplit(url).query).get("indexCode") or [None])[0]
        if not code:
            continue
        try:
            data = json.loads(rec.get("text", "{}")).get("data")
        except Exception:
            continue
        if not isinstance(data, list) or not data:
            continue
        if len(data) > len(best.get(code, [])):
            best[code] = data

    print(f"codes with cached csindex data: {len(best)}")
    for code, rows in sorted(best.items()):
        prev, stamp = load_snapshot(f"csindex_{code}")
        if len(prev) >= len(rows):
            print(f"  {code:8s} keep existing snapshot n={len(prev)} ({stamp})")
            continue
        save_snapshot(f"csindex_{code}", rows)
        n_pe = sum(1 for r in rows if r.get("peg") not in (None, "", 0))
        d0, d1 = rows[0].get("tradeDate"), rows[-1].get("tradeDate")
        print(f"  {code:8s} seeded n={len(rows):5d} pe={n_pe:5d} {d0}→{d1}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
