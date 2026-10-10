# -*- coding: utf-8 -*-
"""p23 - akshare global name table + global hist sina; EM recovery; DAX/India price."""
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

import akshare as ak  # noqa: E402

print("########## A. index_global_name_table")
try:
    t = ak.index_global_name_table()
    print(t.to_string()[:2500])
    OUT["name_table"] = t.to_dict("records")
    SYMS = list(t.iloc[:, 1]) if t.shape[1] > 1 else list(t.iloc[:, 0])
except Exception as e:
    print("ERR", type(e).__name__, str(e)[:150])
    SYMS = []

print("\n########## B. index_global_hist_sina for each symbol")
for s in SYMS:
    for attempt in range(2):
        try:
            df = ak.index_global_hist_sina(symbol=s)
            rec = {"shape": list(df.shape), "cols": list(df.columns),
                   "first": str(df.iloc[0, 0]), "last": str(df.iloc[-1, 0])}
            print(f"  {s:16s} -> {rec}")
            OUT[f"g_{s}"] = rec
            break
        except Exception as e:
            if attempt == 1:
                print(f"  {s:16s} -> ERR {type(e).__name__}: {str(e)[:80]}")
                OUT[f"g_{s}"] = {"error": f"{type(e).__name__}: {str(e)[:80]}"}
            time.sleep(1.5)

print("\n########## C. eastmoney health (single probe)")
for i in range(3):
    try:
        r = requests.get("https://push2his.eastmoney.com/api/qt/stock/kline/get"
                         "?secid=100.GDAXI&fields1=f1&fields2=f51,f53&klt=101&fqt=1"
                         "&beg=0&end=20500101",
                         headers={"User-Agent": UA}, timeout=15, verify=False)
        print(f"  try{i}: {r.status_code} len={len(r.content)} {r.text[:100]}")
        OUT[f"em_try{i}"] = {"status": r.status_code, "len": len(r.content)}
        break
    except Exception as e:
        print(f"  try{i}: ERR {type(e).__name__} {str(e)[:70]}")
        OUT[f"em_try{i}"] = {"error": type(e).__name__}
    time.sleep(8)

print("\n########## D. misc DAX/India price sources")
def get(name, url, show=180):
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=20, verify=False)
        rec = {"status": r.status_code, "len": len(r.content), "body": r.text[:show]}
    except Exception as e:
        rec = {"error": f"{type(e).__name__}: {str(e)[:90]}"}
    OUT[name] = rec
    print(f"  {name:26s} {json.dumps(rec, ensure_ascii=False)[:260]}")
    time.sleep(1.5)

get("sa_dax", "https://stockanalysis.com/quote/index/DAX/history/")
get("sa_dax_data", "https://stockanalysis.com/quote/index/DAX/__data.json")
get("wsj_dax", "https://www.wsj.com/market-data/quotes/index/DAX/historical-prices")
get("mw_dax", "https://www.marketwatch.com/investing/index/dax/downloaddatapartial"
              "?startdate=01/01/2016&enddate=10/09/2026&daterange=d30&frequency=p1d"
              "&csvdownload=true&downloadpartial=false&newdates=false")
get("tx_de_dax_hk", "https://web.ifzq.gtimg.cn/appstock/app/hkfqkline/get?param=deDAX,day,,,2000,qfq")

with open(r"C:\Users\Administrator\Documents\dsh-workplace\fund-PETrace\probe\p23_akglobal.json",
          "w", encoding="utf-8") as f:
    json.dump(OUT, f, ensure_ascii=False, indent=1)
print("\nwrote probe/p23_akglobal.json")
