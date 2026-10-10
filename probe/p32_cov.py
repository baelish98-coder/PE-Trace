# -*- coding: utf-8 -*-
"""Round 5: map the csindex perf API across the whole PE-Trace universe.

For every universe index, derive candidate csindex codes and record whether
the perf endpoint returns daily close + peg(PE), and how deep the history is.

Run: python probe/p32_cov.py
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

OUT = ROOT / "probe" / "p32_cov.json"
HDR = {"Referer": "https://www.csindex.com.cn/"}
PERF = "https://www.csindex.com.cn/csindex-home/perf/index-perf"


def jdefault(o):
    return str(o)


def candidates(ix) -> list:
    """Derive plausible csindex codes from the universe entry."""
    out = []
    dj = ix.get("danjuan") or ""
    if dj.startswith("CSI") and dj[3:].isdigit():
        out.append(dj[3:])
    if dj[:1] in ("H", "h") and dj[1:6].isdigit():
        out.append(dj.upper())
    if ix["id"][:2] in ("SH", "SZ") and ix["id"][2:].isdigit():
        out.append(ix["id"][2:])
    if ix["id"].isdigit():
        out.append(ix["id"])
    # de-dup, keep order
    seen, res = set(), []
    for c in out:
        if c and c not in seen:
            seen.add(c)
            res.append(c)
    return res


def main() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")
    log = setup_logging(verbose=False)
    http = HttpClient(min_interval=0.9, logger=log)
    out: dict = {}

    for ix in universe.INDICES:
        codes = candidates(ix)
        if not codes:
            out[ix["id"]] = {"name": ix["name"], "codes": [], "hit": None}
            print(f"{ix['id']:12s} {ix['name']:12s} (no candidate code)")
            continue
        hit = None
        for code in codes:
            url = f"{PERF}?indexCode={code}&startDate=20040101&endDate=20261010"
            try:
                obj = http.get_json(url, headers=HDR)
                data = obj.get("data") or []
            except Exception:                                    # noqa: BLE001
                data = []
            if data:
                hit = {"code": code,
                       "n": len(data),
                       "first": data[0].get("tradeDate"),
                       "last": data[-1].get("tradeDate"),
                       "name": data[0].get("indexNameCnAll"),
                       "last_peg": data[-1].get("peg"),
                       "last_close": data[-1].get("close"),
                       "peg_nonnull": sum(1 for r in data if r.get("peg") is not None)}
                break
            time.sleep(0.5)
        out[ix["id"]] = {"name": ix["name"], "codes": codes, "hit": hit}
        if hit:
            print(f"{ix['id']:12s} {ix['name']:12s} -> {hit['code']:8s} "
                  f"n={hit['n']:5d} peg_ok={hit['peg_nonnull']:5d} "
                  f"{hit['first']}→{hit['last']} peg={hit['last_peg']}")
        else:
            print(f"{ix['id']:12s} {ix['name']:12s} -> MISS  (tried {codes})")

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=jdefault),
                   encoding="utf-8")
    hits = [k for k, v in out.items() if v.get("hit")]
    print(f"\n{len(hits)}/{len(universe.INDICES)} covered by csindex perf")
    print("wrote", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
