# -*- coding: utf-8 -*-
"""P16: can legulegu monthly PE consistently extend danjuan weekly PE backwards?

If the two series agree over their overlap, we can splice them to give A-share
indices a 2005-onward PE history (much better for a 10-year rolling window).
If they disagree, splicing would fabricate a level shift and we must not do it.
"""
import io
import json
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, r"C:\Users\Administrator\Documents\dsh-workplace\fund-PETrace")

from petrace.core import HttpClient, ensure_dirs
from petrace import sources

ensure_dirs()
h = HttpClient(min_interval=1.5)

PAIRS = [
    ("沪深300", "SH000300"),
    ("上证50", "SH000016"),
    ("中证500", "SH000905"),
    ("中证1000", "SH000852"),
    ("上证180", "SH000010"),
    ("中证100", "SH000903"),
    ("深证100", "SZ399330"),
    ("深证红利", "SZ399324"),
    ("上证红利", "SH000015"),
    ("上证380", "SH000380"),
    ("创业板50", "SZ399673"),
    ("中证800", "SH000906"),
]

report = {}
for lg_name, dj_code in PAIRS:
    print("=" * 78)
    print(f"{lg_name}   danjuan={dj_code}")
    dj = sources.danjuan_pe(h, dj_code)
    try:
        lg = sources.legulegu_pe(lg_name)
    except Exception as e:
        print(f"  legulegu '{lg_name}' FAILED: {type(e).__name__}: {str(e)[:90]}")
        lg = []
    print(f"  danjuan n={len(dj):>4} {dj[0]['date'] if dj else '-'} -> {dj[-1]['date'] if dj else '-'}")
    print(f"  legulegu n={len(lg):>4} {lg[0]['date'] if lg else '-'} -> {lg[-1]['date'] if lg else '-'}")

    if dj and lg:
        # compare on legulegu's monthly points that fall inside danjuan's range
        djm = {r["date"]: r["pe"] for r in dj}
        dj_dates = sorted(djm)
        common = []
        for r in lg:
            d = r["date"]
            if dj_dates[0] <= d <= dj_dates[-1]:
                # nearest danjuan observation within 5 days
                best, bd = None, None
                for dd in dj_dates:
                    gap = abs((__import__("datetime").date.fromisoformat(dd)
                               - __import__("datetime").date.fromisoformat(d)).days)
                    if bd is None or gap < bd:
                        bd, best = gap, dd
                if best is not None and bd <= 5:
                    common.append((d, r["pe"], djm[best], r["pe"] / djm[best] - 1))
        if common:
            ratios = [c[3] for c in common]
            mean_r = sum(ratios) / len(ratios)
            print(f"  overlap n={len(common)}  ratio(legulegu/danjuan) "
                  f"mean={mean_r:+.4f} min={min(ratios):+.4f} max={max(ratios):+.4f}")
            print(f"  last 3 overlap: " + "  ".join(
                f"{d} lg={l:.2f} dj={jd:.2f} ({rr:+.1%})" for d, l, jd, rr in common[-3:]))
            report[dj_code] = {"name": lg_name, "n_overlap": len(common),
                               "ratio_mean": round(mean_r, 4),
                               "ratio_min": round(min(ratios), 4),
                               "ratio_max": round(max(ratios), 4),
                               "dj_first": dj_dates[0],
                               "lg_first": lg[0]["date"], "lg_n": len(lg)}
        else:
            print("  overlap n=0 (series do not intersect in time)")
            report[dj_code] = {"name": lg_name, "n_overlap": 0,
                               "dj_first": dj_dates[0], "lg_first": lg[0]["date"],
                               "lg_n": len(lg)}

with open("probe/p16_splice.json", "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=1)
print("\nwrote probe/p16_splice.json")
