# -*- coding: utf-8 -*-
"""Round 2: deeper PE for the 3 only-legulegu indices, and price/PE history
for the 11 PE-without-price indices.

Leads:
  A. csindex.com.cn official perf API (deep daily PE for CSI codes)
  B. csindex home JSON endpoints
  C. ETF proxies via sina/tencent (CSI customs are tracked by ETFs)
  D. sina/tencent for CSI codes with alternate prefixes
  E. HK customs (HSFML25 / SPHCMSHP / HKHSSCNE) via tencent hk codes
  F. S&P style indices (SPACEVCP/CSPSADRP/SPCQVCP) via US ETF proxies

Run: python probe/p29_deep2.py
"""
from __future__ import annotations

import io
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from petrace import sources                        # noqa: E402
from petrace.core import HttpClient, setup_logging  # noqa: E402

OUT = ROOT / "probe" / "p29_deep2.json"


def jdefault(o):
    return str(o)


def main() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")
    log = setup_logging(verbose=False)
    http = HttpClient(min_interval=1.2, logger=log)
    out: dict = {}

    # ---- A/B: CSIndex official APIs --------------------------------------
    print("=== A. csindex perf API ===")
    for code in ("930652", "931087", "716567", "H11136", "000009", "000906"):
        url = ("https://www.csindex.com.cn/csindex-home/perf/index-perf"
               f"?indexCode={code}&startDate=20050101&endDate=20261010")
        try:
            obj = http.get_json(url, headers={"Referer": "https://www.csindex.com.cn/"})
            data = (obj or {}).get("data")
            n = len(data) if isinstance(data, list) else None
            out[f"csindex_perf:{code}"] = {"n": n,
                                           "keys": list(data[0].keys())[:14] if n else None,
                                           "first": data[0] if n else None,
                                           "last": data[-1] if n else None}
            print(f"  {code:8s} n={n} keys={list(data[0].keys())[:8] if n else None}")
        except Exception as e:                                   # noqa: BLE001
            out[f"csindex_perf:{code}"] = {"error": f"{type(e).__name__}: {str(e)[:90]}"}
            print(f"  {code:8s} FAIL {type(e).__name__} {str(e)[:70]}")
        time.sleep(1.5)

    print("\n=== B. csindex home JSON variants ===")
    for label, url in [
        ("indexInfo", "https://www.csindex.com.cn/csindex-home/indexInfo/index-basic-info?indexCode=930652"),
        ("perfSimple", "https://www.csindex.com.cn/csindex-home/perf/index-perf?indexCode=930652"),
        ("valuation", "https://www.csindex.com.cn/csindex-home/indexInfo/index-valuation?indexCode=930652"),
    ]:
        try:
            obj = http.get_json(url, headers={"Referer": "https://www.csindex.com.cn/"})
            s = json.dumps(obj, ensure_ascii=False, default=jdefault)
            out[f"csindex_{label}"] = {"len": len(s), "head": s[:300]}
            print(f"  {label:12s} len={len(s)} {s[:120]}")
        except Exception as e:                                   # noqa: BLE001
            out[f"csindex_{label}"] = {"error": f"{type(e).__name__}: {str(e)[:90]}"}
            print(f"  {label:12s} FAIL {type(e).__name__} {str(e)[:60]}")
        time.sleep(1.2)

    # ---- C: ETF proxies (price) ------------------------------------------
    print("\n=== C. ETF proxies via sina_cn (price) ===")
    etfs = {
        "sh513050": "中概互联ETF(中国互联CSIH11136)",
        "sh159920": "恒生ETF",
        "sz159920": "恒生ETF(深)",
        "sh510900": "H股ETF",
        "sh513660": "恒生中国企业ETF",
        "sh515000": "科技ETF(科技龙头)",
        "sh515070": "AI ETF",
        "sz159939": "信息技术ETF(中证电子?)",
        "sh159939": "信息技术ETF",
        "sh512760": "芯片ETF",
        "sh512480": "半导体ETF",
        "sh159801": "芯片ETF(深)",
        "sz159801": "芯片ETF",
    }
    for code, desc in etfs.items():
        try:
            rows = sources.sina_cn_kline(http, code, datalen=10)
            out[f"etf_sina:{code}"] = {"desc": desc, "n": len(rows),
                                       "last": rows[-1]["date"] if rows else None}
            print(f"  {code:10s} n={len(rows):4d}  {desc}")
        except Exception as e:                                   # noqa: BLE001
            out[f"etf_sina:{code}"] = {"desc": desc, "error": f"{type(e).__name__}"}
            print(f"  {code:10s} FAIL {type(e).__name__}  {desc}")
        time.sleep(1.2)

    # ---- D: CSI codes alternate prefixes ---------------------------------
    print("\n=== D. CSI/HK codes on tencent & sina, alternate forms ===")
    tries = [
        ("tencent", "sh000932", "day"), ("tencent", "sh000922", "day"),
        ("tencent", "hkHSI", "day"), ("tencent", "hkHSCEI", "day"),
        ("tencent", "hkHSTECH", "day"), ("tencent", "hkHSSCNE", "day"),
        ("tencent", "us.SPHQ", "week"), ("tencent", "us.SPLV", "week"),
        ("tencent", "us.SPHD", "week"), ("tencent", "us.SPY", "week"),
        ("tencent", "us.QUAL", "week"), ("tencent", "us.INDA", "week"),
        ("tencent", "us.EPW", "week"), ("tencent", "us.FXI", "week"),
        ("tencent", "us.KWEB", "week"), ("tencent", "us.MCHI", "week"),
        ("sina_us", "SPHQ", ""), ("sina_us", "SPLV", ""),
        ("sina_us", "SPHD", ""), ("sina_us", "QUAL", ""),
        ("sina_us", "INDA", ""), ("sina_us", "KWEB", ""),
        ("sina_us", "MCHI", ""), ("sina_us", "FXI", ""),
        ("sina_us", "EPW", ""),
    ]
    for kind, code, period in tries:
        key = f"{kind}:{code}:{period}"
        try:
            if kind == "tencent":
                rows = sources.tencent_kline(http, code, period=period, count=10)
            else:
                rows = sources.sina_us_kline(http, code)
            out[key] = {"n": len(rows), "last": rows[-1]["date"] if rows else None}
            print(f"  {key:28s} n={len(rows):5d}")
        except Exception as e:                                   # noqa: BLE001
            out[key] = {"error": f"{type(e).__name__}: {str(e)[:60]}"}
            print(f"  {key:28s} FAIL {type(e).__name__}")
        time.sleep(1.3)

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=jdefault),
                   encoding="utf-8")
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
