# -*- coding: utf-8 -*-
"""Probe global index PRICE history sources."""
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import requests
requests.packages.urllib3.disable_warnings()
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"}

print("### STOOQ (csv)")
stooq = {"S&P500": "^spx", "Nasdaq100": "^ndx", "DAX": "^dax", "Nikkei225": "^nkx",
         "FTSE100": "^ukx", "CAC40": "^cac", "HSI": "^hsi", "KOSPI": "^kospi",
         "ASX200": "^axjo", "TSX": "^tsx", "SMI": "^smi", "AEX": "^aex",
         "IBEX": "^ibex", "MIB": "^f tsemib", "STOXX50": "^stx50", "DOW": "^dji"}
for name, sym in stooq.items():
    try:
        r = requests.get(f"https://stooq.com/q/d/l/?s={sym}&i=d", headers=UA, timeout=25, verify=False)
        lines = r.text.strip().split("\n")
        ok = r.status_code == 200 and len(lines) > 5 and "Date" in lines[0]
        print(f"  {name:10s} {sym:10s} -> {r.status_code} rows={len(lines)-1:6d} "
              f"{lines[1][:34] if len(lines)>1 else ''} | {lines[-1][:34] if len(lines)>1 else ''}")
    except Exception as e:
        print(f"  {name:10s} {sym:10s} FAIL {str(e)[:60]}")
print()

print("### SINA global index daily")
sina_map = {"gb_$dji": "道指", "gb_$ixic": "纳指", "gb_$inx": "标普500", "int_dji": "道指-int"}
for s in ["gb_$dji", "gb_$ixic", "gb_$inx"]:
    for u in [f"https://hq.sinajs.cn/list={s}",
              f"https://stock.finance.sina.com.cn/usstock/api/jsonp.php/var%20x/US_MinKService.getDailyK?symbol=.",
              ]:
        try:
            r = requests.get(u, headers={**UA, "Referer": "https://finance.sina.com.cn"}, timeout=15, verify=False)
            print(f"  {u[:74]} -> {r.status_code} {r.text[:120]}")
        except Exception as e:
            print(f"  {u[:74]} FAIL {str(e)[:60]}")
    break
print()

print("### EASTMONEY push2his kline (global)")
em = {"S&P500": "100.SPX", "Nasdaq": "100.NDX", "DAX": "100.GDAXI", "Nikkei": "100.N225",
      "HSI": "100.HSI", "CSI300": "1.000300"}
for name, sec in em.items():
    u = ("https://push2his.eastmoney.com/api/qt/stock/kline/get?"
         f"secid={sec}&fields1=f1,f2,f3,f4,f5&fields2=f51,f52,f53,f54,f55,f56,f57,f58"
         "&klt=101&fqt=1&beg=0&end=20500101")
    try:
        r = requests.get(u, headers=UA, timeout=20, verify=False)
        j = r.json()
        k = ((j.get("data") or {}).get("klines")) or []
        print(f"  {name:10s} {sec:10s} -> {r.status_code} n={len(k)} first={k[0][:22] if k else '-'} last={k[-1][:22] if k else '-'}")
    except Exception as e:
        print(f"  {name:10s} {sec:10s} FAIL {str(e)[:60]}")
print()

print("### DANJUAN other apis (index quote / kline)")
for u in ["https://danjuanfunds.com/djapi/index_eva/pe_history/SH000300?day=all",
          "https://danjuanfunds.com/djapi/index_eva/pb_history/SH000300?day=all",
          "https://danjuanfunds.com/djapi/index_eva/detail/SP500"]:
    try:
        r = requests.get(u, headers=UA, timeout=20, verify=False)
        print(f"  {u[-48:]} -> {r.status_code} {r.text[:200]}")
    except Exception as e:
        print(f"  FAIL {str(e)[:60]}")
