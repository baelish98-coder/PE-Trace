# -*- coding: utf-8 -*-
"""
petrace.build - fetch every upstream, compute the rolling percentiles, emit
the static data layer the web page reads.

Output
------
web/data/manifest.json      run metadata, source registry, gap report
web/data/index/<ID>.json    one file per index: meta + one or more PE series
web/data/summary.json       compact cross-index comparison table

A single index may carry several PE series (e.g. SP500 has danjuan weekly plus
multpl monthly). They are never merged; each keeps its own source label, so a
reader can see which upstream any number came from.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from datetime import datetime

from . import metrics, sources, universe
from .core import (ROOT, CACHE_DIR, DATA_DIR, HttpClient, HttpError, ensure_dirs,
                   read_json, setup_logging, write_json)

# Series identity: (series_id, source_tag, label, frequency description)
SERIES_DANJUAN = ("danjuan", "danjuan:pe_history", "蛋卷(周频)", "W")
SERIES_LEGULEGU = ("legulegu", "legulegu:rolling_pe", "乐咕乐股(月频)", "M")
SERIES_MULTPL = ("multpl", "multpl:pe", "multpl(月频)", "M")
SERIES_CSINDEX = ("csindex", "csindex:pe_ttm", "中证官方(日频)", "D")


def fetch_price(http, ix, log, refresh=False, as_of=None):
    """Walk this index's price source chain; return (rows, attempt_log)."""
    chain = ix.get("price") or []
    if not chain:
        return [], []
    rows, attempts = sources.price_best(http, chain, as_of=as_of,
                                       refresh=refresh, logger=log)
    if not rows:
        log.warning("  no usable price for %s: %s", ix["id"], "; ".join(attempts))
    return rows, attempts


LEGULEGU_RETRY_WAITS = (6.0, 20.0)

# Run-scoped circuit breaker for legulegu.
#
# legulegu goes through akshare, so it never touches HttpClient and cannot be
# covered by that host breaker - yet it fails the same way (504 site-wide for
# hours). Without this, an unattended run pays the full 6s+20s retry cycle on
# *every* index it serves, which measured ~26s x 7 = ~3 minutes of pure waiting.
# After `LEGULEGU_BREAKER_AFTER` consecutive give-ups we stop dialling it for
# the rest of the run and go straight to the cached series.
LEGULEGU_BREAKER_AFTER = 2
_LEGULEGU: dict[str, object] = {"fails": 0, "down": False}  # reset per run


def _legulegu_reset() -> None:
    _LEGULEGU["fails"] = 0
    _LEGULEGU["down"] = False


def _legulegu_cache_path(symbol: str):
    safe = "".join(ch if ch.isalnum() else "_" for ch in symbol)
    return CACHE_DIR / "legulegu" / f"{safe}.json"


def _legulegu_with_retry(symbol, log):
    """legulegu throttles aggressively (429) and its gateway times out (504).

    A failure here costs a whole PE series, so retry with a long backoff, and
    fall back to the last good copy on disk. legulegu regularly serves 504 for
    everyone for hours at a time; without this cache a rebuild would silently
    drop a series the page had been showing.
    Returns (rows, error_text); a source that genuinely lacks the index answers
    with an empty frame rather than raising.
    """
    cached = read_json(_legulegu_cache_path(symbol))
    if _LEGULEGU["down"]:
        # The host already failed repeatedly this run: do not spend another
        # 26s of backoff on it, just take what we have on disk.
        if cached and cached.get("rows"):
            stamp = datetime.fromtimestamp(cached["fetched_at"]).strftime("%Y-%m-%d %H:%M")
            return cached["rows"], (f"乐咕乐股本轮已熔断（连续失败），"
                                    f"改用 {stamp} 的快照")
        return [], "乐咕乐股本轮不可用（已熔断），无快照可回退"

    last = ""
    for attempt, wait in enumerate((0.0,) + LEGULEGU_RETRY_WAITS):
        if wait:
            log.info("      legulegu %s retry %d after %.0fs", symbol, attempt, wait)
            time.sleep(wait)
        try:
            rows = sources.legulegu_pe(symbol)
        except Exception as e:                       # noqa: BLE001
            last = f"{type(e).__name__}: {str(e)[:70]}"
            continue
        if rows:
            write_json(_legulegu_cache_path(symbol),
                       {"symbol": symbol, "fetched_at": time.time(), "rows": rows})
            _LEGULEGU["fails"] = 0
            return rows, ""
        return [], ""                                # upstream says: no such index

    _LEGULEGU["fails"] = int(_LEGULEGU["fails"]) + 1
    if _LEGULEGU["fails"] >= LEGULEGU_BREAKER_AFTER:
        _LEGULEGU["down"] = True
        log.warning("      legulegu unreachable x%d; skipping it for the rest of "
                    "this run (cached series only)", _LEGULEGU["fails"])

    if cached and cached.get("rows"):
        stamp = datetime.fromtimestamp(cached["fetched_at"]).strftime("%Y-%m-%d %H:%M")
        log.warning("      legulegu %s failed (%s); using cached series from %s",
                    symbol, last[:40], stamp)
        return cached["rows"], f"乐咕乐股暂时不可用，改用 {stamp} 的快照"
    log.warning("      legulegu %s gave up: %s", symbol, last)
    return [], last


