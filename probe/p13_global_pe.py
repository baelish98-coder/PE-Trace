# -*- coding: utf-8 -*-
"""P13: probe candidate sources for NON-A/US/HK/DE developed-market index PE history.

Gap to close: danjuan only has PE history for CN/HK/US/DE. We still need PE
(ideally a long history) for JP, UK, FR, DE, CH, NL, ES, IT, AU, KR, TW, CA.
"""
import io
import json
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import requests
import urllib3

urllib3.disable_warnings()

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
H = {"User-Agent": UA, "Accept": "*/*", "Accept-Language": "en-US,en;q=0.9"}

RESULTS = []


def probe(label, url, *, headers=None, note="", want_json=False, maxlen=260):
    hh = dict(H)
    if headers:
        hh.update(headers)
    t0 = time.time()
    try:
        r = requests.get(url, headers=hh, timeout=25, verify=False)
        ms = int((time.time() - t0) * 1000)
        body = r.text
        info = {"label": label, "url": url, "status": r.status_code,
                "len": len(body), "ms": ms, "note": note}
        if r.status_code == 200:
            if want_json:
                try:
                    j = r.json()
                    info["json_top"] = (list(j.keys())[:12] if isinstance(j, dict)
                                        else f"list[{len(j)}]")
                    info["sample"] = json.dumps(j, ensure_ascii=False)[:maxlen]
                except Exception as e:
                    info["json_err"] = str(e)[:80]
                    info["sample"] = body[:maxlen].replace("\n", " ")
            else:
                info["ctype"] = r.headers.get("Content-Type", "")[:60]
                info["sample"] = body[:maxlen].replace("\n", " ")
        RESULTS.append(info)
        print(f"[{'OK ' if r.status_code==200 else 'BAD'}] {label:<34} "
              f"{r.status_code} len={len(body):>8} {ms:>5}ms  {note}")
        print(f"      {info.get('sample','')[:220]}")
        if info.get("json_top"):
            print(f"      json_top={info['json_top']}")
    except Exception as e:
        RESULTS.append({"label": label, "url": url,
                        "err": f"{type(e).__name__}: {str(e)[:100]}", "note": note})
        print(f"[ERR] {label:<34} {type(e).__name__}: {str(e)[:70]}")
    print()


print("=" * 92)
print("A. stockanalysis.com - index/ETF valuation pages")
print("=" * 92)
probe("sa:SPY", "https://stockanalysis.com/etf/spy/", note="ETF page, PE?")
probe("sa:EWJ", "https://stockanalysis.com/etf/ewj/", note="Japan ETF")
probe("sa:EWU", "https://stockanalysis.com/etf/ewu/", note="UK ETF")
probe("sa:index-nasdaq100", "https://stockanalysis.com/list/nasdaq-100-stocks/",
      note="list page")

print("=" * 92)
print("B. StarCapital - global valuation Excel (CAPE by country)")
print("=" * 92)
probe("sc:valuation-page",
      "https://www.starcapital.de/en/research/stock-market-valuation/",
      note="landing page, look for xlsx link")
probe("sc:xlsx-guess",
      "https://www.starcapital.de/fileadmin/user_upload/files/research/Artikel/"
      "Capital_Market_Valuation_Overview.xlsx",
      note="direct xlsx guess")

print("=" * 92)
print("C. MSCI public index data")
print("=" * 92)
probe("msci:perf-api",
      "https://app2.msci.com/products/service/index/indexmaster/"
      "getIndexPerformance?index_codes=990300&currency=USD&start_date=20200101"
      "&end_date=20201231&frequency=D",
      note="MSCI index performance API", want_json=True)
probe("msci:eod-page",
      "https://www.msci.com/end-of-day-data-search", note="landing page")

print("=" * 92)
print("D. iShares / SPDR fund pages (current PE, maybe history)")
print("=" * 92)
probe("ish:iwda",
      "https://www.ishares.com/uk/individual/en/products/251882/"
      "ishares-msci-world-ucits-etf-acc-fund", note="IWDA page")
probe("ssga:spy",
      "https://www.ssga.com/us/en/intermediary/etfs/spdr-sp-500-etf-trust-spy",
      note="SPY page")

print("=" * 92)
print("E. index provider factsheets / misc")
print("=" * 92)
probe("slickcharts:sp500", "https://www.slickcharts.com/sp500", note="current only")
probe("wsj:index-pe",
      "https://www.wsj.com/market-data/stocks/peyields", note="WSJ PE table")
probe("nasdaq:api-pe",
      "https://api.nasdaq.com/api/quote/SPY/etf-holdings?assetclass=etf",
      note="nasdaq api", want_json=True)
probe("boerse:dax-pe",
      "https://www.boerse.de/boersenlexikon/Kurs-Gewinn-Verhaeltnis",
      note="german site")

print("=" * 92)
print("F. Yahoo / stooq / alternative chart APIs for index PE")
print("=" * 92)
probe("yahoo:chart-spy",
      "https://query1.finance.yahoo.com/v8/finance/chart/SPY?range=1mo&interval=1d",
      note="yahoo (was 403)", want_json=True)
probe("stooq:spx", "https://stooq.com/q/d/l/?s=^spx&i=d", note="stooq (was JS)")
probe("fred:csv",
      "https://fred.stlouisfed.org/graph/fredgraph.csv?id=SP500", note="FRED (was timeout)")

print("=" * 92)
print("G. ETF issuer 'fund' JSON endpoints with PE history")
print("=" * 92)
probe("vanguard:fundapi",
      "https://api.vanguard.com/rs/gre/gra/1.7.1/datasets/"
      "iraq-holdings-usd.json", note="vanguard (unlikely)")
probe("jpmorgan:guide",
      "https://am.jpmorgan.com/us/en/asset-management/adv/products/"
      "jpmorgan-ushigh-yield-fund", note="(unlikely)")
probe("purple:etf",
      "https://www.purplefishsolutions.com", note="(unlikely)")

print("=" * 92)
print("H. macro/valuation aggregators")
print("=" * 92)
probe("currentmarketvaluation",
      "https://www.currentmarketvaluation.com/models/buffett-indicator.php",
      note="has data pages")
probe("worldperatio:index",
      "https://worldperatio.com/", note="ETF valuation ranks")
probe("spglobal:index-factsheet",
      "https://www.spglobal.com/spdji/en/idsenhancedfactsheet/"
      "file/factsheetdownload?fileId=1&languageId=en",
      note="S&P DJI factsheet download")

with open("probe/p13_global_pe.json", "w", encoding="utf-8") as f:
    json.dump(RESULTS, f, ensure_ascii=False, indent=1)
print("\nwrote probe/p13_global_pe.json")
