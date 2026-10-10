# -*- coding: utf-8 -*-
"""Round 3: characterise the csindex-home/perf API.

Questions:
  1. What is `peg`?  (PE? PEG? static PE?)  Compare vs danjuan PE on overlap.
  2. Does it cover 399673 / 716567 / HK customs?
  3. Can startDate reach 2005 for the deep indices?
  4. Are there sibling endpoints carrying a real PE/PB/dividend field?

Run: python probe/p30_csindex.py
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

OUT = ROOT / "probe" / "p30_csindex.json"
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

    # ---- 1. peg vs danjuan PE for 000300 --------------------------------
    print("=== 1. peg semantics: csindex peg vs danjuan PE (000300) ===")
    try:
        obj = http.get_json(f"{PERF}?indexCode=000300&startDate=20161001&endDate=20261010",
                            headers=HDR)
        rows = obj.get("data") or []
        cs = {r["tradeDate"]: r.get("peg") for r in rows if r.get("peg") is not None}
        dj = {r["date"].replace("-", ""): r["pe"] for r in sources.danjuan_pe(http, "SH000300")}
        common = sorted(set(cs) & set(dj))
        ratios = [dj[k] / cs[k] for k in common if cs[k]]
        out["peg_vs_danjuan"] = {
            "cs_n": len(rows), "common": len(common),
            "ratio_mean": round(sum(ratios) / len(ratios), 4) if ratios else None,
            "ratio_min": round(min(ratios), 4) if ratios else None,
            "ratio_max": round(max(ratios), 4) if ratios else None,
            "samples": [{"d": k, "cs_peg": cs[k], "dj_pe": dj[k]} for k in common[-5:]],
        }
        print(f"  cs n={len(rows)} common={len(common)} ratio mean="
              f"{out['peg_vs_danjuan']['ratio_mean']} "
              f"[{out['peg_vs_danjuan']['ratio_min']},{out['peg_vs_danjuan']['ratio_max']}]")
        for s in out["peg_vs_danjuan"]["samples"]:
            print(f"    {s['d']}  cs.peg={s['cs_peg']:8.3f}  danjuan.pe={s['dj_pe']:8.3f}")
    except Exception as e:                                       # noqa: BLE001
        out["peg_vs_danjuan"] = {"error": f"{type(e).__name__}: {str(e)[:90]}"}
        print("  FAIL", e)

    # ---- 2. coverage of the problem codes --------------------------------
    print("\n=== 2. csindex perf coverage of problem codes ===")
    for code in ("399673", "716567", "930652", "931087", "H11136",
                 "000009", "000906", "000300", "000852", "H30533"):
        try:
            obj = http.get_json(f"{PERF}?indexCode={code}&startDate=20040101&endDate=20261010",
                                headers=HDR)
            data = obj.get("data") or []
            first = data[0] if data else None
            last = data[-1] if data else None
            rec = {"n": len(data),
                   "first": (first or {}).get("tradeDate"),
                   "last": (last or {}).get("tradeDate"),
                   "name": (first or {}).get("indexNameCnAll"),
                   "last_peg": (last or {}).get("peg"),
                   "last_close": (last or {}).get("close")}
            out[f"cov:{code}"] = rec
            print(f"  {code:8s} n={len(data):5d} {rec['first']}→{rec['last']} "
                  f"{rec['name']} peg={rec['last_peg']} close={rec['last_close']}")
        except Exception as e:                                   # noqa: BLE001
            out[f"cov:{code}"] = {"error": f"{type(e).__name__}: {str(e)[:80]}"}
            print(f"  {code:8s} FAIL {type(e).__name__} {str(e)[:60]}")
        time.sleep(1.2)

    # ---- 3. sibling endpoints for PE/PB/dividend ------------------------
    print("\n=== 3. sibling endpoints ===")
    cands = [
        ("perf-detail", "https://www.csindex.com.cn/csindex-home/perf/index-perf-detail?indexCode=000300"),
        ("index-valuation", "https://www.csindex.com.cn/csindex-home/indexInfo/index-valuation?indexCode=000300"),
        ("perf-pe", "https://www.csindex.com.cn/csindex-home/perf/index-pe?indexCode=000300"),
        ("index-pe", "https://www.csindex.com.cn/csindex-home/index/index-pe?indexCode=000300"),
        ("valuation-list", "https://www.csindex.com.cn/csindex-home/indexInfo/valuation/list?indexCode=000300"),
        ("indicator", "https://www.csindex.com.cn/csindex-home/indexInfo/index-indicator?indexCode=000300"),
    ]
    for label, url in cands:
        try:
            obj = http.get_json(url, headers=HDR)
            s = json.dumps(obj, ensure_ascii=False, default=jdefault)
            out[f"ep:{label}"] = {"url": url, "len": len(s), "head": s[:260]}
            print(f"  {label:16s} len={len(s):6d} {s[:130]}")
        except Exception as e:                                   # noqa: BLE001
            out[f"ep:{label}"] = {"url": url, "error": f"{type(e).__name__}: {str(e)[:70]}"}
            print(f"  {label:16s} FAIL {type(e).__name__} {str(e)[:60]}")
        time.sleep(1.0)

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=jdefault),
                   encoding="utf-8")
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
