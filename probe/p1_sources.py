# -*- coding: utf-8 -*-
"""Probe candidate PE data sources for coverage + history depth."""
import sys, io, json, traceback
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import requests
requests.packages.urllib3.disable_warnings()

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"}


def show(name, fn):
    print("=" * 70)
    print("###", name)
    try:
        fn()
    except Exception as e:
        print("FAIL", type(e).__name__, str(e)[:300])
    print()


# ---- 1. CSI official: can we get a long daily history? --------------
def csi_history():
    import akshare as ak
    for sym in ["000300", "H30374"]:
        try:
            df = ak.stock_zh_index_value_csindex(symbol=sym)
            print(f"  csindex {sym}: shape={df.shape} cols={list(df.columns)}")
            print("   first:", df.iloc[-1].to_dict())
            print("   last :", df.iloc[0].to_dict())
        except Exception as e:
            print(f"  csindex {sym}: FAIL {str(e)[:120]}")


# ---- 2. LeguLeGu A-share PE: monthly or daily? which symbols? -------
def legulegu():
    import akshare as ak
    for sym in ["沪深300", "上证50", "中证500", "创业板指", "科创50"]:
        try:
            df = ak.stock_index_pe_lg(symbol=sym)
            print(f"  lg {sym}: shape={df.shape} {df.iloc[0,0]} -> {df.iloc[-1,0]}")
        except Exception as e:
            print(f"  lg {sym}: FAIL {str(e)[:110]}")


# ---- 3. Danjuan (蛋卷) index valuation API --------------------------
def danjuan():
    codes = ["SH000300", "SH000016", "SH000905", "SZ399006", "SPX", "NDX",
             "HSI", "GDAXI", "N225", "UKX", "FCHI"]
    for c in codes:
        url = f"https://danjuanfunds.com/djapi/index_eva/detail/{c}"
        try:
            r = requests.get(url, headers=UA, timeout=15, verify=False)
            j = r.json()
            d = j.get("data") or {}
            if isinstance(d, dict) and d.get("pe"):
                print(f"  dj {c}: OK pe={d.get('pe')} pe_pct={d.get('pe_percentile')} "
                      f"pb={d.get('pb')} name={d.get('name')} date={d.get('date')}")
            else:
                print(f"  dj {c}: no-data keys={list(d)[:6] if isinstance(d,dict) else type(d)}")
        except Exception as e:
            print(f"  dj {c}: FAIL {str(e)[:90]}")


# ---- 4. multpl.com S&P500 PE table ---------------------------------
def multpl():
    for slug in ["s-p-500-pe-ratio", "shiller-pe"]:
        url = f"https://www.multpl.com/{slug}/table/by-month"
        try:
            r = requests.get(url, headers=UA, timeout=20, verify=False)
            print(f"  multpl {slug}: {r.status_code} len={len(r.text)}")
            if r.status_code == 200:
                i = r.text.find("<table")
                print("   table@", i, r.text[i:i+260].replace("\n", " ")[:260])
        except Exception as e:
            print(f"  multpl {slug}: FAIL {str(e)[:90]}")


# ---- 5. LeguLeGu direct with browser-ish headers --------------------
def legulegu_direct():
    for url in ["https://legulegu.com/stockdata/global-stock-pe",
                "https://legulegu.com/stockdata/index-basic-pe"]:
        try:
            r = requests.get(url, headers=UA, timeout=20, verify=False)
            print(f"  {url}: {r.status_code} len={len(r.text)}")
        except Exception as e:
            print(f"  {url}: FAIL {str(e)[:90]}")


for n, f in [("CSI_HISTORY", csi_history), ("LEGULEGU_ASHARE", legulegu),
             ("DANJUAN", danjuan), ("MULTPL", multpl),
             ("LEGULEGU_DIRECT", legulegu_direct)]:
    show(n, f)
