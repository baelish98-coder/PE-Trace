# -*- coding: utf-8 -*-
"""Round 10: price proxies for the last two HK indices without a price feed.

SPHCMSHP (香港中小) and HKHSSCNE (香港新经济) publish a danjuan PE weekly but
have no free index price feed.  Look for an ETF that tracks something close.

Run: python probe/p37_hk_proxy.py
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from petrace.core import HttpClient, setup_logging  # noqa: E402
from petrace import sources  # noqa: E402

OUT = ROOT / "probe" / "p37_hk_proxy.json"

CANDIDATES = [
    ("sz159920", "sina_cn"), ("sh513660", "sina_cn"), ("sh510900", "sina_cn"),
    ("sz159954", "sina_cn"), ("sh513630", "sina_cn"), ("sz159850", "sina_cn"),
    ("sz159892", "sina_cn"), ("sh513330", "sina_cn"), ("sz159605", "sina_cn"),
    ("sh513050", "sina_cn"), ("sz159607", "sina_cn"), ("sh513230", "sina_cn"),
    ("sz159740", "sina_cn"), ("sh513090", "sina_cn"), ("sz159792", "sina_cn"),
    ("sh513160", "sina_cn"), ("sz159687", "sina_cn"), ("sh513020", "sina_cn"),
    ("sz159567", "sina_cn"), ("sh513130", "sina_cn"),
    ("hkHSTECH", "tencent"), ("hkHSCEI", "tencent"), ("hkHSI", "tencent"),
]


def main() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")
    log = setup_logging(verbose=False)
    http = HttpClient(min_interval=0.8, logger=log)
    out = {}
    for sym, kind in CANDIDATES:
        try:
            if kind == "sina_cn":
                rows = sources.sina_cn_kline(http, sym)
            else:
                rows = sources.tencent_kline(http, sym, period="day", count=2000)
        except Exception as e:                              # noqa: BLE001
            print(f"  {sym:12s} ERR  {type(e).__name__}: {str(e)[-40:]}")
            continue
        rec = {"kind": kind, "n": len(rows)}
        if rows:
            rec.update(first=rows[0]["date"], last=rows[-1]["date"])
            print(f"  {sym:12s} OK   n={rec['n']:5d} {rec['first']}→{rec['last']}")
        else:
            print(f"  {sym:12s} EMPTY")
        out[sym] = rec
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("wrote", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
