# -*- coding: utf-8 -*-
"""p27 - verify final per-index price source chains (sina_cn / tencent / sina_gi / sina_us)."""
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


def sina_cn(code):
    r = requests.get("https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/"
                     "CN_MarketData.getKLineData",
                     params={"symbol": code, "scale": 240, "ma": "no", "datalen": 6000},
                     headers={"User-Agent": UA, "Referer": "https://finance.sina.com.cn/"},
                     timeout=25, verify=False)
    a = json.loads(r.text)
    return {"n": len(a), "first": a[0]["day"], "last": a[-1]["day"], "c": a[-1]["close"]}


def tencent(code, period="day", cnt=2000):
    r = requests.get("https://web.ifzq.gtimg.cn/appstock/app/fqkline/get",
                     params={"param": f"{code},{period},,,{cnt},qfq"},
                     headers={"User-Agent": UA}, timeout=25, verify=False)
    j = r.json()
    d = (j.get("data") or {}).get(code) or {}
    kl = d.get(period) or d.get("qfq" + period) or d.get("day") or []
    if not kl:
        return {"n": 0}
    return {"n": len(kl), "first": kl[0][0], "last": kl[-1][0], "c": kl[-1][2]}


def sina_gi(code):
    r = requests.get("https://gi.finance.sina.com.cn/hq/daily",
                     params={"symbol": code, "num": "1000"},
                     headers={"User-Agent": UA}, timeout=25, verify=False)
    d = (r.json().get("result") or {}).get("data") or []
    if not d:
        return {"n": 0}
    return {"n": len(d), "first": d[0]["d"], "last": d[-1]["d"], "c": d[-1]["c"]}


def sina_us(sym):
    r = requests.get("https://stock.finance.sina.com.cn/usstock/api/jsonp.php/var%20a=/"
                     "US_MinKService.getDailyK",
                     params={"symbol": sym, "___qn": "3"},
                     headers={"User-Agent": UA, "Referer": "https://stock.finance.sina.com.cn/"},
                     timeout=25, verify=False)
    t = r.text
    i, j2 = t.find("(["), t.rfind("])")
    arr = json.loads(t[i + 1:j2 + 1])
    return {"n": len(arr), "first": arr[0]["d"], "last": arr[-1]["d"], "c": arr[-1]["c"]}


def run(name, fn, *a):
    t = time.time()
    try:
        res = fn(*a)
    except Exception as e:
        res = {"error": f"{type(e).__name__}: {str(e)[:80]}"}
    res["sec"] = round(time.time() - t, 2)
    OUT[name] = res
    ok = "n=%s" % res.get("n") if res.get("n") else res.get("error", res)
    print(f"  {name:34s} {json.dumps(res, ensure_ascii=False)[:190]}")
    time.sleep(0.8)
    return res


print("########## A. A-share indices: sina_cn + tencent(day/week)")
ASHARE = {
    "SH000300": "sh000300", "SH000016": "sh000016", "SH000905": "sh000905",
    "SH000852": "sh000852", "SH000688": "sh000688", "SZ399006": "sz399006",
    "SH000903": "sh000903", "SH000010": "sh000010", "SZ399001": "sz399001",
    "SZ399330": "sz399330", "SZ399324": "sz399324", "SH000015": "sh000015",
    "SH000922": "sh000922", "SH000925": "sh000925", "SH000919": "sh000919",
    "SZ399317": "sz399317", "SZ399550": "sz399550", "SH000170": "sh000170",
    "SH000991": "sh000991", "SH000932": "sh000932", "SH000993": "sh000993",
    "SH000009": "sh000009", "SZ399673": "sz399673", "SH000906": "sh000906",
    "CSI716567": None, "CSI930652": None, "CSI931087": None,
}
for iid, code in ASHARE.items():
    if not code:
        continue
    run(f"sina_cn_{iid}", sina_cn, code)
    run(f"tx_day_{iid}", tencent, code, "day")

print("\n########## B. HK indices: tencent day/week + sina_cn")
for iid, code in [("HKHSI", "hkHSI"), ("HKHSCEI", "hkHSCEI"),
                  ("HKHSTECH", "hkHSTECH")]:
    run(f"tx_day_{iid}", tencent, code, "day", 2000)
    run(f"tx_week_{iid}", tencent, code, "week", 2000)

print("\n########## C. US indices: sina_us")
for iid, sym in [("SP500", ".INX"), ("NDX", ".NDX"), ("DJI", ".DJI"),
                 ("NASDAQ", ".IXIC")]:
    run(f"sina_us_{iid}", sina_us, sym)

print("\n########## D. Global developed: sina_gi")
for iid, code in [("FTSE", "UKX"), ("FCHI", "CAC"), ("SX5E", "SX5E"),
                  ("AEX", "AEX"), ("IBEX", "IBEX"), ("MIB", "FTSEMIB"),
                  ("GDAXI", "DAX"), ("N225", "NKY"), ("KS11", "KOSPI"),
                  ("AS51", "AS51"), ("TWII", "TWJQ"), ("SMI", "SWI20"),
                  ("GSPTSE", "GSPTSE"), ("SENSEX", "SENSEX")]:
    run(f"sina_gi_{iid}", sina_gi, code)

print("\n########## E. DAX deep-history attempts")
for name, url, params in [
    ("sohu_dax", "https://q.stock.sohu.com/hisHq",
     {"code": "znb_DAX", "start": "20050101", "end": "20261009", "stat": "1", "order": "D", "period": "d", "callback": "", "rt": "json"}),
    ("hexun_dax", "https://webforex.hermes.hexun.com/forex/kline",
     {"code": "DAX", "start": "20050101", "number": "-2500", "type": "day"}),
]:
    try:
        r = requests.get(url, params=params, headers={"User-Agent": UA}, timeout=20, verify=False)
        rec = {"status": r.status_code, "len": len(r.content), "body": r.text[:200]}
    except Exception as e:
        rec = {"error": f"{type(e).__name__}: {str(e)[:80]}"}
    OUT[name] = rec
    print(f"  {name:30s} {json.dumps(rec, ensure_ascii=False)[:280]}")
    time.sleep(1.2)

print("\n########## F. eastmoney health")
for i in range(2):
    try:
        r = requests.get("https://push2his.eastmoney.com/api/qt/stock/kline/get"
                         "?secid=100.GDAXI&fields1=f1&fields2=f51,f53&klt=101&fqt=1&beg=0&end=20500101",
                         headers={"User-Agent": UA}, timeout=12, verify=False)
        print(f"  em{i}: {r.status_code} {len(r.content)}")
        OUT[f"em_health{i}"] = {"status": r.status_code}
        break
    except Exception as e:
        print(f"  em{i}: ERR {type(e).__name__}")
        OUT[f"em_health{i}"] = {"error": type(e).__name__}
    time.sleep(5)

with open(r"C:\Users\Administrator\Documents\dsh-workplace\fund-PETrace\probe\p27_matrix.json",
          "w", encoding="utf-8") as f:
    json.dump(OUT, f, ensure_ascii=False, indent=1)
print("\nwrote probe/p27_matrix.json")
