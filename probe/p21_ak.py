# -*- coding: utf-8 -*-
"""p21 - akshare global index daily + tencent us/hk fqkline variants."""
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


def get(name, url, headers=None, show=200):
    h = {"User-Agent": UA}
    if headers:
        h.update(headers)
    try:
        r = requests.get(url, headers=h, timeout=25, verify=False)
        rec = {"status": r.status_code, "len": len(r.content), "body": r.text[:show]}
    except Exception as e:
        rec = {"error": f"{type(e).__name__}: {str(e)[:110]}"}
    OUT[name] = rec
    print(f"{name:26s} {json.dumps(rec, ensure_ascii=False)[:320]}")
    time.sleep(1.2)
    return rec


print("########## A. tencent us/hk fqkline + other endpoints")
for name, url in [
    ("tx_usfq_usINX", "https://web.ifzq.gtimg.cn/appstock/app/usfqkline/get?param=usINX,day,,,2000,qfq"),
    ("tx_usfq_usSPX", "https://web.ifzq.gtimg.cn/appstock/app/usfqkline/get?param=usSPX,day,,,2000,qfq"),
    ("tx_hkfq_hkHSI", "https://web.ifzq.gtimg.cn/appstock/app/hkfqkline/get?param=hkHSI,day,,,2000,qfq"),
    ("tx_dayq_usINX", "https://web.ifzq.gtimg.cn/appstock/app/day/query?code=usINX"),
    ("tx_usINX_dot", "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=us.INX,day,,,2000,qfq"),
    ("tx_usINX_us", "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=usINX,day,2016-01-01,2026-10-09,2000,qfq"),
    ("tx_usDJI_us", "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=usDJI,day,2016-01-01,2026-10-09,2000,qfq"),
]:
    get(name, url)

print("\n########## B. akshare global index functions")
try:
    import akshare as ak
    print("akshare", ak.__version__)
except Exception as e:
    print("ak import fail", e)
    ak = None

if ak:
    for fn, kw in [
        ("index_us_stock_sina", {"symbol": ".INX"}),
        ("index_us_stock_sina", {"symbol": ".DJI"}),
        ("index_us_stock_sina", {"symbol": ".NDX"}),
        ("stock_hk_index_daily_sina", {"symbol": "HSI"}),
        ("stock_hk_index_daily_em", {"symbol": "HSI"}),
        ("index_investing_global", {"country": "美国", "index_name": "标普500指数",
                                    "period": "每日", "start_date": "20160101",
                                    "end_date": "20261009"}),
    ]:
        try:
            df = getattr(ak, fn)(**kw)
            print(f"  ak.{fn}{kw} -> shape={df.shape}")
            print("     cols:", list(df.columns))
            print("     head:", df.head(2).to_dict("records"))
            OUT[f"ak_{fn}_{list(kw.values())[0]}"] = {
                "shape": list(df.shape), "cols": list(df.columns),
                "first": str(df.iloc[0, 0]), "last": str(df.iloc[-1, 0])}
        except Exception as e:
            print(f"  ak.{fn}{kw} -> ERR {type(e).__name__}: {str(e)[:130]}")
            OUT[f"ak_{fn}_{list(kw.values())[0]}"] = {"error": f"{type(e).__name__}: {str(e)[:130]}"}
        time.sleep(2.5)

print("\n########## C. sina us daily k correct path")
for name, sym in [("sina_usK_.INX", ".INX"), ("sina_usK_$INX", "$INX")]:
    get(name,
        f"https://stock.finance.sina.com.cn/usstock/api/jsonp.php/var%20a=/"
        f"US_MinKService.getDailyK?symbol={sym}&___qn=3",
        headers={"Referer": "https://stock.finance.sina.com.cn/"})

with open(r"C:\Users\Administrator\Documents\dsh-workplace\fund-PETrace\probe\p21_ak.json",
          "w", encoding="utf-8") as f:
    json.dump(OUT, f, ensure_ascii=False, indent=1)
print("\nwrote probe/p21_ak.json")
