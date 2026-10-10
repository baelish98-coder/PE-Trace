# -*- coding: utf-8 -*-
"""Round 7: trustworthy csindex perf coverage map.

p32_cov.py under-reported because a single throttled response was read as
"code absent".  Here every code gets 3 attempts with backoff, and a code is
only called a miss after all attempts returned an empty list (the API answers
{"msg":"Success","data":[]} for a genuinely absent code, and raises/returns
null when throttled).

Recorded per code: n, first/last close date, first/last non-null peg date,
last peg value, last close.

Run: python probe/p34_cov2.py
"""
from __future__ import annotations

import io
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from petrace import universe                        # noqa: E402
from petrace.core import HttpClient, setup_logging  # noqa: E402

OUT = ROOT / "probe" / "p34_cov2.json"
HDR = {"Referer": "https://www.csindex.com.cn/"}
PERF = "https://www.csindex.com.cn/csindex-home/perf/index-perf"


def jdefault(o):
    return str(o)


def candidates(ix) -> list:
    out = []
    dj = (ix.get("danjuan") or "").upper()
    if dj.startswith("CSI") and dj[3:].isdigit():
        out.append(dj[3:])
    if dj.startswith("CSIH") and dj[4:].isdigit():
        out.append("H" + dj[4:])
    if ix["id"][:2] in ("SH", "SZ") and ix["id"][2:].isdigit():
        out.append(ix["id"][2:])
    if ix["id"].isdigit():
        out.append(ix["id"])
    seen, res = set(), []
    for c in out:
        if c and c not in seen:
            seen.add(c)
            res.append(c)
    return res


def probe(http, code, log) -> dict:
    """Return {'absent':True} only when the API clearly says 'no such code'."""
    last = ""
    for attempt in range(3):
        if attempt:
            time.sleep(2.0 * attempt)
        try:
            obj = http.get_json(
                f"{PERF}?indexCode={code}&startDate=20040101&endDate=20261010",
                headers=HDR)
        except Exception as e:                                   # noqa: BLE001
            last = f"{type(e).__name__}: {str(e)[:60]}"
            continue
        if not isinstance(obj, dict):
            last = "non-dict response"
            continue
        data = obj.get("data")
        if isinstance(data, list) and data:
            pegs = [r for r in data if r.get("peg") is not None]
            return {"absent": False, "n": len(data),
                    "first": data[0].get("tradeDate"),
                    "last": data[-1].get("tradeDate"),
                    "peg_n": len(pegs),
                    "peg_first": pegs[0]["tradeDate"] if pegs else None,
                    "peg_last": pegs[-1]["tradeDate"] if pegs else None,
                    "last_peg": data[-1].get("peg"),
                    "last_close": data[-1].get("close"),
                    "name": data[0].get("indexNameCnAll")}
        # data == [] -> genuinely absent for this code
        return {"absent": True, "msg": obj.get("msg")}
    return {"absent": None, "error": last}


def main() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")
    log = setup_logging(verbose=False)
    http = HttpClient(min_interval=1.0, logger=log)
    out: dict = {}

    for ix in universe.INDICES:
        codes = candidates(ix)
        rec = {"name": ix["name"], "region": ix["region"], "codes": codes, "hit": None}
        for code in codes:
            r = probe(http, code, log)
            if r.get("absent") is False:
                rec["hit"] = dict(r, code=code)
                break
            if r.get("absent") is None:
                rec["error"] = r.get("error")
        out[ix["id"]] = rec
        h = rec["hit"]
        if h:
            print(f"{ix['id']:12s} {ix['name']:12s} -> {h['code']:8s} "
                  f"close n={h['n']:5d} {h['first']} | "
                  f"PE n={h['peg_n']:5d} {h['peg_first']}→{h['peg_last']} "
                  f"lastPE={h['last_peg']}")
        else:
            print(f"{ix['id']:12s} {ix['name']:12s} -> MISS {codes} "
                  f"{rec.get('error') or ''}")

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=jdefault),
                   encoding="utf-8")
    hits = [k for k, v in out.items() if v.get("hit")]
    print(f"\n{len(hits)}/{len(universe.INDICES)} covered: {hits}")
    print("wrote", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
