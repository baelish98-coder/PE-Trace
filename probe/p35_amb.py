# -*- coding: utf-8 -*-
"""Round 8: resolve the ambiguous csindex codes.

p34 marked some codes MISS via HttpError (transport failure, could be
throttling) rather than an empty data list.  Those are worth retrying slowly:
中证/上证 indices should exist; 深证/国证 (399xxx) belong to a different
index company and are expected to be genuinely absent.

Run: python probe/p35_amb.py
"""
from __future__ import annotations

import io
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from petrace.core import HttpClient, setup_logging  # noqa: E402

OUT = ROOT / "probe" / "p35_amb.json"
HDR = {"Referer": "https://www.csindex.com.cn/"}
PERF = "https://www.csindex.com.cn/csindex-home/perf/index-perf"

# (code, expected_owner)
CODES = [
    ("000688", "中证/科创50"), ("399006", "深证/创业板指"),
    ("399001", "深证/深证成指"), ("399330", "深证/深证100"),
    ("399324", "深证/深证红利"), ("399317", "国证/A指"),
    ("000925", "中证/基本面50"), ("000919", "中证/300价值"),
    ("000170", "中证/50AH优选"), ("399550", "央视/央视50"),
    ("399673", "深证/创业板50"), ("716567", "MSCI中国"),
    ("935600", "MSCI印度"), ("000015", "上证/上证红利"),
    ("000922", "中证/中证红利"), ("H30533", "中证/中概互联50"),
    ("H30269", "中证/红利低波"), ("930740", "中证/300红利LV"),
    ("930782", "中证/500低波"), ("931157", "中证/红利成长LV"),
    ("930740", "中证/300红利LV"), ("H30094", "中证/消费红利"),
    ("931079", "中证/5G通讯"), ("931142", "中证/东证竞争"),
]


def main() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")
    log = setup_logging(verbose=False)
    http = HttpClient(min_interval=1.6, logger=log)
    out: dict = {}

    for code, owner in CODES:
        if code in out:
            continue
        rec = {"owner": owner}
        for attempt in range(3):
            if attempt:
                time.sleep(4.0 * attempt)
            try:
                obj = http.get_json(
                    f"{PERF}?indexCode={code}&startDate=20040101&endDate=20261010",
                    headers=HDR)
            except Exception as e:                                # noqa: BLE001
                rec = {"owner": owner, "error": f"{type(e).__name__}: {str(e)[-50:]}"}
                continue
            data = (obj or {}).get("data")
            if isinstance(data, list) and data:
                pegs = [r for r in data if r.get("peg") is not None]
                rec = {"owner": owner, "n": len(data),
                       "first": data[0].get("tradeDate"),
                       "last": data[-1].get("tradeDate"),
                       "name": data[0].get("indexNameCnAll"),
                       "peg_n": len(pegs),
                       "peg_first": pegs[0]["tradeDate"] if pegs else None,
                       "last_peg": data[-1].get("peg")}
                break
            rec = {"owner": owner, "absent": True, "msg": (obj or {}).get("msg")}
            break
        out[code] = rec
        if rec.get("n"):
            print(f"  {code:8s} OK  n={rec['n']:5d} PE={rec['peg_n']:5d} "
                  f"from {rec['peg_first']} lastPE={rec['last_peg']} {rec['name']}")
        else:
            print(f"  {code:8s} --- {rec.get('error') or 'absent'} ({owner})")

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    ok = [c for c, v in out.items() if v.get("n")]
    print(f"\nworking: {ok}")
    print("wrote", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
