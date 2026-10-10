# -*- coding: utf-8 -*-
"""P15: last focused attempt at global developed-market PE history.

P13/P14 killed the obvious aggregators. Remaining live leads worth real effort:
  * StarCapital  - country CAPE/PE workbook (JS site; mine the HTML for asset URLs)
  * stockanalysis.com __data.json - does the ETF payload carry a PE ratio?
  * stockanalysis index pages - do '/index/XXX/' pages exist with valuation?
  * index_global_spot_em - does EM's global spot table expose a PE column?
  * a few country-PE publishers
"""
import io
import json
import re
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import requests
import urllib3

urllib3.disable_warnings()

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
H = {"User-Agent": UA, "Accept": "*/*", "Accept-Language": "en-US,en;q=0.9,de;q=0.8"}
OUT = {}


def get(u, **kw):
    hh = dict(H); hh.update(kw.pop("headers", {}) or {})
    return requests.get(u, headers=hh, timeout=30, verify=False, **kw)


print("=" * 94)
print("1. StarCapital - mine landing page for downloadable assets")
print("=" * 94)
try:
    r = get("https://www.starcapital.de/en/research/stock-market-valuation/")
    print(f"[{r.status_code}] len={len(r.text)}")
    for pat, label in [
        (r'fileadmin[^"\'<>\s]+', "fileadmin"),
        (r'href="([^"]*\.(?:xlsx|xls|csv|zip|pdf))"', "asset"),
        (r'(?:src|data-[a-z]+)="([^"]*\.(?:xlsx|xls|csv|zip))"', "asset2"),
        (r'valuation[^"\'<>\s]{0,80}', "valuation-token"),
    ]:
        found = re.findall(pat, r.text, re.I)
        uniq = list(dict.fromkeys(found))[:14]
        print(f"  {label}: {uniq}")
        OUT.setdefault("starcapital", {})[label] = uniq
except Exception as e:
    print("  ERR", type(e).__name__, str(e)[:100])
print()

# try the German-language page too, and the historic known file paths
for u in ["https://www.starcapital.de/en/research/stock-market-valuation",
          "https://www.starcapital.de/en/research/capital-market-valuation/",
          "https://www.starcapital.de/research/aktienmarktbewertung"]:
    try:
        r = get(u)
        fa = list(dict.fromkeys(re.findall(r'href="([^"]*fileadmin[^"]*)"', r.text, re.I)))[:10]
        print(f"  [{r.status_code}] {u}  fileadmin_hrefs={fa}")
        if fa:
            OUT.setdefault("starcapital_hrefs", {})[u] = fa
    except Exception as e:
        print(f"  ERR {u}: {type(e).__name__}")
    time.sleep(0.4)
print()

print("=" * 94)
print("2. stockanalysis.com __data.json - look for a PE ratio")
print("=" * 94)
try:
    r = get("https://stockanalysis.com/etf/spy/__data.json")
    j = r.json()
    blob = json.dumps(j, ensure_ascii=False)
    print(f"  len(json)={len(blob)}")
    for kw in ["peRatio", "pe_ratio", "PE Ratio", "\"pe\"", "peTtm", "peForward"]:
        idx = blob.find(kw)
        print(f"  {kw!r}: {'FOUND @'+str(idx) if idx>=0 else 'absent'}"
              + (f" ... {blob[max(0,idx-40):idx+90]}" if idx >= 0 else ""))
    OUT["sa_datajson_len"] = len(blob)
except Exception as e:
    print("  ERR", type(e).__name__, str(e)[:100])
print()

print("=" * 94)
print("3. stockanalysis index pages")
print("=" * 94)
for slug in ["spx", "ndx", "dji", "ukx", "dax", "nikkei-225", "hsi"]:
    for tmpl in [f"https://stockanalysis.com/index/{slug}/",
                 f"https://stockanalysis.com/index/{slug}/__data.json"]:
        try:
            r = get(tmpl)
            ok = r.status_code == 200
            pe = ""
            if ok and "json" in r.headers.get("Content-Type", ""):
                b = json.dumps(r.json(), ensure_ascii=False)
                m = re.search(r'"pe[^"]*"\s*:\s*([0-9.]+)', b)
                pe = f" pe={m.group(1)}" if m else " no-pe"
            elif ok:
                m = re.search(r'PE Ratio[^0-9]{0,60}([0-9]+\.[0-9]+)', r.text)
                pe = f" pe={m.group(1)}" if m else ""
            print(f"  [{r.status_code}] {tmpl} len={len(r.content)}{pe}")
            if ok:
                OUT.setdefault("sa_index_ok", []).append(tmpl)
        except Exception as e:
            print(f"  [ERR] {tmpl} {type(e).__name__}")
        time.sleep(0.35)
print()

print("=" * 94)
print("4. eastmoney global spot - is there a PE column?")
print("=" * 94)
try:
    import akshare as ak
    df = ak.index_global_spot_em()
    print("  shape:", df.shape)
    print("  cols:", list(df.columns))
    print(df.head(3).to_string())
    OUT["em_global_spot_cols"] = list(df.columns)
except Exception as e:
    print("  ERR", type(e).__name__, str(e)[:140])
print()

print("=" * 94)
print("5. country-PE publishers")
print("=" * 94)
CAND = [
    ("countryeconomy:uk", "https://countryeconomy.com/business/pe-ratio/uk"),
    ("countryeconomy:de", "https://countryeconomy.com/business/pe-ratio/germany"),
    ("ceicdata:pe", "https://www.ceicdata.com/en/indicator/united-states/pe-ratio"),
    ("gurufocus:global", "https://www.gurufocus.com/global-market-valuation.php"),
    ("longtermtrends", "https://www.longtermtrends.net/sp500/"),
    ("valuewalk", "https://www.valuewalk.com/"),
    ("dshort", "https://www.advisorperspectives.com/dshort/updates/2024/01/02/"
               "sp-500-pe-ratio-and-earnings-yield"),
    ("stockmarketvaluation", "https://www.stockmarketvaluation.com/"),
    ("ycharts:sp500pe", "https://ycharts.com/indicators/sp_500_pe_ratio"),
    ("multpl:sp500pe", "https://www.multpl.com/s-p-500-pe-ratio/table/by-month"),
]
for label, u in CAND:
    try:
        r = get(u)
        body = r.text
        has_tbl = bool(re.search(r"<table", body, re.I))
        nnum = len(re.findall(r"\b\d{1,3}\.\d{1,2}\b", body))
        print(f"  [{r.status_code}] {label:<22} len={len(body):>8} table={has_tbl} nums={nnum}")
        if r.status_code == 200:
            OUT.setdefault("country_pe_ok", []).append({"label": label, "url": u,
                                                        "table": has_tbl, "nums": nnum})
    except Exception as e:
        print(f"  [ERR] {label:<22} {type(e).__name__}: {str(e)[:50]}")
    time.sleep(0.5)

with open("probe/p15_global_deep.json", "w", encoding="utf-8") as f:
    json.dump(OUT, f, ensure_ascii=False, indent=1)
print("\nwrote probe/p15_global_deep.json")
