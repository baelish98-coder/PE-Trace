# -*- coding: utf-8 -*-
"""
Warm the legulegu series cache.

legulegu (via akshare's stock_index_pe_lg) serves 504 / 429 in bursts for hours
at a time. The build reads cache/legulegu/<symbol>.json as a fallback, so this
script walks every configured symbol slowly and keeps whatever succeeds.

Usage: python -m tools.warm_legulegu [--wait 45] [--rounds 3]
"""
from __future__ import annotations

import argparse
import io
import sys
import time

from petrace import sources, universe
from petrace.build import _legulegu_cache_path
from petrace.core import read_json, write_json, ensure_dirs


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wait", type=float, default=45.0,
                    help="seconds between symbols (default 45)")
    ap.add_argument("--rounds", type=int, default=2)
    args = ap.parse_args(argv)
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")
    ensure_dirs()

    symbols = [x["legulegu"] for x in universe.INDICES if x.get("legulegu")]
    todo = list(symbols)
    for rnd in range(1, args.rounds + 1):
        if not todo:
            break
        print(f"\n=== round {rnd}: {len(todo)} symbol(s) still missing ===")
        still = []
        for i, sym in enumerate(todo):
            if i:
                time.sleep(args.wait)
            try:
                rows = sources.legulegu_pe(sym)
            except Exception as e:                     # noqa: BLE001
                print(f"  {sym:8s} FAIL {type(e).__name__}: {str(e)[-60:]}")
                still.append(sym)
                continue
            if not rows:
                print(f"  {sym:8s} empty (source has no such index)")
                continue
            write_json(_legulegu_cache_path(sym),
                       {"symbol": sym, "fetched_at": time.time(), "rows": rows})
            print(f"  {sym:8s} OK n={len(rows)} {rows[0]['date']}→{rows[-1]['date']}")
        todo = still

    print("\n--- cache status ---")
    for sym in symbols:
        rec = read_json(_legulegu_cache_path(sym))
        if rec and rec.get("rows"):
            stamp = time.strftime("%Y-%m-%d %H:%M", time.localtime(rec["fetched_at"]))
            print(f"  {sym:8s} cached n={len(rec['rows']):4d}  from {stamp}")
        else:
            print(f"  {sym:8s} MISSING")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
