# -*- coding: utf-8 -*-
"""Probe: stock_market_pe_lg, starcapital, other global PE sources."""
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import requests, akshare as ak
requests.packages.urllib3.disable_warnings()
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"}

print("### akshare stock_market_pe_lg")
try:
    df = ak.stock_market_pe_lg(symbol="上证")
    print("  ok", df.shape, list(df.columns)); print(df.tail(3).to_string()[:300])
except Exception as e:
    print("  FAIL", str(e)[:200])
print()

print("### starcapital CAPE by country")
for u in ["https://www.starcapital.de/en/ratings/stock-markets-valuation/",
          "https://www.starcapital.de/fileadmin/user_upload/files/website_daten/Shiller_CAPE_Data.csv",
          "https://www.starcapital.de/fileadmin/user_upload/files/website_daten/Stock_Market_Valuation.csv",
          "https://www.starcapital.de/fileadmin/user_upload/files/website_daten/"]:
    try:
        r = requests.get(u, headers=UA, timeout=25, verify=False)
        print(f"  {u[-58:]:58s} -> {r.status_code} len={len(r.content)} ct={r.headers.get('content-type','')[:30]}")
        if "csv" in u and r.status_code == 200:
            print("   HEAD:", r.text[:300].replace("\n", " | "))
    except Exception as e:
        print(f"  {u[-58:]:58s} FAIL {str(e)[:60]}")
print()

print("### other global PE candidates")
for label, u in [
    ("gurufocus", "https://www.gurufocus.com/economic_indicators/6778/sp-500-pe-ratio"),
    ("siblisresearch", "https://siblisresearch.com/data/global-stock-market-cap/"),
    ("worldbank", "https://data.worldbank.org"),
    ("indexmundi", "https://www.indexmundi.com/"),
    ("ycharts", "https://ycharts.com/indicators/sp_500_pe_ratio"),
    ("nasdaq-data", "https://data.nasdaq.com/api/v3/datasets/MULTPL/SP500_PE_RATIO_MONTH.json"),
    ("fred", "https://fred.stlouisfed.org/graph/fredgraph.csv?id=SP500"),
    ("eodhd", "https://eodhd.com/api/fundamentals/GSPC.INDX"),
    ("investing", "https://www.investing.com/indices/"),
    ("slickcharts", "https://www.slickcharts.com/sp500"),
    ("mclellan", "https://www.mcoscillator.com/"),
    ("tradingview", "https://scanner.tradingview.com/global/scan"),
]:
    try:
        r = requests.get(u, headers=UA, timeout=18, verify=False, allow_redirects=True)
        print(f"  {label:16s} -> {r.status_code} len={len(r.content):7d} {r.url[:60]}")
    except Exception as e:
        print(f"  {label:16s} -> FAIL {str(e)[:60]}")
print()

print("### FRED CSV check (works?)")
try:
    r = requests.get("https://fred.stlouisfed.org/graph/fredgraph.csv?id=SP500", headers=UA, timeout=25, verify=False)
    print("  status", r.status_code, "lines", len(r.text.split("\n")))
    print("  ", r.text[:200].replace("\n", " | "))
except Exception as e:
    print("  FAIL", str(e)[:120])
