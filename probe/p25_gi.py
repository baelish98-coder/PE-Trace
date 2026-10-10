# -*- coding: utf-8 -*-
"""p25 - gi.finance.sina.com.cn/hq/daily raw endpoint for all 20 global indices."""
import io
import json
import sys
import time

sys.path.insert(0, r"C:\Users\Administrator\Documents\dsh-workplace\fund-PETrace")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import requests  # noqa: E402
import urllib3  # noqa: E402

urllib3.disable_warnings()
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
OUT = {}

from akshare.index.cons import index_global_sina_symbol_map as M  # noqa: E402

print("########## A. raw gi.finance.sina.com.cn/hq/daily")
for cn, code in M.items():
    try:
        r = requests.get("https://gi.finance.sina.com.cn/hq/daily",
                         params={"symbol": code, "num": "10000"},
                         headers={"User-Agent": UA}, timeout=25, verify=False)
        j = r.json()
        data = (j.get("result") or {}).get("data") or []
        if data:
            rec = {"code": code, "n": len(data), "first": data[0]["d"],
                   "last": data[-1]["d"], "lastclose": data[-1]["c"]}
            print(f"  {cn:26s} {code:9s} n={len(data):6d} {data[0]['d']} -> {data[-1]['d']} c={data[-1]['c']}")
        else:
            rec = {"code": code, "n": 0, "resp": json.dumps(j, ensure_ascii=False)[:130]}
            print(f"  {cn:26s} {code:9s} EMPTY {rec['resp']}")
        OUT[code] = rec
    except Exception as e:
        print(f"  {cn:26s} {code:9s} ERR {type(e).__name__}: {str(e)[:80]}")
        OUT[code] = {"error": f"{type(e).__name__}: {str(e)[:80]}"}
    time.sleep(1.0)

print("\n########## B. weekly/monthly variants on the same endpoint")
for code in ["DAX", "UKX", "NKY", "SX5E"]:
    for extra in ({}, {"type": "week"}, {"type": "month"}, {"period": "week"}):
        try:
            p = {"symbol": code, "num": "10000"}
            p.update(extra)
            r = requests.get("https://gi.finance.sina.com.cn/hq/daily", params=p,
                             headers={"User-Agent": UA}, timeout=20, verify=False)
            j = r.json()
            data = (j.get("result") or {}).get("data") or []
            if data:
                print(f"  {code:5s} {extra} n={len(data)} {data[0]['d']} -> {data[-1]['d']}")
            else:
                print(f"  {code:5s} {extra} EMPTY")
        except Exception as e:
            print(f"  {code:5s} {extra} ERR {type(e).__name__}")
        time.sleep(0.8)

with open(r"C:\Users\Administrator\Documents\dsh-workplace\fund-PETrace\probe\p25_gi.json",
          "w", encoding="utf-8") as f:
    json.dump(OUT, f, ensure_ascii=False, indent=1)
print("\nwrote probe/p25_gi.json")
