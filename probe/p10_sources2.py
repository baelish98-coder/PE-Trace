# -*- coding: utf-8 -*-
"""Final probe round: starcapital CAPE links, global name table, EM reliability, granularity."""
import sys, io, re, json, time, datetime
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import requests, akshare as ak
requests.packages.urllib3.disable_warnings()
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"}

print("### A. star capital data links")
try:
    r = requests.get("https://www.starcapital.de/en/ratings/stock-markets-valuation/",
                     headers=UA, timeout=30, verify=False)
    links = set(re.findall(r'(?:href|src)="([^"]+\.(?:csv|xlsx|xls|json|zip))"', r.text, re.I))
    print("  data links:", links if links else "(none)")
    for kw in ["CAPE", "Shiller", "Valuation", "daten", "download", "fileadmin"]:
        for m in set(re.findall(r'["\']([^"\']*%s[^"\']*)["\']' % kw, r.text, re.I)):
            if len(m) < 160:
                print(f"   [{kw}] {m}")
except Exception as e:
    print("  FAIL", str(e)[:120])
print()

print("### B. akshare index_global_name_table (full)")
try:
    df = ak.index_global_name_table()
    print(df.to_string())
except Exception as e:
    print("  FAIL", str(e)[:150])
print()

print("### C. eastmoney kline reliability (session + retry)")
sess = requests.Session()
sess.headers.update(UA)
secids = ["100.SPX", "100.NDX", "100.DJI", "100.GDAXI", "100.N225", "100.HSI",
          "100.UKX", "100.CAC", "100.SMI", "100.AEX", "100.KS11", "100.AS51"]
ok = 0
for sec in secids:
    u = ("https://push2his.eastmoney.com/api/qt/stock/kline/get?"
         f"secid={sec}&fields1=f1,f2,f3,f4,f5&fields2=f51,f52,f53,f54,f55,f56,f57,f58"
         "&klt=101&fqt=1&beg=0&end=20500101")
    for attempt in range(3):
        try:
            j = sess.get(u, timeout=20, verify=False).json()
            k = ((j.get("data") or {}).get("klines")) or []
            if k:
                print(f"  {sec:11s} OK n={len(k):6d} {k[0][:10]} -> {k[-1][:10]} close={k[-1].split(',')[2]}")
                ok += 1
                break
            else:
                print(f"  {sec:11s} empty data={j.get('data')}")
                break
        except Exception as e:
            if attempt == 2:
                print(f"  {sec:11s} FAIL(3x) {str(e)[:50]}")
            else:
                time.sleep(1.5)
print(f"  => {ok}/{len(secids)} ok")
print()

print("### D. legulegu granularity (akshare stock_index_pe_lg)")
try:
    df = ak.stock_index_pe_lg(symbol="沪深300")
    d = list(df.iloc[:, 0])
    print("  n=", len(d), "first", d[0], "last", d[-1])
    gaps = []
    for i in range(min(len(d) - 1, 40)):
        gaps.append((d[i + 1] - d[i]))
    print("  first 25 gaps (days):", [str(g) for g in gaps[:25]])
    from collections import Counter
    allgaps = [(d[i + 1] - d[i]).days for i in range(len(d) - 1)]
    print("  gap counter:", Counter(allgaps).most_common(8))
except Exception as e:
    print("  FAIL", str(e)[:150])
print()

print("### E. other valuation-by-country sources")
for label, u in [
    ("worldperatio", "https://www.worldperatio.com/"),
    ("ceic", "https://www.ceicdata.com/en/indicator/stock-market-index"),
    ("theglobaleconomy", "https://www.theglobaleconomy.com/rankings/stock_market_capitalization/"),
    ("tradingeconomics", "https://tradingeconomics.com/country-list/stock-market"),
    ("msci-factsheet", "https://www.msci.com/documents/10199/178e6643-6ae6-47b9-82be-e1fc565ededb"),
    ("longtermtrends", "https://www.longtermtrends.net/"),
    ("buffett", "https://currentmarketvaluation.com/models/buffett-indicator.php"),
]:
    try:
        rr = requests.get(u, headers=UA, timeout=18, verify=False)
        print(f"  {label:18s} -> {rr.status_code} len={len(rr.content):7d}")
    except Exception as e:
        print(f"  {label:18s} -> FAIL {str(e)[:50]}")
