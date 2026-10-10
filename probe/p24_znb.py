# -*- coding: utf-8 -*-
"""p24 - sina znb_* global index family: quote + history."""
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
REF = {"Referer": "https://finance.sina.com.cn/"}
OUT = {}


def get(name, url, headers=REF, show=170):
    h = {"User-Agent": UA}
    h.update(headers)
    try:
        r = requests.get(url, headers=h, timeout=20, verify=False)
        rec = {"status": r.status_code, "len": len(r.content), "body": r.text[:show]}
    except Exception as e:
        rec = {"error": f"{type(e).__name__}: {str(e)[:90]}"}
    OUT[name] = rec
    print(f"  {name:30s} {json.dumps(rec, ensure_ascii=False)[:270]}")
    time.sleep(1.3)
    return rec


print("########## A. sina znb_* quotes (which exist)")
CODES = ["UKX", "DAX", "CAC", "SX5E", "SWI20", "FTSEMIB", "AEX", "IBEX",
         "NKY", "KOSPI", "AS51", "TWJQ", "GSPTSE", "SENSEX", "MXX", "IBOV",
         "NZ250", "JCI", "CASE", "INDEXCF", "SPX", "DJI", "IXIC", "NDX"]
lst = ",".join(f"znb_{c}" for c in CODES)
get("znb_all_quotes", f"https://hq.sinajs.cn/list={lst}", show=2000)

print("\n########## B. sina znb_* history js")
for c in ["UKX", "DAX", "SX5E", "NKY", "KOSPI", "TWJQ", "AS51", "GSPTSE", "CAC"]:
    get(f"znb_klc_{c}",
        f"https://finance.sina.com.cn/realstock/company/znb_{c}/hisdata/klc_kl.js",
        show=120)

print("\n########## C. sina global index api")
for c in ["UKX", "DAX"]:
    get(f"sinaglobal_{c}",
        "https://stock.finance.sina.com.cn/globalIndex/api/jsonp_v2.php/"
        f"var%20a=/GlobalIndexService.getDailyK?symbol={c}&___qn=3", show=160)
    get(f"sinaglobal2_{c}",
        "https://stock.finance.sina.com.cn/globalIndex/api/jsonp.php/"
        f"var%20a=/GlobalIndexService.getDailyK?symbol={c}&___qn=3", show=160)

print("\n########## D. eastmoney retry (health)")
get("em_health",
    "https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=100.GDAXI"
    "&fields1=f1&fields2=f51,f53&klt=101&fqt=1&beg=0&end=20500101", show=100)

with open(r"C:\Users\Administrator\Documents\dsh-workplace\fund-PETrace\probe\p24_znb.json",
          "w", encoding="utf-8") as f:
    json.dump(OUT, f, ensure_ascii=False, indent=1)
print("\nwrote probe/p24_znb.json")