def build_index(http, ix, log, *, refresh=False, offline=False):
    """Return the full payload for one index, or an error record."""
    iid = ix["id"]
    series_blocks = []
    gaps = []

    price, price_attempts = fetch_price(http, ix, log, refresh=refresh)
    price_src = price[-1].get("src") if price else None
    price_n = len(price)

    # ---- danjuan weekly PE -------------------------------------------------
    if ix.get("danjuan"):
        try:
            rows = sources.danjuan_pe(http, ix["danjuan"], refresh=refresh)
        except HttpError as e:
            rows = []
            gaps.append(f"蛋卷 PE 拉取失败: {str(e)[:80]}")
        if rows:
            a = metrics.analyze(rows, price)
            if a.get("ok"):
                a["series_id"] = "danjuan"
                a["label"] = SERIES_DANJUAN[2]
                a["source"] = SERIES_DANJUAN[1]
                a["upstream_code"] = ix["danjuan"]
                series_blocks.append(a)
        else:
            gaps.append("蛋卷无该指数 PE 历史")

    # ---- csindex daily PE-TTM (official, deepest daily A-share PE) ---------
    if ix.get("csindex"):
        try:
            rows = sources.csindex_pe(http, ix["csindex"], refresh=refresh)
        except HttpError as e:
            rows = []
            gaps.append(f"中证官方 PE 拉取失败: {str(e)[:80]}")
        if rows:
            a = metrics.analyze(rows, price)
            if a.get("ok"):
                a["series_id"] = "csindex"
                a["label"] = SERIES_CSINDEX[2]
                a["source"] = SERIES_CSINDEX[1]
                a["upstream_code"] = ix["csindex"]
                series_blocks.append(a)
        else:
            gaps.append("中证官方无该指数 PE 历史")

    # ---- legulegu monthly PE (never spliced onto danjuan) ------------------
    if ix.get("legulegu"):
        rows, err = _legulegu_with_retry(ix["legulegu"], log)
        if err:
            gaps.append(f"乐咕乐股 PE：{err}")
        if rows:
            a = metrics.analyze(rows, price)
            if a.get("ok"):
                a["series_id"] = "legulegu"
                a["label"] = SERIES_LEGULEGU[2]
                a["source"] = SERIES_LEGULEGU[1]
                a["upstream_code"] = ix["legulegu"]
                if err:
                    a["stale"] = True
                series_blocks.append(a)
        elif not err:
            gaps.append("乐咕乐股无该指数 PE 历史")

    # ---- multpl monthly PE (long history, S&P 500 only) --------------------
    if ix.get("multpl"):
        try:
            rows = sources.multpl_table(http, ix["multpl"], refresh=refresh)
        except HttpError as e:
            rows = []
            gaps.append(f"multpl 拉取失败: {str(e)[:70]}")
        if rows:
            a = metrics.analyze(rows, price)
            if a.get("ok"):
                a["series_id"] = "multpl"
                a["label"] = SERIES_MULTPL[2]
                a["source"] = SERIES_MULTPL[1]
                a["upstream_code"] = ix["multpl"]
                series_blocks.append(a)
        else:
            gaps.append("multpl 无该指数 PE 历史")

    if not price:
        gaps.append("无指数价格数据（候选源：%s）" % ("; ".join(price_attempts) or "未配置"))

    if not series_blocks:
        # Price-only index (several developed markets have no free PE history).
        # Still emit a trend payload; the PE gap is declared in `gaps`.
        if price:
            a = metrics.analyze_price_only(price)
            if a.get("ok"):
                a["series_id"] = "price_only"
                a["label"] = "仅指数点位（无PE源）"
                a["source"] = "price:%s" % (price_src or "?")
                a["upstream_code"] = None
                return {
                    "ok": True,
                    "has_pe": False,
                    "id": iid,
                    "name": ix["name"],
                    "region": ix.get("region"),
                    "country": ix.get("country"),
                    "developed": bool(ix.get("developed")),
                    "note": ix.get("note", ""),
                    "gaps": gaps + ["该指数暂无公开免费的 PE 历史源，仅展示指数点位走势"],
                    "has_price": True,
                    "price_source": price_src,
                    "price_note": ix.get("price_note"),
                    "price_n": price_n,
                    "price_attempts": price_attempts,
                    "series": [a],
                    "primary_series": "price_only",
                }
        return {"ok": False, "id": iid, "reason": "no_pe_series", "gaps": gaps}

    # Headline series: the CSIndex official daily PE-TTM when present (daily
    # resolution gives a far better-populated rolling window than the weekly
    # feed), else danjuan weekly, else whichever series is longest.
    primary = next((s for s in series_blocks if s["series_id"] == "csindex"), None)
    if primary is None:
        primary = next((s for s in series_blocks if s["series_id"] == "danjuan"), None)
    if primary is None:
        primary = max(series_blocks, key=lambda s: s["n"])

    return {
        "ok": True,
        "has_pe": True,
        "id": iid,
        "name": ix["name"],
        "region": ix.get("region"),
        "country": ix.get("country"),
        "developed": bool(ix.get("developed")),
        "note": ix.get("note", ""),
        "gaps": gaps,
        "has_price": bool(price),
        "price_source": price_src,
        "price_note": ix.get("price_note"),
        "price_n": price_n,
        "price_attempts": price_attempts,
        "series": series_blocks,
        "primary_series": primary["series_id"],
    }


