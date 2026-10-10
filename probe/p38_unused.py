# -*- coding: utf-8 -*-
"""Round 10b: inventory every danjuan index we are *not* yet using, to see
whether any developed market outside the US/HK carries a usable PE history.

Run: python probe/p38_unused.py
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from petrace.core import HttpClient, setup_logging  # noqa: E402
from petrace import sources, universe  # noqa: E402

OUT = ROOT / "probe" / "p38_unused.json"


def main() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")
    log = setup_logging(verbose=False)
    http = HttpClient(min_interval=0.9, logger=log)
    lst = sources.danjuan_list(http)
    used = {x.get("danjuan") for x in universe.INDICES if x.get("danjuan")}
    out = {}
    for r in sorted(lst, key=lambda x: str(x.get("index_code"))):
        code = r.get("index_code")
        if code in used:
            continue
        rec = {"name": r.get("name"), "spot_pe": r.get("pe")}
        try:
            rows = sources.danjuan_pe(http, code)
        except Exception as e:                              # noqa: BLE001
            rec["err"] = f"{type(e).__name__}: {str(e)[-40:]}"
            rows = []
        rec["n"] = len(rows)
        if rows:
            rec.update(first=rows[0]["date"], last=rows[-1]["date"],
                       last_pe=rows[-1]["pe"])
        out[code] = rec
        print(f"  {code:12s} {str(rec['name'])[:20]:22s} n={rec['n']:4d} "
              f"{rec.get('first','-')}→{rec.get('last','-')} "
              f"pe={rec.get('last_pe')}" + (f" ERR {rec.get('err')}" if rec.get("err") else ""))
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("wrote", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
