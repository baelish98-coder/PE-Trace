# -*- coding: utf-8 -*-
"""p26 - push gi.finance.sina.com.cn/hq/daily for deeper history + params."""
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


def daily(name, params):
    try:
        r = requests.get("https://gi.finance.sina.com.cn/hq/daily", params=params,
                         headers={"User-Agent": UA}, timeout=25, verify=False)
        j = r.json()
        res = j.get("result") or {}
        data = res.get("data") or []
        rec = {"params": params, "status": r.status_code, "n": len(data),
               "keys": sorted(res.keys())}
        if data:
            rec.update({"first": data[0]["d"], "last": data[-1]["d"],
                        "row0": data[0]})
        else:
            rec["body"] = json.dumps(j, ensure_ascii=False)[:200]
        OUT[name] = rec
        print(f"  {name:34s} {json.dumps(rec, ensure_ascii=False)[:300]}")
    except Exception as e:
        OUT[name] = {"error": f"{type(e).__name__}: {str(e)[:90]}"}
        print(f"  {name:34s} ERR {type(e).__name__} {str(e)[:80]}")
    time.sleep(1.1)


print("########## A. num variants (DAX)")
for n in ["1000", "2000", "3000", "5000", "10000", "20000", "999999"]:
    daily(f"num_{n}", {"symbol": "DAX", "num": n})

print("\n########## B. date params")
for name, p in [
    ("start_end", {"symbol": "DAX", "num": "10000", "start": "2005-01-01", "end": "2026-10-09"}),
    ("from_to", {"symbol": "DAX", "num": "10000", "from": "2005-01-01", "to": "2026-10-09"}),
    ("begin", {"symbol": "DAX", "num": "10000", "begin": "2005-01-01"}),
    ("page2", {"symbol": "DAX", "num": "1000", "page": "2"}),
    ("p2", {"symbol": "DAX", "num": "1000", "p": "2"}),
    ("offset", {"symbol": "DAX", "num": "1000", "offset": "1000"}),
]:
    daily(name, p)

print("\n########## C. alternate sina global endpoints")
for name, url, p in [
    ("gi_kline", "https://gi.finance.sina.com.cn/hq/kline", {"symbol": "DAX", "num": "10000"}),
    ("gi_daily2", "https://gi.finance.sina.com.cn/hq/daily2", {"symbol": "DAX", "num": "10000"}),
    ("gi_history", "https://gi.finance.sina.com.cn/hq/history", {"symbol": "DAX", "num": "10000"}),
    ("gi_daily_nover", "https://gi.finance.sina.com.cn/hq/daily", {"symbol": "DAX"}),
    ("gi_daily_post", "https://gi.finance.sina.com.cn/hq/daily", {"symbol": "DAX", "num": "10000", "type": "day"}),
]:
    try:
        r = requests.get(url, params=p, headers={"User-Agent": UA}, timeout=20, verify=False)
        rec = {"status": r.status_code, "len": len(r.content), "body": r.text[:170]}
        OUT[name] = rec
        print(f"  {name:20s} {json.dumps(rec, ensure_ascii=False)[:250]}")
    except Exception as e:
        print(f"  {name:20s} ERR {type(e).__name__} {str(e)[:70]}")
    time.sleep(1.2)

print("\n########## D. eastmoney health again")
for i in range(2):
    try:
        r = requests.get("https://push2his.eastmoney.com/api/qt/stock/kline/get"
                         "?secid=100.GDAXI&fields1=f1&fields2=f51,f53&klt=101&fqt=1&beg=0&end=20500101",
                         headers={"User-Agent": UA}, timeout=12, verify=False)
        print(f"  em{i}: {r.status_code} {len(r.content)}")
        break
    except Exception as e:
        print(f"  em{i}: ERR {type(e).__name__}")
    time.sleep(5)

with open(r"C:\Users\Administrator\Documents\dsh-workplace\fund-PETrace\probe\p26_gi2.json",
          "w", encoding="utf-8") as f:
    json.dump(OUT, f, ensure_ascii=False, indent=1)
print("\nwrote probe/p26_gi2.json")
