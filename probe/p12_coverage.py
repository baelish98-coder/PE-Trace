# -*- coding: utf-8 -*-
"""
Paced coverage probe. Distinguishes TRUE-EMPTY from RATE-LIMITED by
interleaving a known-good control (SP500) and retrying with backoff.

Outputs probe/coverage_danjuan.json and probe/coverage_em.json
"""
import sys, io, json, time, os, datetime
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import requests
requests.packages.urllib3.disable_warnings()

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"}
HERE = os.path.dirname(os.path.abspath(__file__))
SESSION = requests.Session()
SESSION.headers.update(UA)


def fetch_json(url, tries=4, base_sleep=1.5):
    last = None
    for i in range(tries):
        try:
            r = SESSION.get(url, timeout=25, verify=False)
            if r.status_code == 200:
                return r.json(), None
            last = f"HTTP{r.status_code}"
        except Exception as e:
            last = f"{type(e).__name__}:{str(e)[:60]}"
        time.sleep(base_sleep * (i + 1))
    return None, last


def control_ok():
    """SP500 is known to have history - use as a liveness control."""
    j, err = fetch_json(
        "https://danjuanfunds.com/djapi/index_eva/pe_history/SP500?day=all", tries=3)
    if not j:
        return False
    return bool(((j.get("data") or {}).get("index_eva_pe_growths")))


# ------------------------------------------------------------------ danjuan
DANJUAN_CODES = [
    # A-share / China
    "SH000300", "SH000905", "SH000016", "SH000010", "SH000903", "SH000852",
    "SH000688", "SH000922", "SH000015", "SH000919", "SZ399006", "SZ399001",
    "SZ399330", "SZ399324", "SZ399550", "SH000925", "SH000170", "SH000991",
    "SH000932", "SH000993", "SZ399317", "CSI716567", "CSI931087", "CSI930652",
    # Hong Kong
    "HKHSI", "HKHSCEI", "HKHSTECH", "HSFML25", "HKHSSCNE", "SPHCMSHP", "CSIH11136",
    # United States
    "SP500", "NDX", "DJI", "RUT", "NASDAQ", "SPACEVCP", "SPCQVCP", "CSPSADRP",
    # Developed Europe / others
    "GDAXI", "UKX", "FCHI", "SX5E", "STOXX50", "SSMI", "SMI", "AEX", "IBEX",
    "FTSEMIB", "OMX", "OMXS30", "OSEBX", "HEX", "ISEQ",
    # Developed Asia-Pacific
    "N225", "NKY", "TOPIX", "KOSPI", "KS11", "AS51", "AXJO", "TWII", "NZ250",
    "GSPTSE", "SPTSX", "HSI",
    # Emerging / other
    "935600", "MSCIIN", "MSCIEM", "MSCIACWI", "MSCIWORLD", "MSCIEF",
    "IBOV", "MXX", "SENSEX", "JCI", "SET", "PSEI", "VNINDEX",
]

print("### DANJUAN coverage probe (paced)\n", flush=True)
danjuan_result = {}
for idx, code in enumerate(DANJUAN_CODES):
    url = f"https://danjuanfunds.com/djapi/index_eva/pe_history/{code}?day=all"
    j, err = fetch_json(url, tries=3, base_sleep=1.2)
    g = ((j or {}).get("data") or {}).get("index_eva_pe_growths") or []
    if g:
        t0 = datetime.datetime.fromtimestamp(g[0]["ts"] / 1000, datetime.UTC).date()
        t1 = datetime.datetime.fromtimestamp(g[-1]["ts"] / 1000, datetime.UTC).date()
        danjuan_result[code] = {"n": len(g), "start": str(t0), "end": str(t1),
                                "last_pe": g[-1]["pe"], "status": "ok"}
        print(f"  [{idx:02d}] {code:11s} OK    n={len(g):5d} {t0} -> {t1}", flush=True)
    else:
        # retry once more slowly, with liveness control
        alive = control_ok()
        j2, err2 = fetch_json(url, tries=3, base_sleep=2.5)
        g2 = ((j2 or {}).get("data") or {}).get("index_eva_pe_growths") or []
        if g2:
            t0 = datetime.datetime.fromtimestamp(g2[0]["ts"] / 1000, datetime.UTC).date()
            t1 = datetime.datetime.fromtimestamp(g2[-1]["ts"] / 1000, datetime.UTC).date()
            danjuan_result[code] = {"n": len(g2), "start": str(t0), "end": str(t1),
                                    "last_pe": g2[-1]["pe"], "status": "ok"}
            print(f"  [{idx:02d}] {code:11s} OK*   n={len(g2):5d} {t0} -> {t1}", flush=True)
        else:
            status = "empty" if alive else "unclear"
            danjuan_result[code] = {"status": status, "err": err2 or err,
                                    "control_alive": alive}
            print(f"  [{idx:02d}] {code:11s} {status.upper():7s} err={err2 or err} "
                  f"ctrl={alive}", flush=True)
    time.sleep(0.7)