def build_summary(payloads: list[dict]) -> list[dict]:
    """Compact cross-index row set for the comparison table."""
    rows = []
    for p in payloads:
        if not p.get("ok"):
            rows.append({
                "id": p["id"],
                "ok": False,
                "region": (universe.by_id(p["id"]) or {}).get("region"),
                "name": (universe.by_id(p["id"]) or {}).get("name", p["id"]),
                "gaps": p.get("gaps", []),
            })
            continue
        ix = universe.by_id(p["id"]) or {}
        prim = next((s for s in p["series"] if s["series_id"] == p["primary_series"]),
                    p["series"][0])
        row = {
            "id": p["id"],
            "ok": True,
            "has_pe": bool(p.get("has_pe", True)),
            "name": p["name"],
            "region": p.get("region"),
            "country": p.get("country"),
            "developed": p.get("developed"),
            "note": p.get("note", ""),
            "series_label": prim["label"],
            "source": prim["source"],
            "n": prim["n"],
            "freq": prim["freq"],
            "first": prim["first"],
            "last": prim["last"],
            "current_pe": prim.get("current_pe"),
            "current_price": prim.get("current_price"),
            "price_start": prim.get("price_start"),
            "price_source": p.get("price_source"),
            "price_note": p.get("price_note"),
            "price_n": p.get("price_n"),
            "primary_window": prim.get("primary_window"),
            "primary_pct": prim.get("primary_pct"),
            "primary_band": prim.get("primary_band"),
            "windows": {k: {"pct": v.get("pct"), "sufficient": v.get("sufficient"),
                            "n": v.get("n"), "start": v.get("start")}
                        for k, v in (prim.get("windows") or {}).items()},
            "series_ids": [s["series_id"] for s in p["series"]],
            "gaps": p.get("gaps", []),
        }
        rows.append(row)
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description="Build the PE-Trace data layer")
    ap.add_argument("--refresh", action="store_true",
                    help="ignore the disk cache and re-fetch upstream")
    ap.add_argument("--offline", action="store_true",
                    help="never touch the network; use cached responses only")
    ap.add_argument("--only", default="", help="comma-separated index ids")
    ap.add_argument("--min-interval", type=float, default=0.7)
    ap.add_argument("--max-age", type=float, default=None, metavar="HOURS",
                    help="treat cached responses older than HOURS as expired and "
                         "re-fetch them; a failed refresh falls back to the stale "
                         "copy. Default: cache never expires (fast local rebuild). "
                         "Scheduled runs want this (e.g. 6), because every upstream "
                         "URL is fixed and would otherwise be cached forever.")
    ap.add_argument("--skip-legulegu", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)

    ensure_dirs()
    log = setup_logging(args.verbose)
    t0 = time.time()
    _legulegu_reset()
    # a --refresh run ignores the cache entirely; otherwise honour the TTL.
    # Note `is not None`: --max-age 0 means "everything is expired", not "never
    # expire" (0 is falsy, so a truthiness test would silently invert it).
    max_age = None if args.refresh else (
        args.max_age * 3600.0 if args.max_age is not None else None)

    if args.only:
        wanted = {s.strip() for s in args.only.split(",") if s.strip()}
        todo = [x for x in universe.INDICES if x["id"] in wanted]
        missing = wanted - {x["id"] for x in todo}
        if missing:
            log.warning("unknown index ids ignored: %s", sorted(missing))
    else:
        todo = list(universe.INDICES)
    todo.sort(key=universe.sort_key)

    http = HttpClient(min_interval=args.min_interval, offline=args.offline,
                      max_age=max_age)
    if args.skip_legulegu:
        todo = [dict(x) for x in todo]
        for x in todo:
            x.pop("legulegu", None)

    payloads, failures = [], []
    for i, ix in enumerate(todo, 1):
        log.info("[%2d/%2d] %-9s %s", i, len(todo), ix["id"], ix["name"])
        try:
            p = build_index(http, ix, log, refresh=args.refresh,
                            offline=args.offline)
        except Exception as e:
            log.error("  FAILED: %s: %s", type(e).__name__, str(e)[:140])
            if args.verbose:
                traceback.print_exc()
            p = {"ok": False, "id": ix["id"], "reason": f"{type(e).__name__}"}
            failures.append(ix["id"])
        payloads.append(p)
        if p.get("ok"):
            nser = len(p["series"])
            det = " | ".join(f"{s['label']} n={s['n']} {s['first']}→{s['last']} "
                             f"PE={s['current_pe']} 5y%={s['windows'].get('5年',{}).get('pct')}"
                             for s in p["series"])
            log.info("      OK  %s", det)
            write_json(ROOT / "web" / "data" / "index" / f"{ix['id']}.json", p)
        else:
            log.warning("      NO PE SERIES (%s)", p.get("reason"))

    summary = build_summary(payloads)
    root = ROOT
    prev_manifest = read_json(DATA_DIR / "manifest.json") or {}

    def _row(p: dict) -> dict:
        # has_pe/has_price are recorded explicitly so the merged --only path can
        # count coverage without guessing from series_id.
        return {"id": p["id"],
                "name": (universe.by_id(p["id"]) or {}).get("name", p["id"]),
                "ok": bool(p.get("ok")),
                "has_pe": bool(p.get("has_pe", True)),
                "has_price": bool(p.get("has_price")),
                "series": [{"series_id": s["series_id"], "label": s["label"],
                            "source": s["source"], "n": s["n"],
                            "first": s["first"], "last": s["last"],
                            "freq": s["freq"]}
                           for s in p.get("series", [])],
                "gaps": p.get("gaps", [])}

    # A scoped --only run rebuilds a few indices but must not shrink the data
    # layer: without merging, `counts` would read "2/2 indices" and the sidebar
    # and coverage header would lose 50 entries. Merge by id, new wins.
    if args.only and prev_manifest.get("indices"):
        merged = {r["id"]: r for r in prev_manifest["indices"]}
        for p in payloads:
            merged[p["id"]] = _row(p)
        order = {x["id"]: i for i, x in enumerate(universe.INDICES)}
        index_rows = sorted(merged.values(), key=lambda r: order.get(r["id"], 999))
        prev_summary = read_json(DATA_DIR / "summary.json") or {}
        srows = {r["id"]: r for r in (prev_summary.get("rows") or [])}
        for r in summary:
            srows[r["id"]] = r
        summary = sorted(srows.values(),
                         key=lambda r: order.get(r["id"], 999))
    else:
        index_rows = [_row(p) for p in payloads]

    partial_note = None
    if args.only:
        partial_note = ("本次为局部重建，只刷新了 %s；其余指数沿用上一次运行的结果"
                        % args.only)
    write_json(root / "web" / "data" / "summary.json",
               {"generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                "partial": bool(args.only),
                "rows": summary}, indent=1)

    ok = sum(1 for p in payloads if p.get("ok"))
    with_pe = sum(1 for p in payloads if p.get("ok") and p.get("has_pe", True))
    with_price = sum(1 for p in payloads if p.get("ok") and p.get("has_price"))
    as_of = max((s["last"] for p in payloads if p.get("ok")
                 for s in p["series"]), default=None)
    # Compare with the previous run so a scheduler (and a reader) can tell
    # "the job ran and upstream had nothing new" apart from "the job failed".
    prev_as_of = prev_manifest.get("as_of")
    # never compare against a scoped run: its as_of covers only a few indices,
    # so the comparison would be meaningless in both directions
    prev_usable = bool(prev_manifest) and not prev_manifest.get("partial")
    if args.only:
        # counts must describe the whole merged layer, not just this subset
        ok = sum(1 for r in index_rows if r["ok"])
        with_pe = sum(1 for r in index_rows if r["ok"] and r["has_pe"])
        with_price = sum(1 for r in index_rows if r["ok"] and r["has_price"])
        as_of = max((s["last"] for r in index_rows for s in r["series"]),
                    default=as_of)
    manifest = {
        "app": "PE-Trace",
        "version": __import__("petrace").__version__,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "elapsed_sec": round(time.time() - t0, 1),
        "as_of": as_of,
        "freshness": {
            "previous_as_of": prev_as_of if prev_usable else None,
            "previous_generated_at": prev_manifest.get("generated_at"),
            "advanced": (as_of is not None and prev_usable and prev_as_of is not None
                         and as_of > prev_as_of),
            "note": "as_of 是各序列最新观测日；advanced=false 表示本次运行未取得"
                    "更新的数据（非交易日、上游未更新，或抓取失败），不等于运行失败。",
            "cache_max_age_hours": (args.max_age if not args.refresh else 0),
            "stale_responses": http.stats.get("stale", 0),
            "stale_urls": http.stale_urls[:20],
        },
        "counts": {"total": len(index_rows), "ok": ok, "with_pe": with_pe,
                   "with_price": with_price, "no_pe": len(index_rows) - with_pe,
                   "price_only": ok - with_pe},
        "partial": bool(args.only),
        "partial_note": partial_note,
        "counts_note": "ok=有页面数据(含仅点位)；with_pe=有PE序列；with_price=有点位；"
                       "no_pe=无公开PE源；price_only=仅点位无PE",
        "http": http.stats,
        "regions": universe.REGIONS,
        "sources": {
            "danjuan": {"name": "蛋卷基金 danjuanfunds.com",
                        "what": "指数 PE/PB 历史（周频，约 2016-10 起）",
                        "url": "https://danjuanfunds.com/djapi/index_eva/pe_history/{code}?day=all"},
            "csindex": {"name": "中证指数公司 csindex.com.cn（官方）",
                        "what": "指数日线收盘价 + 日频市盈率（PE-TTM）。接口字段名为 peg，"
                                "已用沪深300历史PE水位与蛋卷重叠日比值验证其为 PE-TTM。"
                                "收盘价自 2004 起，PE 多自 2011-06-28 起（个别更晚）。",
                        "url": "https://www.csindex.com.cn/csindex-home/perf/index-perf"},
            "legulegu": {"name": "乐咕乐股 legulegu.com（经 akshare）",
                         "what": "指数滚动市盈率（月频，2005 起，仅主要 A 股宽基）",
                         "url": "https://legulegu.com/stockdata/index-basic-pe"},
            "em": {"name": "东方财富 push2his",
                   "what": "指数日线收盘价（当前链路末位；该主机对持续轮询有硬封禁）",
                   "url": "https://push2his.eastmoney.com/api/qt/stock/kline/get"},
            "price": {"name": "新浪财经 / 腾讯证券",
                     "what": "指数日线/周线收盘价（多源回退链，自动跳过过期源）",
                     "url": "https://money.finance.sina.com.cn + https://web.ifzq.gtimg.cn"},
            "proxy": {"name": "ETF 价格代理",
                      "what": "部分指数无免费指数价格源，改用跟踪同一指数的 ETF 价格"
                              "（在页面与该指数档案中明确标注为代理）",
                      "url": "https://stock.finance.sina.com.cn/usstock/ + https://money.finance.sina.com.cn/"},
            "multpl": {"name": "multpl.com",
                       "what": "标普500 滚动市盈率（月频，长历史）",
                       "url": "https://www.multpl.com/s-p-500-pe-ratio/table/by-month"},
        },
        "method": {
            "percentile": "窗口内中位秩百分位 (count(v<x)+0.5*count(v==x))/n*100",
            "window": "以观测日为终点、按自然日回溯的滚动窗口",
            "sufficiency": "窗口内观测数须达到满窗应有数的 60%（且≥3）才给出分位",
            "bands": [{"lo": lo, "hi": hi, "label": lbl} for lo, hi, lbl, _ in metrics.BANDS],
            "windows": [metrics.WINDOW_LABELS[w] for w in metrics.WINDOWS],
        },
        "failures": failures,
        "indices": index_rows,
    }
    write_json(root / "web" / "data" / "manifest.json", manifest, indent=1)
    if args.only:
        log.info("partial run: only %s rebuilt; the other rows were carried over "
                 "from the previous manifest, so counts still describe all %d indices",
                 args.only, len(index_rows))
    log.info("done in %.1fs | ok=%d/%d | http=%s",
             time.time() - t0, with_pe, len(index_rows), http.stats)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
