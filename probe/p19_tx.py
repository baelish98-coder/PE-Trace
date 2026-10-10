# -*- coding: utf-8 -*-
"""p19 - tencent max count + global index codes + fallback price sources."""
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


def tx(param, show=0):
    url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={param}"
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=25, verify=False)
        if r.status_code != 200 or len(r.content) < 100:
            return {"status": r.status_code, "len": len(r.content), "body": r.text[:120]}
        j = r.json()
        if j.get("code") != 0:
            return {"status": 200, "code": j.get("code"), "msg": j.get("msg", "")[:100]}
        out = {}
        for code, pl in (j.get("data") or {}).items():
            if not isinstance(pl, dict):
                continue
            kl = pl.get("day") or pl.get("qfqday") or []
            if kl:
                out[code] = {"n": len(kl), "first": kl[0][0], "last": kl[-1][0],
                             "firstclose": kl[0][2], "lastclose": kl[-1][2]}
            else:
                out[code] = {"n": 0, "keys": sorted(pl.keys())[:8]}
        return {"status": 200, "data": out}
    except Exception as e:
        return {"error": f"{type(e).__name__}: {str(e)[:110]}"}


print("########## A. tencent max count bisect (sh000300)")
for n in [320, 500, 800, 1000, 1500, 2000, 3000, 5000, 640, 700]:
    res = tx(f"sh000300,day,,,{n},qfq")
    d = res.get("data", {}).get("sh000300", {})
    print(f"  n={n:5d} -> {json.dumps(d, ensure_ascii=False)[:140] if d else res}")
    time.sleep(1.2)

print("\n########## B. tencent global index codes")
GLOBAL = ["usINX", "usDJI", "usIXIC", "usNDX", "hkHSI", "hkHSCEI", "hkHSTECH",
          "deDAX", "ukFTSE", "ukUKX", "jpNI225", "jpN225", "frCAC", "frCAC40",
          "euSX5E", "usSPX", "sgSTI", "krKOSPI", "auAS51", "caGSPTSE",
          "indNIFTY", "nlAEX", "esIBEX", "itMIB", "sh000001", "sz399001"]
for code in GLOBAL:
    for cnt in (320, 3000):
        res = tx(f"{code},day,,,{cnt},qfq")
        d = res.get("data", {}).get(code, {})
        print(f"  {code:12s} cnt={cnt:5d} -> {json.dumps(d if d else res, ensure_ascii=False)[:150]}")
        time.sleep(1.0)

print("\n########## C. eastmoney health re-check")
try:
    r = requests.get("https://push2his.eastmoney.com/api/qt/stock/kline/get"
                     "?secid=1.000300&fields1=f1&fields2=f51,f53&klt=101&fqt=1&beg=0&end=20500101",
                     headers={"User-Agent": UA}, timeout=15, verify=False)
    print("  em:", r.status_code, len(r.content))
except Exception as e:
    print("  em ERR:", type(e).__name__, str(e)[:90])

print("\n########## D. sina A-share daily via cn api")
try:
    r = requests.get("https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/"
                     "CN_MarketData.getKLineData?symbol=sh000300&scale=240&ma=no&datalen=1023",
                     headers={"User-Agent": UA, "Referer": "https://finance.sina.com.cn/"},
                     timeout=20, verify=False)
    print("  sina cn:", r.status_code, len(r.content), r.text[:200])
except Exception as e:
    print("  sina cn ERR:", type(e).__name__, str(e)[:90])

with open(r"C:\Users\Administrator\Documents\dsh-workplace\fund-PETrace\probe\p19_tx.json",
          "w", encoding="utf-8") as f:
    json.dump(RESULTS, f, ensure_ascii=False, indent=1)
