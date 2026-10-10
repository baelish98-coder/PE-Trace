# -*- coding: utf-8 -*-
"""Round 4: pin down csindex `peg` semantics, and chase the last uncovered codes.

Verification plan for `peg`:
  * CSI300 PE-TTM well-known levels: 2007-10 ~45 (peak), 2015-06 ~18.5,
    2018-12 ~10.2, 2020-03 ~11.5, 2024-02 ~10.6.
  * If csindex peg lands near those, it is PE (TTM-ish).  If it lands near
    0.5-2 it is the PEG ratio and must not be used as PE.
  * Year-by-year csindex peg vs danjuan PE ratio.

Coverage chase:
  * cnindex.com.cn (国证/深证 official) for 399673 创业板50 and 399xxx peers
  * HK customs HSFML25 / SPHCMSHP / HKHSSCNE via tencent hk codes
  * 716567 MSCI China / 935600 MSCI India

Run: python probe/p31_csindex2.py
"""
from __future__ import annotations

import io
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from petrace import sources                        # noqa: E402
from petrace.core import HttpClient, setup_logging  # noqa: E402

OUT = ROOT / "probe" / "p31_csindex2.json"
HDR = {"Referer": "https://www.csindex.com.cn/"}
PERF = "https://www.csindex.com.cn/csindex-home/perf/index-perf"


def jdefault(o):
    return str(o)


def main() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")
    log = setup_logging(verbose=False)
    http = HttpClient(min_interval=1.2, logger=log)
    out: dict = {}

    # ---- 1. peg at well-known PE dates -----------------------------------
    print("=== 1. csindex peg at known CSI300 PE dates ===")
    try:
        obj = http.get_json(f"{PERF}?indexCode=000300&startDate=20040101&endDate=20261010",
                            headers=HDR)
        rows = obj.get("data") or []
        by_date = {r["tradeDate"]: r for r in rows}
        known = {"20071016": "CSI300 PE-TTM peak ~45",
                 "20150612": "2015 bull peak ~18.5",
                 "20181228": "2018 bear trough ~10.2",
                 "20200323": "COVID trough ~11.5",
                 "20240205": "2024 trough ~10.6",
                 "20211026": "2021 peak ~13.5"}
        out["known_dates"] = {}
        for d, desc in known.items():
            # nearest trading day on or before
            cand = [k for k in by_date if k <= d]
            k = max(cand) if cand else None
            rec = by_date.get(k) if k else None
            out["known_dates"][d] = {"desc": desc, "actual_date": k,
                                     "peg": rec.get("peg") if rec else None,
                                     "close": rec.get("close") if rec else None}
            print(f"  {d} ({desc:28s}) -> {k}  peg={rec.get('peg') if rec else None}"
                  f"  close={rec.get('close') if rec else None}")
        # min / max peg across history
        pegs = [r["peg"] for r in rows if r.get("peg") is not None]
        out["peg_range"] = {"n": len(pegs), "min": min(pegs), "max": max(pegs),
                            "mean": round(sum(pegs) / len(pegs), 3)}
        print(f"  peg range over {len(pegs)} days: {min(pegs)} .. {max(pegs)} "
              f"mean={out['peg_range']['mean']}")
    except Exception as e:                                       # noqa: BLE001
        out["known_dates"] = {"error": f"{type(e).__name__}: {str(e)[:90]}"}
        print("  FAIL", e)

    # ---- 2. year-by-year ratio vs danjuan --------------------------------
    print("\n=== 2. csindex peg / danjuan PE by year (000300) ===")
    try:
        dj = {r["date"].replace("-", ""): r["pe"] for r in sources.danjuan_pe(http, "SH000300")}
        buckets = defaultdict(list)
        for r in rows:
            k = r["tradeDate"]
            if k in dj and r.get("peg"):
                buckets[k[:4]].append(dj[k] / r["peg"])
        out["by_year"] = {}
        for y in sorted(buckets):
            v = buckets[y]
            m = sum(v) / len(v)
            out["by_year"][y] = {"n": len(v), "mean": round(m, 4),
                                 "min": round(min(v), 4), "max": round(max(v), 4)}
            print(f"  {y}  n={len(v):3d}  danjuan/peg mean={m:.4f} "
                  f"[{min(v):.4f},{max(v):.4f}]")
    except Exception as e:                                       # noqa: BLE001
        out["by_year"] = {"error": f"{type(e).__name__}: {str(e)[:90]}"}
        print("  FAIL", e)

    # ---- 3. cnindex (国证/深证) for 399673 -------------------------------
    print("\n=== 3. cnindex.com.cn for 399673 创业板50 ===")
    cn = [
        ("cnindex-perf", "https://www.cnindex.com.cn/sample-detail/index-performance?indexcode=399673"),
        ("cnindex-api", "https://www.cnindex.com.cn/index/indexBasicInfo?indexCode=399673"),
        ("cnindex-hist", "https://www.cnindex.com.cn/index/indexHistory?indexCode=399673"),
        ("cnindex-trend", "https://www.cnindex.com.cn/sample-detail/index-trend?indexcode=399673"),
    ]
    for label, url in cn:
        try:
            txt = http.get_text(url, headers={"Referer": "https://www.cnindex.com.cn/"})
            out[f"cnindex:{label}"] = {"len": len(txt), "head": txt[:220]}
            print(f"  {label:16s} len={len(txt):7d} {txt[:110]}")
        except Exception as e:                                   # noqa: BLE001
            out[f"cnindex:{label}"] = {"error": f"{type(e).__name__}: {str(e)[:70]}"}
            print(f"  {label:16s} FAIL {type(e).__name__} {str(e)[:60]}")
        time.sleep(1.0)

    # ---- 4. HK customs via tencent ---------------------------------------
    print("\n=== 4. HK customs on tencent ===")
    for code in ("hkHSFML25", "hkSPHCMSHP", "hkHSSCNE", "hkHSSCTECH",
                 "hkHSTECH", "hkHSCEI", "hkHSI", "hkHSNE", "hkHSSCHK",
                 "hkHSSCBI", "hkHSSCCSI"):
        try:
            rows = sources.tencent_kline(http, code, period="week", count=10)
            out[f"hk:{code}"] = {"n": len(rows), "last": rows[-1]["date"] if rows else None}
            print(f"  {code:14s} week n={len(rows)}")
        except Exception as e:                                   # noqa: BLE001
            out[f"hk:{code}"] = {"error": f"{type(e).__name__}"}
            print(f"  {code:14s} week FAIL {type(e).__name__}")
        time.sleep(1.2)

    # ---- 5. MSCI proxies -------------------------------------------------
    print("\n=== 5. MSCI China / India proxies ===")
    for code in ("MCHI", "KWEB", "FXI", "INDA", "EPI", "SMIN"):
        try:
            rows = sources.sina_us_kline(http, code)
            out[f"us:{code}"] = {"n": len(rows),
                                 "first": rows[0]["date"] if rows else None,
                                 "last": rows[-1]["date"] if rows else None}
            print(f"  sina_us {code:6s} n={len(rows):5d}")
        except Exception as e:                                   # noqa: BLE001
            out[f"us:{code}"] = {"error": f"{type(e).__name__}"}
            print(f"  sina_us {code:6s} FAIL {type(e).__name__}")
        time.sleep(1.2)

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=jdefault),
                   encoding="utf-8")
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
