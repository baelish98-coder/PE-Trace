# -*- coding: utf-8 -*-
"""p18 - inspect tencent bodies; probe 163/sina-us/yahoo price history."""
import io
import json
import sys
import time

sys.path.insert(0, r"C:\Users\Administrator\Documents\dsh-workplace\fund-PETrace")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import requests  # noqa: E402
import urllib3  # noqa: E402

urllib3.disable_warnings()

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
RESULTS = {}


def probe(name, url, *, headers=None, show=300):
    h = {"User-Agent": UA}
    if headers:
        h.update(headers)
    t = time.time()
    rec = {"url": url}
    try:
        r = requests.get(url, headers=h, timeout=25, verify=False)
        rec["status"] = r.status_code
        rec["len"] = len(r.content)
        rec["sec"] = round(time.time() - t, 2)
        rec["body"] = r.text[:show]
    except Exception as e:
        rec["error"] = f"{type(e).__name__}: {str(e)[:130]}"
    RESULTS[name] = rec
    print(f"--- {name}: {json.dumps({k: v for k, v in rec.items() if k != 'url'}, ensure_ascii=False)[:420]}")
    time.sleep(1.8)
    return rec


print("########## 1. tencent variants")
for name, url in [
    ("tx_v1", "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sh000300,day,,,320,qfq"),
    ("tx_v2", "https://web.ifzq.gtimg.cn/appstock/app/kline/kline?param=sh000300,day,,,320"),
    ("tx_v3", "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?_var=kline_dayqfq&param=sh000300,day,,,320,qfq"),
    ("tx_v4", "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sh000300,day,2010-01-01,2026-10-09,320,qfq"),
    ("tx_global_hk", "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=hkHSI,day,,,320,qfq"),
    ("tx_global_us", "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=usINX,day,,,320,qfq"),
]:
    probe(name, url)

print("\n########## 2. 163 chddata (A-share CSV)")
for name, code in [("163_sh000300", "0000300"), ("163_sz399006", "1399006"),
                   ("163_sh000905", "0000905")]:
    probe(name,
          f"http://quotes.money.163.com/service/chddata.html?code={code}"
          f"&start=20050101&end=20261009&fields=TCLOSE;HIGH;LOW;TOPEN;LCLOSE;CHG;PCHG;TURNOVER;VOTURNOVER;VATURNOVER;TCAP;MCAP",
          show=260)

print("\n########## 3. sina US/global daily k")
for name, sym in [("sina_us_.INX", ".INX"), ("sina_us_.DJI", ".DJI"),
                  ("sina_us_.IXIC", ".IXIC"), ("sina_us_.NDX", ".NDX"),
                  ("sina_us_SPY", "SPY")]:
    probe(name,
          f"https://stock.finance.sina.com.cn/usstock/api/jsonp_v2.php/var%20_/{sym}/"
          f"US_MinKService.getDailyK?symbol={sym}&___qn=3",
          headers={"Referer": "https://stock.finance.sina.com.cn/"}, show=200)

print("\n########## 4. yahoo v8 chart")
for name, sym in [("yh_GSPC", "%5EGSPC"), ("yh_IXIC", "%5EIXIC"), ("yh_HSI", "%5EHSI")]:
    probe(name,
          f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=max&interval=1d",
          show=200)
for name, sym in [("yh2_GSPC", "%5EGSPC")]:
    probe(name,
          f"https://query2.finance.yahoo.com/v8/finance/chart/{sym}?range=max&interval=1d",
          show=200)

print("\n########## 5. sina global index via cn stock api")
probe("sina_gd_HSI",
      "https://hq.sinajs.cn/list=int_hangseng,int_dji,int_nasdaq,int_sp500,int_nikkei,znb_UKX",
      headers={"Referer": "https://finance.sina.com.cn/"})

with open(r"C:\Users\Administrator\Documents\dsh-workplace\fund-PETrace\probe\p18_price2.json",
          "w", encoding="utf-8") as f:
    json.dump(RESULTS, f, ensure_ascii=False, indent=1)
print("\nwrote probe/p18_price2.json")
