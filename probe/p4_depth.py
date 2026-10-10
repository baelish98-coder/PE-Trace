# -*- coding: utf-8 -*-
"""Probe: danjuan history depth, price series, legulegu/akshare token mechanism."""
import sys, io, json, datetime, inspect
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import requests, akshare as ak
requests.packages.urllib3.disable_warnings()
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"}

print("### 1. danjuan pe_history depth per index")
codes = ["SH000300", "SH000905", "SH000016", "SZ399006", "SH000688",
         "SP500", "NDX", "GDAXI", "HKHSI", "935600", "SPACEVCP", "CSPSADRP"]
for c in codes:
    try:
        r = requests.get(f"https://danjuanfunds.com/djapi/index_eva/pe_history/{c}?day=all",
                         headers=UA, timeout=25, verify=False)
        d = r.json().get("data") or {}
        g = d.get("index_eva_pe_growths") or []
        if g:
            t0 = datetime.datetime.utcfromtimestamp(g[0]["ts"] / 1000).date()
            t1 = datetime.datetime.utcfromtimestamp(g[-1]["ts"] / 1000).date()
            print(f"  {c:10s} n={len(g):5d} {t0} -> {t1}  last_pe={g[-1]['pe']}")
        else:
            print(f"  {c:10s} EMPTY keys={list(d)[:6]}")
    except Exception as e:
        print(f"  {c:10s} FAIL {str(e)[:80]}")
print()

print("### 2. other danjuan day params (SP500)")
for day in ["all", "10", "5", "3", "1"]:
    try:
        r = requests.get(f"https://danjuanfunds.com/djapi/index_eva/pe_history/SP500?day={day}",
                         headers=UA, timeout=25, verify=False)
        g = ((r.json().get("data") or {}).get("index_eva_pe_growths") or [])
        if g:
            t0 = datetime.datetime.utcfromtimestamp(g[0]["ts"] / 1000).date()
            t1 = datetime.datetime.utcfromtimestamp(g[-1]["ts"] / 1000).date()
            print(f"  day={day:4s} n={len(g):5d} {t0} -> {t1}")
        else:
            print(f"  day={day:4s} empty")
    except Exception as e:
        print(f"  day={day:4s} FAIL {str(e)[:70]}")
print()

print("### 3. akshare stock_index_pe_lg source")
src = inspect.getsource(ak.stock_index_pe_lg)
print(src[:2000])
print()

print("### 4. global price history options")
for fn, kw in [("index_global_hist_sina", {}), ("index_global_spot_em", {})]:
    try:
        f = getattr(ak, fn)
        if fn == "index_global_hist_sina":
            try:
                df = f(symbol="sp500")
                print(f"  {fn}: shape={df.shape} cols={list(df.columns)}")
                print(df.head(2).to_string()[:300], "\n  tail:", df.tail(1).to_string()[:200])
            except Exception as e2:
                print(f"  {fn}(sp500) FAIL {str(e2)[:120]}")
        else:
            df = f()
            print(f"  {fn}: shape={df.shape} cols={list(df.columns)}")
            print(df.head(8).to_string()[:600])
    except Exception as e:
        print(f"  {fn}: FAIL {str(e)[:120]}")
