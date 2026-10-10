# -*- coding: utf-8 -*-
"""p20 - deeper price history: tencent week/month, sina datalen, EM host sweep."""
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
OUT = {}


def get(name, url, headers=None, show=230):
    h = {"User-Agent": UA}
    if headers:
        h.update(headers)
    try:
        r = requests.get(url, headers=h, timeout=25, verify=False)
        rec = {"status": r.status_code, "len": len(r.content), "body": r.text[:show]}
    except Exception as e:
        rec = {"error": f"{type(e).__name__}: {str(e)[:110]}"}
    OUT[name] = rec
    print(f"{name:30s} {json.dumps(rec, ensure_ascii=False)[:330]}")
    time.sleep(1.4)
    return rec


def tx(period, code, cnt=2000, start="", end=""):
    url = (f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?"
           f"param={code},{period},{start},{end},{cnt},qfq")
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=25, verify=False)
        j = r.json()
        if j.get("code") != 0:
            return {"err": j.get("msg", "")[:60]}
        d = (j.get("data") or {}).get(code) or {}
        kl = d.get(period) or d.get("qfq" + period) or []
        if not kl:
            return {"n": 0, "keys": sorted(d.keys())}
        return {"n": len(kl), "first": kl[0][0], "last": kl[-1][0],
                "lastclose": kl[-1][2]}
    except Exception as e:
        return {"error": f"{type(e).__name__}: {str(e)[:80]}"}


print("########## A. tencent weekly/monthly, 2000 bars")
for period in ("week", "month"):
    for code in ["sh000300", "sh000905", "sh000016", "sz399006", "sh000688",
                 "hkHSI", "hkHSCEI", "hkHSTECH", "usINX", "hkHSI", "deDAX",
                 "ukFTSE", "jpNI225", "sh000001"]:
        r = tx(period, code)
        print(f"  {period:5s} {code:10s} -> {json.dumps(r, ensure_ascii=False)[:150]}")
        OUT[f"tx_{period}_{code}"] = r
        time.sleep(1.0)
    print()

print("########## B. sina datalen limits")
for dl in [1023, 2000, 3000, 6000]:
    get(f"sina_dl{dl}",
        "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/"
        f"CN_MarketData.getKLineData?symbol=sh000300&scale=240&ma=no&datalen={dl}",
        headers={"Referer": "https://finance.sina.com.cn/"}, show=120)
    # measure array length
    try:
        r = requests.get("https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/"
                         f"CN_MarketData.getKLineData?symbol=sh000300&scale=240&ma=no&datalen={dl}",
                         headers={"User-Agent": UA, "Referer": "https://finance.sina.com.cn/"},
                         timeout=20, verify=False)
        arr = json.loads(r.text)
        print(f"    -> parsed n={len(arr)} first={arr[0]['day']} last={arr[-1]['day']}")
    except Exception as e:
        print("    -> parse err", type(e).__name__, str(e)[:80])
    time.sleep(1.2)

print("\n########## C. sina global index daily k (klc_kl.js)")
for sym in ["int_dji", "int_sp500", "int_nasdaq", "int_hangseng", "int_nikkei"]:
    get(f"sina_klc_{sym}",
        f"https://finance.sina.com.cn/realstock/company/{sym}/hisdata/klc_kl.js",
        headers={"Referer": "https://finance.sina.com.cn/"}, show=140)

print("\n########## D. eastmoney host sweep")
EM_PATH = ("/api/qt/stock/kline/get?secid=1.000300&fields1=f1,f2,f3"
           "&fields2=f51,f53&klt=101&fqt=1&beg=0&end=20500101")
for host in ["push2his.eastmoney.com", "push2his1.eastmoney.com",
             "push2his2.eastmoney.com", "1.push2his.eastmoney.com",
             "7.push2his.eastmoney.com", "82.push2his.eastmoney.com",
             "push2.eastmoney.com", "push2delay.eastmoney.com",
             "quote.eastmoney.com"]:
    get(f"em_{host}", f"https://{host}{EM_PATH}", show=90)

print("\n########## E. 163 retry")
get("163_retry",
    "http://quotes.money.163.com/service/chddata.html?code=0000300"
    "&start=20050101&end=20261009&fields=TCLOSE", show=140)

with open(r"C:\Users\Administrator\Documents\dsh-workplace\fund-PETrace\probe\p20_deep.json",
          "w", encoding="utf-8") as f:
    json.dump(OUT, f, ensure_ascii=False, indent=1)
print("\nwrote probe/p20_deep.json")
