# -*- coding: utf-8 -*-
"""Probe: danjuan granularity, price history sources, CDN availability."""
import sys, io, json, datetime
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import requests, akshare as ak
requests.packages.urllib3.disable_warnings()
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"}

print("### 1. danjuan granularity check (SH000300 last 12 ts)")
r = requests.get("https://danjuanfunds.com/djapi/index_eva/pe_history/SH000300?day=all",
                 headers=UA, timeout=25, verify=False)
g = r.json()["data"]["index_eva_pe_growths"]
for it in g[-12:]:
    print("   ", datetime.datetime.fromtimestamp(it["ts"]/1000, datetime.UTC).date(), it["pe"])
deltas = [(g[i+1]["ts"]-g[i]["ts"])/86400000 for i in range(len(g)-1)]
from collections import Counter
print("   spacing days counter:", Counter([round(d) for d in deltas]).most_common(8))
print()

print("### 2. danjuan index quote api")
for u in ["https://danjuanfunds.com/djapi/index_eva/detail/SH000300",
          "https://danjuanfunds.com/djapi/fund/index/quote/SH000300"]:
    try:
        r = requests.get(u, headers=UA, timeout=20, verify=False)
        print(f"  {u[-50:]} -> {r.status_code} {r.text[:260]}")
    except Exception as e:
        print(f"  FAIL {str(e)[:80]}")
print()

print("### 3. akshare A-share price history")
for fn, kw in [("stock_zh_index_daily", {"symbol": "sh000300"}),
               ("index_zh_a_hist", {"symbol": "000300", "period": "daily"})]:
    try:
        df = getattr(ak, fn)(**kw)
        print(f"  {fn}: shape={df.shape} cols={list(df.columns)}")
        print("   ", df.head(1).to_string()[:200], "|", df.tail(1).to_string()[:200])
    except Exception as e:
        print(f"  {fn} FAIL {str(e)[:120]}")
print()

print("### 4. global price history candidates")
for fn in ["index_global_hist_em"]:
    for sym in ["标普500", "纳斯达克100", "日经225"]:
        try:
            df = getattr(ak, fn)(symbol=sym)
            print(f"  {fn}/{sym}: shape={df.shape} {df.iloc[-1,0]}..{df.iloc[0,0]} cols={list(df.columns)}")
        except Exception as e:
            print(f"  {fn}/{sym} FAIL {str(e)[:90]}")
print()

print("### 5. CDN / offline asset availability")
for u in ["https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js",
          "https://unpkg.com/echarts@5/dist/echarts.min.js",
          "https://cdnjs.cloudflare.com/ajax/libs/echarts/5.5.0/echarts.min.js",
          "https://query1.finance.yahoo.com/v8/finance/chart/%5EGSPC?range=1mo&interval=1d",
          "https://stooq.com/q/d/l/?s=%5Espx&i=d"]:
    try:
        r = requests.get(u, headers=UA, timeout=20, verify=False)
        print(f"  {u[:70]} -> {r.status_code} len={len(r.content)}")
    except Exception as e:
        print(f"  {u[:70]} FAIL {str(e)[:70]}")
