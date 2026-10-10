# -*- coding: utf-8 -*-
"""P14: serious attempt at a GLOBAL developed-market PE-history source.

P13 showed most aggregators are dead ends. Two look alive and are worth real work:
  * starcapital.de  - publishes a "Capital Market Valuation" workbook with PE/CAPE
                      by country; the guessed .xlsx URL redirected to the homepage,
                      so scrape the landing page for the real download href.
  * stockanalysis.com - ETF page carries a PE ratio; find the backing JSON API and
                      check whether any history endpoint exists.
Also re-check siblisresearch (historical PE by country) and a few long shots.
"""
import io
import json
import re
import sys
import time
from urllib.parse import urljoin

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import requests
import urllib3

urllib3.disable_warnings()

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
H = {"User-Agent": UA, "Accept": "*/*", "Accept-Language": "en-US,en;q=0.9,de;q=0.8"}

OUT = {}


def get(url, **kw):
    hh = dict(H)
    hh.update(kw.pop("headers", {}) or {})
    return requests.get(url, headers=hh, timeout=30, verify=False, **kw)


def show(label, r, n=200):
    print(f"[{r.status_code}] {label}  len={len(r.content)}  "
          f"ctype={r.headers.get('Content-Type','')[:60]}")
    if "text" in r.headers.get("Content-Type", "") or r.text[:1] in "<{[":
        print("     ", r.text[:n].replace("\n", " "))
    print()


print("=" * 94)
print("1. StarCapital - locate the real valuation workbook URL")
print("=" * 94)
sc_url = "https://www.starcapital.de/en/research/stock-market-valuation/"
try:
    r = get(sc_url)
    show("starcapital landing", r, 120)
    links = re.findall(r'href="([^"]+)"', r.text)
    interesting = [l for l in links
                   if re.search(r"(xlsx|xls|csv|download|valuation|bewertung)", l, re.I)]
    print("  candidate links:")
    for l in dict.fromkeys(interesting):
        print("    ", urljoin(sc_url, l))
    OUT["starcapital_links"] = [urljoin(sc_url, l) for l in dict.fromkeys(interesting)]

    # try the most likely ones
    for l in dict.fromkeys(interesting):
        full = urljoin(sc_url, l)
        if not re.search(r"\.(xlsx|xls|csv)$", full, re.I):
            continue
        try:
            rr = get(full)
            print(f"  -> [{rr.status_code}] {full}  bytes={len(rr.content)}  "
                  f"ctype={rr.headers.get('Content-Type','')[:40]}")
            if rr.status_code == 200 and len(rr.content) > 5000:
                OUT["starcapital_file"] = full
                with open("probe/starcapital_valuation.bin", "wb") as f:
                    f.write(rr.content)
                print("     SAVED")
        except Exception as e:
            print(f"  -> ERR {full}: {type(e).__name__}: {str(e)[:60]}")
        time.sleep(0.6)
except Exception as e:
    print("starcapital failed:", type(e).__name__, str(e)[:120])

print("=" * 94)
print("2. stockanalysis.com - find the JSON API behind an ETF page")
print("=" * 94)
for api in [
    "https://stockanalysis.com/api/symbol/e/SPY/overview",
    "https://stockanalysis.com/api/symbol/etf/SPY/overview",
    "https://stockanalysis.com/etf/spy/__data.json",
    "https://stockanalysis.com/api/screener/e?m=marketCap&s=desc&c=no,s,n,marketCap,peRatio&cn=500",
]:
    try:
        r = get(api)
        show(f"sa api {api.split('/api/')[-1][:52]}", r, 240)
        if r.status_code == 200 and r.text.strip().startswith(("{", "[")):
            OUT.setdefault("sa_api_ok", []).append(api)
    except Exception as e:
        print(f"[ERR] {api} {type(e).__name__}: {str(e)[:60]}\n")
    time.sleep(0.5)

# does the SPY etf page itself contain a PE number we could parse?
try:
    r = get("https://stockanalysis.com/etf/spy/")
    hits = re.findall(r'PE Ratio[^0-9]{0,80}([0-9]+\.[0-9]+)', r.text)
    print("  SPY page 'PE Ratio' matches:", hits[:5])
    OUT["sa_spy_pe"] = hits[:5]
except Exception as e:
    print("  SPY page err:", str(e)[:80])
print()

print("=" * 94)
print("3. siblisresearch - historical PE by country")
print("=" * 94)
for u in ["https://siblisresearch.com/data/",
          "https://siblisresearch.com/data/us-stock-market-valuation/",
          "https://siblisresearch.com/data/sp-500-pe-ratio/"]:
    try:
        r = get(u)
        show(u, r, 160)
        if r.status_code == 200:
            xl = [l for l in re.findall(r'href="([^"]+)"', r.text)
                  if re.search(r"\.(xls|xlsx|csv)", l, re.I)]
            if xl:
                print("   xls links:", xl[:8])
                OUT.setdefault("siblis_xls", []).extend(xl[:8])
    except Exception as e:
        print(f"[ERR] {u}: {type(e).__name__}: {str(e)[:70]}\n")
    time.sleep(0.6)

print("=" * 94)
print("4. Long shots with plausible PE history")
print("=" * 94)
LONG = [
    ("nasdaq:SPY-pe", "https://api.nasdaq.com/api/quote/SPY/summary?assetclass=etf"),
    ("ishares:ajax", "https://www.ishares.com/uk/individual/en/products/251882/"
                     "ishares-msci-world-ucits-etf-acc-fund/1506575576011.ajax"),
    ("ssga:spy-json", "https://www.ssga.com/us/en/intermediary/library-content/"
                      "products/fund/fund-data/etfs/spy/product.json"),
    ("etfcom:SPY", "https://www.etf.com/SPY"),
    ("morningstar:api", "https://www.morningstar.com/api/v2/security/quote/SPY"),
    ("stockanalysis:index", "https://stockanalysis.com/list/sp-500-stocks/"),
    ("finviz:global", "https://finviz.com/quote.ashx?t=SPY"),
    ("tradingview:scan", "https://scanner.tradingview.com/global/scan"),
    ("businessinsider:pe", "https://markets.businessinsider.com/index/"
                           "s-p-500?mi=22&p=1"),
    ("worldbank:data", "https://api.worldbank.org/v2/country/US/indicator/"
                       "CM.MKT.PORTAL.ZG?format=json"),
]
for label, u in LONG:
    try:
        r = get(u)
        show(label, r, 150)
        if r.status_code == 200 and len(r.content) > 1000:
            OUT.setdefault("longshot_ok", []).append(u)
    except Exception as e:
        print(f"[ERR] {label}: {type(e).__name__}: {str(e)[:70]}\n")
    time.sleep(0.6)

with open("probe/p14_global_pe2.json", "w", encoding="utf-8") as f:
    json.dump(OUT, f, ensure_ascii=False, indent=1)
print("\nwrote probe/p14_global_pe2.json")
