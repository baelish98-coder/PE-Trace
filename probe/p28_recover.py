# -*- coding: utf-8 -*-
"""Recover the 3 only-legulegu PE indices, and find prices for the 11
PE-without-price indices.

Run: python probe/p28_recover.py
"""
from __future__ import annotations

import io
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from petrace import sources                      # noqa: E402
from petrace.core import HttpClient, setup_logging  # noqa: E402

OUT = ROOT / "probe" / "p28_recover.json"


def main() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")
    log = setup_logging(verbose=False)
    http = HttpClient(min_interval=1.2, logger=log)
    out: dict = {"legulegu": {}, "csindex": {}, "price": {}, "tencent": {}}

    # ---- 1. legulegu retry for the 3 only-legulegu indices ----------------
    print("=== legulegu retry ===")
    for sym in ("上证380", "中证800", "创业板50"):
        try:
            rows = sources.legulegu_pe(sym)
            out["legulegu"][sym] = {"n": len(rows),
                                    "first": rows[0]["date"] if rows else None,
                                    "last": rows[-1]["date"] if rows else None}
            print(f"  {sym}: n={len(rows)}")
        except Exception as e:                                   # noqa: BLE001
            out["legulegu"][sym] = {"error": f"{type(e).__name__}: {str(e)[-70:]}"}
            print(f"  {sym}: FAIL {type(e).__name__} {str(e)[-60:]}")
        time.sleep(8)

    # ---- 2. CSIndex official valuation for the 3 --------------------------
    print("\n=== csindex stock_zh_index_value_csindex ===")
    try:
        import akshare as ak
    except Exception as e:                                       # noqa: BLE001
        print("  akshare import failed:", e)
        ak = None
    if ak:
        for code in ("000009", "000906", "399673", "000300"):
            try:
                df = ak.stock_zh_index_value_csindex(symbol=code)
                out["csindex"][code] = {"rows": len(df),
                                        "cols": list(df.columns)[:8],
                                        "head": df.head(2).to_dict("records")}
                print(f"  {code}: n={len(df)} cols={list(df.columns)[:6]}")
            except Exception as e:                               # noqa: BLE001
                out["csindex"][code] = {"error": f"{type(e).__name__}: {str(e)[:80]}"}
                print(f"  {code}: FAIL {type(e).__name__} {str(e)[:70]}")
            time.sleep(4)

    # ---- 3. prices for the 11 PE-only indices ----------------------------
    # sina A-share convention: sh000300 / sz399006.  CSI codes are tried both
    # bare and with the sh/sz prefix, plus tencent equivalents.
    print("\n=== price probes (sina_cn / tencent) ===")
    a_prefix = ["sh716567", "sh930652", "sh931087", "sz399673", "sh000009",
                "sh000906"]
    for code in ["sh930652", "sh931087", "sh716567", "shh11136", "sh950090",
                 "sh000009", "sh000906", "sz399673"]:
        try:
            rows = sources.sina_cn_kline(http, code, datalen=10)
            out["price"][f"sina_cn:{code}"] = {"n": len(rows),
                                               "last": rows[-1]["date"] if rows else None}
            print(f"  sina_cn {code:10s} n={len(rows)}")
        except Exception as e:                                   # noqa: BLE001
            out["price"][f"sina_cn:{code}"] = {"error": f"{type(e).__name__}"}
            print(f"  sina_cn {code:10s} FAIL {type(e).__name__}")
        time.sleep(1.5)

    for code, period in [("sh930652", "day"), ("sh931087", "day"),
                         ("sh716567", "day"), ("sz399673", "day"),
                         ("hkHSTECH", "week")]:
        try:
            rows = sources.tencent_kline(http, code, period=period, count=10)
            key = f"tencent:{code}:{period}"
            out["tencent"][key] = {"n": len(rows),
                                   "last": rows[-1]["date"] if rows else None}
            print(f"  tencent {code:10s} {period:5s} n={len(rows)}")
        except Exception as e:                                   # noqa: BLE001
            out["tencent"][f"tencent:{code}:{period}"] = {"error": f"{type(e).__name__}"}
            print(f"  tencent {code:10s} {period:5s} FAIL {type(e).__name__}")
        time.sleep(1.5)

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
