# -*- coding: utf-8 -*-
"""Probe: EM retry after cooldown, worldperatio structure, danjuan granularity."""
import sys, io, re, json, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import requests
requests.packages.urllib3.disable_warnings()
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"}

print("### A. eastmoney retry (fresh, paced)")
for sec, name in [("100.SPX", "SP500"), ("100.N225", "N225"), ("1.000300", "CSI300")]:
    u = ("https://push2his.eastmoney.com/api/qt/stock/kline/get?"
         f"secid={sec}&fields1=f1,f2,f3,f4,f5&fields2=f51,f52,f53,f54,f55,f56,f57,f58"
         "&klt=101&fqt=1&beg=0&end=20500101")
    try:
        r = requests.get(u, headers=UA, timeout=25, verify=False)
        j = r.json()
        k = ((j.get("data") or {}).get("klines")) or []
        print(f"  {name:8s} {sec:10s} -> {r.status_code} n={len(k)} {k[0][:10] if k else '-'} -> {k[-1][:10] if k else '-'}")
    except Exception as e:
        print(f"  {name:8s} {sec:10s} -> FAIL {str(e)[:70]}")
    time.sleep(3)
print()

print("### B. eastmoney alternative hosts")
for host in ["push2his.eastmoney.com", "push2.eastmoney.com", "82.push2his.eastmoney.com",
             "push2his.eastmoney.com:443"]:
    u = (f"https://{host}/api/qt/stock/kline/get?secid=100.SPX"
         "&fields1=f1,f2&fields2=f51,f52,f53&klt=101&fqt=1&beg=0&end=20500101")
    try:
        r = requests.get(u, headers=UA, timeout=18, verify=False)
        k = ((r.json().get("data") or {}).get("klines")) or []
        print(f"  {host:32s} -> {r.status_code} n={len(k)}")
    except Exception as e:
        print(f"  {host:32s} -> FAIL {str(e)[:60]}")
print()

print("### C. worldperatio.com")
try:
    r = requests.get("https://www.worldperatio.com/", headers=UA, timeout=25, verify=False)
    print("  status", r.status_code, "len", len(r.text))
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", r.text, re.S)
    print("  rows:", len(rows))
    for row in rows[:12]:
        cells = [re.sub(r"<[^>]+>", "", c).strip() for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S)]
        cells = [c for c in cells if c]
        if cells:
            print("   ", cells[:8])
    links = set(re.findall(r'href="([^"]+)"', r.text))
    print("  sample links:", [l for l in links if "country" in l or "index" in l][:12])
except Exception as e:
    print("  FAIL", str(e)[:150])
print()

print("### D. worldperatio country page")
for p in ["/country/united-states", "/united-states", "/usa"]:
    try:
        r = requests.get(f"https://www.worldperatio.com{p}", headers=UA, timeout=20, verify=False)
        print(f"  {p:22s} -> {r.status_code} len={len(r.text)}")
        if r.status_code == 200 and len(r.text) > 5000:
            txt = re.sub(r"<script.*?</script>", "", r.text, flags=re.S)
            txt = re.sub(r"<[^>]+>", " ", txt)
            txt = re.sub(r"\s+", " ", txt)
            print("   ", txt[:400])
    except Exception as e:
        print(f"  {p:22s} FAIL {str(e)[:60]}")
