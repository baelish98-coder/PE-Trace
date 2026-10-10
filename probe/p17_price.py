# -*- coding: utf-8 -*-
"""p17 - find a price source that works while eastmoney has us blocked."""
import io
import json
import sys
import time
import traceback

sys.path.insert(0, r"C:\Users\Administrator\Documents\dsh-workplace\fund-PETrace")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import requests  # noqa: E402
import urllib3  # noqa: E402

urllib3.disable_warnings()

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

RESULTS = {}


def probe(name, url, *, headers=None, parser=None):
    h = {"User-Agent": UA}
    if headers:
        h.update(headers)
    t = time.time()
    rec = {"url": url}
    try:
        r = requests.get(url, headers=h, timeout=20, verify=False)
        rec["status"] = r.status_code
        rec["len"] = len(r.content)
        rec["sec"] = round(time.time() - t, 2)
        body = r.text
        if parser:
            try:
                rec["parsed"] = parser(body)
            except Exception as e:
                rec["parse_err"] = f"{type(e).__name__}: {e}"[:200]
        else:
            rec["head"] = body[:220]
    except Exception as e:
        rec["error"] = f"{type(e).__name__}: {str(e)[:150]}"
        rec["sec"] = round(time.time() - t, 2)
    RESULTS[name] = rec
    print(f"{name:34s} {json.dumps(rec, ensure_ascii=False)[:300]}")
    time.sleep(2.0)
    return rec


def tencent_parse(body):
    j = json.loads(body)
    d = j.get("data", {})
    out = []
    for code, payload in d.items():
        if not isinstance(payload, dict):
            continue
        kl = payload.get("day") or payload.get("qfqday") or []
        if kl:
            out.append({"code": code, "n": len(kl),
                        "first": kl[0][0], "last": kl[-1][0],
                        "lastclose": kl[-1][2]})
    return out


print("=== Tencent ifzq (A-share) ===")
probe("tx_sh000300",
      "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sh000300,day,,,8000,qfq",
      parser=tencent_parse)
probe("tx_sz399006",
      "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sz399006,day,,,8000,qfq",
      parser=tencent_parse)

print("=== Tencent ifzq (global) ===")
for code in ["usSPX", "usINX", "usDJI", "usIXIC", "usNDX", "hkHSI", "hkHSCEI",
             "deDAX", "ukFTSE", "jpNI225", "frCAC", "sh000001"]:
    probe(f"tx_{code}",
          f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={code},day,,,8000,qfq",
          parser=tencent_parse)

print("=== Sina hq (quote) ===")
probe("sina_quote_sh000300",
      "https://hq.sinajs.cn/list=sh000300,sz399006,sh000001,int_hangseng,int_dji,int_nasdaq,int_sp500",
      headers={"Referer": "https://finance.sina.com.cn/"})

print("=== Sina hisdata js ===")
probe("sina_his_sh000300",
      "https://finance.sina.com.cn/realstock/company/sh000300/hisdata/klc_kl.js",
      headers={"Referer": "https://finance.sina.com.cn/"})

print("=== Eastmoney retry (single, paced) ===")
probe("em_retry",
      "https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=1.000300"
      "&fields1=f1,f2,f3,f4,f5&fields2=f51,f52,f53,f54,f55,f56,f57,f58"
      "&klt=101&fqt=1&beg=0&end=20500101")

with open(r"C:\Users\Administrator\Documents\dsh-workplace\fund-PETrace\probe\p17_price.json",
          "w", encoding="utf-8") as f:
    json.dump(RESULTS, f, ensure_ascii=False, indent=1)
print("\nwrote probe/p17_price.json")
