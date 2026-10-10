# -*- coding: utf-8 -*-
"""Gap: alternative PE sources for developed markets beyond danjuan."""
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import requests
requests.packages.urllib3.disable_warnings()
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
      "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"}

def try_get(label, url, headers=None, snippet=190):
    try:
        r = requests.get(url, headers={**UA, **(headers or {})}, timeout=22, verify=False)
        body = r.text
        print(f"  {label:38s} -> {r.status_code} len={len(body):7d} | {body[:snippet]}".replace("\n", " "))
    except Exception as e:
        print(f"  {label:38s} -> FAIL {str(e)[:70]}")

print("### legulegu global PE (with referer/cookie warmup)")
s = requests.Session()
s.headers.update(UA)
try:
    s.get("https://legulegu.com/", timeout=20, verify=False)
    print("  cookies:", list(s.cookies.keys()))
except Exception as e:
    print("  warmup fail", str(e)[:70])
for u in ["https://legulegu.com/stockdata/global-stock-pe",
          "https://legulegu.com/stockdata/globalindex-pe",
          "https://legulegu.com/stockdata/index-basic-pe",
          "https://legulegu.com/stockdata/pe-ratio",
          "https://legulegu.com/stockdata",
          "https://legulegu.com/stockdata/usa-stock-pe",
          "https://legulegu.com/stockdata/hk-stock-pe"]:
    try:
        r = s.get(u, timeout=20, verify=False)
        print(f"  {u[-42:]:42s} -> {r.status_code} len={len(r.text)}")
    except Exception as e:
        print(f"  {u[-42:]:42s} FAIL {str(e)[:60]}")
print()

print("### eniu (亿牛) with referer")
for u in ["https://eniu.com/chart/peh/sh000300/t/all",
          "https://eniu.com/chart/peh/sh000300/all",
          "https://eniu.com/gu/sh000300"]:
    try_get(u[-44:], u, {"Referer": "https://eniu.com/", "X-Requested-With": "XMLHttpRequest"})
print()

print("### yahoo finance")
for u in ["https://query1.finance.yahoo.com/v8/finance/chart/%5EGSPC?range=1mo&interval=1d",
          "https://query2.finance.yahoo.com/v10/finance/quoteSummary/%5EGSPC?modules=summaryDetail",
          "https://query1.finance.yahoo.com/v7/finance/quote?symbols=%5EGSPC"]:
    try_get(u[-52:], u)
print()

print("### multpl / other US PE series")
for u in ["https://www.multpl.com/s-p-500-pe-ratio/table/by-month",
          "https://www.multpl.com/s-p-500-earnings/table/by-month",
          "https://www.multpl.com/shiller-pe/table/by-month"]:
    try_get(u[-46:], u, snippet=130)
print()

print("### wsj / ft / msci markets data")
for u in ["https://www.wsj.com/market-data/stocks/peyields",
          "https://markets.ft.com/data/indices",
          "https://www.msci.com/end-of-day-data-search",
          "https://api.msci.com/index/performance"]:
    try_get(u[-44:], u, snippet=130)
print()

print("### ishares ETF fund pages (PE via holdings csv)")
for u in ["https://www.ishares.com/us/products/239726/ishares-core-sp-500-etf",
          "https://www.ishares.com/uk/individual/en/products/253743/ishares-sp-500-b-ucits-etf-acc-fund"]:
    try_get(u[-46:], u, snippet=130)
