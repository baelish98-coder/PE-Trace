# -*- coding: utf-8 -*-
"""Probe HISTORY endpoints: danjuan, eniu, csindex, legulegu."""
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import requests
requests.packages.urllib3.disable_warnings()

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
      "Accept": "application/json, text/plain, */*"}


def get(url, **kw):
    return requests.get(url, headers=UA, timeout=20, verify=False, **kw)


# ---------- DANJUAN ----------
print("=" * 72)
print("### DANJUAN index list + pe history")
try:
    r = get("https://danjuanfunds.com/djapi/index_eva/dj")
    j = r.json()
    items = (j.get("data") or {}).get("items") or []
    print("  list status", r.status_code, "n=", len(items))
    for it in items[:40]:
        print("   ", it.get("index_code"), it.get("name"), it.get("pe"), it.get("pe_percentile"))
except Exception as e:
    print("  list FAIL", str(e)[:200])

for code in ["SH000300", "NDX", "GDAXI", "SPX"]:
    for path in [f"https://danjuanfunds.com/djapi/index_eva/pe_history/{code}",
                 f"https://danjuanfunds.com/djapi/index_eva/pe_history/{code}?day=all",
                 f"https://danjuanfunds.com/djapi/index_eva/pe/{code}"]:
        try:
            r = get(path)
            t = r.text
            print(f"  pehist {code} {path.split('/djapi')[1][:46]} -> {r.status_code} len={len(t)} {t[:150]}")
        except Exception as e:
            print(f"  pehist {code} FAIL {str(e)[:70]}")
print()

# ---------- ENIU (亿牛网) ----------
print("=" * 72)
print("### ENIU")
for code in ["sh000300", "sz399006"]:
    for path in [f"https://eniu.com/chart/peh/{code}/all",
                 f"https://eniu.com/chart/peq/{code}/all",
                 f"https://eniu.com/chart/pbh/{code}/all"]:
        try:
            r = get(path)
            print(f"  {path} -> {r.status_code} len={len(r.text)} {r.text[:220]}")
        except Exception as e:
            print(f"  {path} FAIL {str(e)[:70]}")
print()

# ---------- CSINDEX official API ----------
print("=" * 72)
print("### CSINDEX api")
cands = [
    "https://www.csindex.com.cn/csindex-home/indexInfo/index-detail/000300",
    "https://www.csindex.com.cn/csindex-home/perf/index-perf-history?indexCode=000300",
    "https://www.csindex.com.cn/csindex-home/index-list/query-index-item?indexCode=000300",
]
for u in cands:
    try:
        r = get(u)
        print(f"  {u[:88]} -> {r.status_code} len={len(r.text)} {r.text[:160]}")
    except Exception as e:
        print(f"  {u[:88]} FAIL {str(e)[:70]}")
print()

# ---------- LEGULEGU daily pe ----------
print("=" * 72)
print("### LEGULEGU api")
for u in ["https://legulegu.com/api/stockdata/index-basic-pe?indexCode=000300",
          "https://legulegu.com/stockdata/index-basic-pe?indexCode=000300",
          "https://legulegu.com/stockdata/globalindex-pe"]:
    try:
        r = get(u)
        print(f"  {u[:80]} -> {r.status_code} len={len(r.text)} {r.text[:180]}")
    except Exception as e:
        print(f"  {u[:80]} FAIL {str(e)[:70]}")
