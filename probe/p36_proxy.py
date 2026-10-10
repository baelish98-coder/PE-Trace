# -*- coding: utf-8 -*-
"""Round 9: price proxies for the PE-but-no-price indices.

These indices publish a PE history but no free index price feed.  An ETF that
tracks the same index (or a very close cousin) can stand in for the price line,
but it MUST be labelled as a proxy - the PE comes from the index while the
price comes from a fund.

Run: python probe/p36_proxy.py
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from petrace.core import HttpClient, setup_logging  # noqa: E402
from petrace import sources  # noqa: E402

OUT = ROOT / "probe" / "p36_proxy.json"

# (label, target_index, kind, spec)
CANDIDATES = [
    ("MCHI 中国ETF", "MSCI中国", "sina_us", "MCHI"),
    ("KWEB 中概互联ETF", "中概互联50", "sina_us", "KWEB"),
    ("FXI 中国大盘ETF", "中国互联", "sina_us", "FXI"),
    ("INDA 印度ETF", "MSCI印度", "sina_us", "INDA"),
    ("EPI 印度盈利ETF", "MSCI印度", "sina_us", "EPI"),
    ("SMIN 印度小盘ETF", "MSCI印度", "sina_us", "SMIN"),
    ("IVE 标普500价值ETF", "标普价值", "sina_us", "IVE"),
    ("VLUE 美国价值ETF", "标普价值", "sina_us", "VLUE"),
    ("SPYV 标普500价值ETF", "标普价值", "sina_us", "SPYV"),
    ("SPHQ 标普500质量ETF", "标普质量", "sina_us", "SPHQ"),
    ("QUAL 美国质量ETF", "标普质量", "sina_us", "QUAL"),
    ("NOBL 标普红利贵族ETF", "标普红利", "sina_us", "NOBL"),
    ("SPHD 标普高股息ETF", "标普红利", "sina_us", "SPHD"),
    ("SDY 标普高股息ETF", "标普红利", "sina_us", "SDY"),
    ("DIA 道指ETF", "道琼斯工业平均", "sina_us", "DIA"),
    ("sz159920 恒生ETF", "恒生指数", "sina_cn", "sz159920"),
    ("sh513660 恒生中国企业ETF", "恒生国企指数", "sina_cn", "sh513660"),
    ("sh510900 H股ETF", "恒生国企指数", "sina_cn", "sh510900"),
    ("sz159607 中概互联ETF", "中概互联50", "sina_cn", "sz159607"),
    ("sh513050 中概互联ETF", "中概互联50", "sina_cn", "sh513050"),
    ("sh513500 标普500ETF", "标普500", "sina_cn", "sh513500"),
]


def main() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")
    log = setup_logging(verbose=False)
    http = HttpClient(min_interval=0.8, logger=log)
    out = {}
    for label, target, kind, spec in CANDIDATES:
        try:
            rows = sources.PRICE_FETCHERS[kind](http, spec, False)
        except Exception as e:                              # noqa: BLE001
            out[label] = {"target": target, "error": f"{type(e).__name__}: {str(e)[-40:]}"}
            print(f"  {label:26s} ERR  {out[label]['error']}")
            continue
        rec = {"target": target, "kind": kind, "spec": spec, "n": len(rows)}
        if rows:
            rec.update(first=rows[0]["date"], last=rows[-1]["date"],
                       c0=rows[0]["close"], c1=rows[-1]["close"])
            print(f"  {label:26s} OK   n={rec['n']:5d} {rec['first']}→{rec['last']}")
        else:
            print(f"  {label:26s} EMPTY")
        out[label] = rec
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("wrote", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
