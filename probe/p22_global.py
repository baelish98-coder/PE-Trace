# -*- coding: utf-8 -*-
"""p22 - tencent CC.CODE global pattern + akshare global candidates."""
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


def tx(period, code, cnt=2000):
    url = (f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?"
           f"param={code},{period},,,{cnt},qfq")
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=25, verify=False)
        j = r.json()
        if j.get("code") != 0:
            return {"err": j.get("msg", "")[:40]}
        d = (j.get("data") or {}).get(code) or {}
        kl = d.get(period) or d.get("qfq" + period) or d.get("day") or []
        if not kl:
            return {"n": 0}
        return {"n": len(kl), "first": kl[0][0], "last": kl[-1][0]}
    except Exception as e:
        return {"error": f"{type(e).__name__}: {str(e)[:70]}"}


print("########## A. tencent CC.CODE global pattern")
CANDIDATES = [
    "us.INX", "us.DJI", "us.IXIC", "us.NDX", "us.SPX",
    "de.DAX", "de.DAX30", "uk.FTSE", "uk.UKX", "uk.FTSE100",
    "jp.N225", "jp.NI225", "jp.TOPIX", "fr.CAC", "fr.CAC40",
    "eu.SX5E", "eu.STOXX50", "hk.HSI", "hk.HSCEI", "hk.HSTECH",
    "kr.KOSPI", "kr.KS11", "au.AS51", "au.AXJO", "ca.GSPTSE",
    "in.NIFTY", "in.SENSEX", "sg.STI", "nl.AEX", "es.IBEX",
    "it.MIB", "ch.SMI", "se.OMXS30", "tw.TWII",
]
for code in CANDIDATES:
    for period in ("day", "week"):
        r = tx(period, code)
        tag = f"tx_{period}_{code}"
        OUT[tag] = r
        if r.get("n"):
            print(f"  {period:5s} {code:12s} n={r['n']:5d} {r['first']} -> {r['last']}")
        time.sleep(0.75)

print("\n########## B. akshare index_*global* / *_index_daily_* inventory")
import akshare as ak  # noqa: E402
names = [n for n in dir(ak) if "index" in n.lower()]
print("  index-ish fns:", len(names))
for n in sorted(names):
    if any(k in n.lower() for k in ("global", "us_stock", "hk_index", "investing",
                                    "daily_em", "daily_sina")):
        print("   *", n)
OUT["ak_index_fns"] = sorted(n for n in names
                             if any(k in n.lower() for k in ("global", "us_stock",
                                                             "hk_index", "investing")))

for fn, kw in [
    ("index_global_hist_sina", {"symbol": "标普500"}),
    ("stock_zh_index_daily_em", {"symbol": "sh000300"}),
    ("stock_zh_index_daily_tx", {"symbol": "sh000300"}),
    ("index_global_spot_em", {}),
]:
    if not hasattr(ak, fn):
        print(f"  ak.{fn} -> MISSING")
        OUT[f"ak_{fn}"] = "missing"
        continue
    try:
        df = getattr(ak, fn)(**kw)
        print(f"  ak.{fn}{kw} -> shape={df.shape} cols={list(df.columns)[:8]}")
        if len(df):
            print("     head:", df.head(1).to_dict("records"))
            print("     tail:", df.tail(1).to_dict("records"))
        OUT[f"ak_{fn}"] = {"shape": list(df.shape), "cols": list(df.columns)}
    except Exception as e:
        print(f"  ak.{fn}{kw} -> ERR {type(e).__name__}: {str(e)[:110]}")
        OUT[f"ak_{fn}"] = {"error": f"{type(e).__name__}: {str(e)[:110]}"}
    time.sleep(2.0)

with open(r"C:\Users\Administrator\Documents\dsh-workplace\fund-PETrace\probe\p22_global.json",
          "w", encoding="utf-8") as f:
    json.dump(OUT, f, ensure_ascii=False, indent=1)
print("\nwrote probe/p22_global.json")
