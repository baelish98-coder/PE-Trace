# -*- coding: utf-8 -*-
"""Probe: funddb, global price history, full danjuan universe."""
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import requests, akshare as ak
requests.packages.urllib3.disable_warnings()
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"}

print("### akshare value/global fns")
print([f for f in dir(ak) if "funddb" in f or "value" in f])
print()

print("### funddb interfaces")
for fn in ["index_value_name_funddb"]:
    try:
        df = getattr(ak, fn)()
        print(f"  {fn}: shape={df.shape} cols={list(df.columns)}")
        print(df.head(6).to_string()[:700])
    except Exception as e:
        print(f"  {fn}: FAIL {str(e)[:150]}")
try:
    df = ak.index_value_hist_funddb(symbol="沪深300", indicator="市盈率")
    print("  index_value_hist_funddb 沪深300: shape=", df.shape, list(df.columns))
    print(df.head(3).to_string()[:400])
    print("  tail:", df.tail(2).to_string()[:300])
except Exception as e:
    print("  index_value_hist_funddb FAIL", str(e)[:200])
print()

print("### global price history")
for sym in ["标普500", "纳斯达克", "日经225", "德国DAX"]:
    try:
        df = ak.index_global_hist_em(symbol=sym)
        print(f"  em {sym}: shape={df.shape} cols={list(df.columns)} range={df.iloc[-1,0]}..{df.iloc[0,0]}")
    except Exception as e:
        print(f"  em {sym}: FAIL {str(e)[:100]}")
print()

print("### danjuan full universe")
try:
    r = requests.get("https://danjuanfunds.com/djapi/index_eva/dj", headers=UA, timeout=20, verify=False)
    items = (r.json().get("data") or {}).get("items") or []
    print("  total:", len(items))
    for it in items:
        print("   ", it.get("index_code"), it.get("name"), it.get("pe"), it.get("pe_percentile"))
except Exception as e:
    print("  FAIL", str(e)[:200])