with open(os.path.join(HERE, "coverage_danjuan.json"), "w", encoding="utf-8") as f:
    json.dump(danjuan_result, f, ensure_ascii=False, indent=1)
print(f"\n=> danjuan OK count: {sum(1 for v in danjuan_result.values() if v['status']=='ok')}"
      f" / {len(DANJUAN_CODES)}\n", flush=True)


# --------------------------------------------------------------- eastmoney
EM = {
    "S&P 500": "100.SPX", "Nasdaq 100": "100.NDX", "Dow Jones": "100.DJI",
    "Russell 2000": "100.RUT", "DAX": "100.GDAXI", "FTSE 100": "100.UKX",
    "CAC 40": "100.CAC", "Euro Stoxx 50": "100.SX5E", "SMI": "100.SMI",
    "AEX": "100.AEX", "IBEX 35": "100.IBEX", "FTSE MIB": "100.FTSEMIB",
    "OMX Stockholm 30": "100.OMXS30", "Nikkei 225": "100.N225", "TOPIX": "100.TOPX",
    "KOSPI": "100.KS11", "ASX 200": "100.AS51", "TWSE": "100.TWII",
    "S&P/TSX": "100.GSPTSE", "Hang Seng": "100.HSI", "HSCEI": "100.HSCEI",
    "Hang Seng Tech": "100.HSTECH", "CSI 300": "1.000300", "CSI 500": "1.000905",
    "SSE 50": "1.000016", "CSI 1000": "1.000852", "STAR 50": "1.000688",
    "ChiNext": "0.399006", "SZSE Component": "0.399001", "SSE Composite": "1.000001",
    "CSI 100": "1.000903", "Shenzhen 100": "0.399330",
}

print("### EASTMONEY price coverage probe (paced)\n", flush=True)
em_result = {}
for idx, (name, sec) in enumerate(EM.items()):
    url = ("https://push2his.eastmoney.com/api/qt/stock/kline/get?"
           f"secid={sec}&fields1=f1,f2,f3,f4,f5&fields2=f51,f52,f53,f54,f55,f56,f57,f58"
           "&klt=101&fqt=1&beg=0&end=20500101")
    k = []
    err = None
    for attempt in range(4):
        try:
            r = SESSION.get(url, timeout=25, verify=False)
            k = ((r.json().get("data") or {}).get("klines")) or []
            if k:
                break
            err = "empty"
        except Exception as e:
            err = f"{type(e).__name__}:{str(e)[:50]}"
        time.sleep(1.8 * (attempt + 1))
    if k:
        em_result[sec] = {"name": name, "n": len(k), "start": k[0][:10],
                          "end": k[-1][:10], "status": "ok"}
        print(f"  [{idx:02d}] {name:22s} {sec:11s} OK n={len(k):6d} {k[0][:10]} -> {k[-1][:10]}",
              flush=True)
    else:
        em_result[sec] = {"name": name, "status": "fail", "err": err}
        print(f"  [{idx:02d}] {name:22s} {sec:11s} FAIL {err}", flush=True)
    time.sleep(0.8)

with open(os.path.join(HERE, "coverage_em.json"), "w", encoding="utf-8") as f:
    json.dump(em_result, f, ensure_ascii=False, indent=1)
print(f"\n=> eastmoney OK count: {sum(1 for v in em_result.values() if v['status']=='ok')}"
      f" / {len(EM)}", flush=True)
