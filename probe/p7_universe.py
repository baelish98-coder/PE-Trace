# -*- coding: utf-8 -*-
"""Gap: full danjuan universe + eastmoney global secid map + pe_history coverage."""
import sys, io, json, datetime
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import requests
requests.packages.urllib3.disable_warnings()
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"}

print("### A. danjuan full index_eva list dump")
r = requests.get("https://danjuanfunds.com/djapi/index_eva/dj", headers=UA, timeout=25, verify=False)
items = (r.json().get("data") or {}).get("items") or []
print("total", len(items))
for it in items:
    print(json.dumps({k: it.get(k) for k in
          ["index_code", "name", "pe", "pb", "pe_percentile", "pb_percentile", "roe", "yeild"]},
          ensure_ascii=False))
print()

print("### B. danjuan pe_history coverage probe for global codes")
for c in ["N225", "UKX", "FCHI", "AXJO", "KOSPI", "TWII", "SPTSX", "SSMI", "AEX",
          "IBEX", "FTSEMIB", "SX5E", "SP500", "NDX", "DJI", "GDAXI", "HSI",
          "HSCEI", "HSTECH", "MSCIACWI", "MSCIWORLD", "MSCIEF", "NASDAQ", "RUT"]:
    try:
        rr = requests.get(f"https://danjuanfunds.com/djapi/index_eva/pe_history/{c}?day=all",
                          headers=UA, timeout=18, verify=False)
        g = ((rr.json().get("data") or {}).get("index_eva_pe_growths") or [])
        if g:
            t0 = datetime.datetime.fromtimestamp(g[0]["ts"]/1000, datetime.UTC).date()
            t1 = datetime.datetime.fromtimestamp(g[-1]["ts"]/1000, datetime.UTC).date()
            print(f"  {c:11s} n={len(g):5d} {t0} -> {t1}")
        else:
            print(f"  {c:11s} EMPTY")
    except Exception as e:
        print(f"  {c:11s} FAIL {str(e)[:60]}")
print()

print("### C. eastmoney global secid sweep")
cands = {"S&P500": "100.SPX", "Nasdaq100": "100.NDX", "Dow": "100.DJI", "DAX": "100.GDAXI",
         "Nikkei225": "100.N225", "HSI": "100.HSI", "HSCEI": "100.HSCEI", "HSTECH": "100.HSTECH",
         "FTSE100": "100.UKX", "CAC40": "100.CAC", "SMI": "100.SMI", "AEX": "100.AEX",
         "IBEX35": "100.IBEX", "FTSE_MIB": "100.FTSEMIB", "ASX200": "100.AS51",
         "KOSPI": "100.KS11", "TWSE": "100.TWII", "TSX": "100.GSPTSE", "STOXX50": "100.SX5E",
         "EuroStoxx50": "100.STOXX50", "CSI300": "1.000300", "CSI500": "1.000905",
         "SSE50": "1.000016", "ChiNext": "0.399006", "STAR50": "1.000688",
         "CSI1000": "1.000852", "SZSE": "0.399001", "SSE": "1.000001"}
for name, sec in cands.items():
    u = ("https://push2his.eastmoney.com/api/qt/stock/kline/get?"
         f"secid={sec}&fields1=f1,f2,f3,f4,f5&fields2=f51,f52,f53,f54,f55,f56,f57,f58"
         "&klt=101&fqt=1&beg=0&end=20500101")
    try:
        rr = requests.get(u, headers=UA, timeout=18, verify=False)
        k = ((rr.json().get("data") or {}).get("klines")) or []
        print(f"  {name:12s} {sec:12s} n={len(k):6d} {k[0][:10] if k else '-':12s} {k[-1][:10] if k else '-':12s} last={k[-1].split(',')[2] if k else '-'}")
    except Exception as e:
        print(f"  {name:12s} {sec:12s} FAIL {str(e)[:55]}")
