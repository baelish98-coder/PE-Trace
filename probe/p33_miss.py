# -*- coding: utf-8 -*-
"""Round 6: why do 000016/000905/000903/000010 miss the perf API, and when
does peg history actually start?

Hypotheses for the misses:
  H1 date range too wide -> server refuses
  H2 these are served by a different csindex endpoint / indexCode prefix
  H3 they are genuinely absent from the perf dataset

Also record the first non-null peg date per working code so the UI can state
the true PE depth (peg starts later than close).

Run: python probe/p33_miss.py
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

OUT = ROOT / "probe" / "p33_miss.json"
HDR = {"Referer": "https://www.csindex.com.cn/"}
PERF = "https://www.csindex.com.cn/csindex-home/perf/index-perf"


def jdefault(o):
    return str(o)


def main() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")
    log = setup_logging(verbose=False)
    http = HttpClient(min_interval=0.9, logger=log)
    out: dict = {}

    # ---- H1: narrow ranges for the missing 上证 codes --------------------
    print("=== H1. narrow date ranges for missing 上证 codes ===")
    for code in ("000016", "000905", "000903", "000010", "000015", "000922"):
        for rng in (("20260101", "20261010"), ("20200101", "20261010"),
                    ("20040101", "20261010")):
            url = (f"{PERF}?indexCode={code}"
                   f"&startDate={rng[0]}&endDate={rng[1]}")
            try:
                obj = http.get_json(url, headers=HDR)
                data = obj.get("data")
                n = len(data) if isinstance(data, list) else -1
                msg = obj.get("msg")
            except Exception as e:                               # noqa: BLE001
                n, msg = -2, f"{type(e).__name__}: {str(e)[:50]}"
            print(f"  {code} {rng[0]}..{rng[1]}  n={n}  msg={msg}")
            out[f"h1:{code}:{rng[0]}"] = {"n": n, "msg": msg}
            time.sleep(0.8)

    # ---- H2: alternate endpoints for 上证50 ------------------------------
    print("\n=== H2. alternate endpoints for 000016 ===")
    alts = [
        ("perf-idx", f"{PERF}?indexCode=000016"),
        ("perf-h", f"{PERF}?indexCode=H00016"),
        ("perf-sh", f"{PERF}?indexCode=SH000016"),
        ("perf-cs", f"{PERF}?indexCode=000016&indexType=1"),
        ("perf-idxCode", "https://www.csindex.com.cn/csindex-home/perf/index-perf?indexCode=000016&startDate=20240101&endDate=20261010&type=1"),
    ]
    for label, url in alts:
        try:
            obj = http.get_json(url, headers=HDR)
            s = json.dumps(obj, ensure_ascii=False, default=jdefault)
            out[f"h2:{label}"] = {"len": len(s), "head": s[:200]}
            print(f"  {label:14s} {s[:150]}")
        except Exception as e:                                   # noqa: BLE001
            out[f"h2:{label}"] = {"error": f"{type(e).__name__}: {str(e)[:70]}"}
            print(f"  {label:14s} FAIL {type(e).__name__} {str(e)[:60]}")
        time.sleep(0.8)

    # ---- H3: peg depth per working code ----------------------------------
    print("\n=== H3. peg depth (first non-null peg) per working code ===")
    for code in ("000300", "000852", "000991", "000932", "000993",
                 "000009", "000906", "930652", "931087", "H11136", "H30533"):
        try:
            obj = http.get_json(
                f"{PERF}?indexCode={code}&startDate=20040101&endDate=20261010",
                headers=HDR)
            data = obj.get("data") or []
            pegs = [r for r in data if r.get("peg") is not None]
            rec = {"n": len(data), "peg_n": len(pegs),
                   "peg_first": pegs[0]["tradeDate"] if pegs else None,
                   "peg_last": pegs[-1]["tradeDate"] if pegs else None,
                   "close_first": data[0]["tradeDate"] if data else None}
            out[f"h3:{code}"] = rec
            print(f"  {code:8s} close n={rec['n']:5d} from {rec['close_first']} | "
                  f"peg n={rec['peg_n']:5d} {rec['peg_first']}→{rec['peg_last']}")
        except Exception as e:                                   # noqa: BLE001
            out[f"h3:{code}"] = {"error": f"{type(e).__name__}: {str(e)[:70]}"}
            print(f"  {code:8s} FAIL {type(e).__name__} {str(e)[:60]}")
        time.sleep(0.9)

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=jdefault),
                   encoding="utf-8")
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
