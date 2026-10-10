# -*- coding: utf-8 -*-
"""Round 11: hunt for *historical* PE for developed markets outside US/HK.

Known-good so far: A-shares (danjuan/csindex), HK (danjuan), US (danjuan +
multpl), India (danjuan). Missing: Japan, Korea, Taiwan, Australia, most of
Europe. This probes candidate sources for a PE *series* (a single current P/E
is useless for a rolling percentile).

Run: python probe/p39_devpe.py
"""
from __future__ import annotations

import io
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import requests  # noqa: E402
import urllib3  # noqa: E402

from petrace.core import DEFAULT_HEADERS  # noqa: E402

urllib3.disable_warnings()
OUT = ROOT / "probe" / "p39_devpe.json"

CANDIDATES = [
    # label, url, does-this-look-like-a-series?
    ("legulegu-global", "https://legulegu.com/stockdata/global-stock-market-valuation", None),
    ("legulegu-pe-band", "https://legulegu.com/stockdata/index-basic-pe", None),
    ("stockanalysis-ewj", "https://stockanalysis.com/etf/ewj/", None),
    ("stockanalysis-ewj-data", "https://stockanalysis.com/etf/ewj/__data.json", None),
    ("ishares-ewj", "https://www.ishares.com/us/products/239639/ishares-msci-japan-etf", None),
    ("xueqiu-index-pe", "https://stock.xueqiu.com/v5/stock/quote.json?symbol=NI225&extend=detail", None),
    ("em-datacenter", "https://datacenter-web.eastmoney.com/api/data/v1/get?reportName=RPT_VALUEINDEX_DET&columns=ALL&pageSize=5", None),
    ("em-push2", "https://push2.eastmoney.com/api/qt/stock/get?secid=100.N225&fields=f43,f58,f162,f167", None),
    ("sina-global-pe", "https://hq.sinajs.cn/list=znb_NKY", None),
    ("msci-japan-fact", "https://www.msci.com/documents/10199/9f5b1a1e", None),
]


def main() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")
    s = requests.Session()
    s.headers.update(DEFAULT_HEADERS)
    out = {}
    for label, url, _ in CANDIDATES:
        rec = {"url": url}
        try:
            r = s.get(url, timeout=18, verify=False)
            rec["status"] = r.status_code
            rec["len"] = len(r.content)
            body = r.text
            rec["ctype"] = r.headers.get("content-type", "")
            rec["has_pe_word"] = bool(re.search(r"P/?E|市盈率|pe_ratio|peRatio",
                                                body[:400000], re.I))
            rec["sample"] = body[:200].replace("\n", " ")
            print(f"  {label:24s} {r.status_code} len={len(r.content):8d} "
                  f"pe_word={rec['has_pe_word']} {rec['ctype'][:28]}")
        except Exception as e:                              # noqa: BLE001
            rec["err"] = f"{type(e).__name__}: {str(e)[:80]}"
            print(f"  {label:24s} ERR {rec['err']}")
        out[label] = rec
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("wrote", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
