# -*- coding: utf-8 -*-
"""
petrace.sources - one adapter per upstream, all returning the same tidy shapes.

Canonical records
-----------------
PE observation : {"date": "YYYY-MM-DD", "pe": float, "src": str, "freq": "W"|"M"}
                 The PE is whatever the upstream publishes. We never re-derive an
                 index PE ourselves; every number traces back to a named source.
Price bar      : {"date": "YYYY-MM-DD", "close": float}
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone, timedelta
from html import unescape

from .core import HttpClient, HttpError, load_snapshot, save_snapshot

CN_TZ = timezone(timedelta(hours=8))


def _strip_cell(html_fragment: str) -> str:
    """Tag-strip an HTML table cell and decode entities, leaving the value text."""
    return unescape(re.sub(r"<[^>]+>", " ", html_fragment)).strip()

# --------------------------------------------------------------------------
# danjuanfunds.com - weekly index PE/PB history, the primary PE source
# --------------------------------------------------------------------------
DANJUAN_PE = "https://danjuanfunds.com/djapi/index_eva/pe_history/{code}?day=all"
DANJUAN_PB = "https://danjuanfunds.com/djapi/index_eva/pb_history/{code}?day=all"
DANJUAN_DETAIL = "https://danjuanfunds.com/djapi/index_eva/detail/{code}"
DANJUAN_LIST = "https://danjuanfunds.com/djapi/index_eva/dj"


def _ms_to_date(ms) -> str | None:
    try:
        ms = int(ms)
    except (TypeError, ValueError):
        return None
    if ms <= 0:
        return None
    return datetime.fromtimestamp(ms / 1000.0, CN_TZ).strftime("%Y-%m-%d")


def _clean_pe_rows(rows, src: str, freq: str = "W") -> list[dict]:
    out, seen = [], set()
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        d = _ms_to_date(r.get("ts"))
        pe = r.get("pe")
        if d is None or pe is None:
            continue
        try:
            pe = float(pe)
        except (TypeError, ValueError):
            continue
        if pe <= 0 or pe > 500:
            continue
        if d in seen:
            continue
        seen.add(d)
        out.append({"date": d, "pe": pe, "src": src, "freq": freq})
    out.sort(key=lambda x: x["date"])
    return out


# --------------------------------------------------------------------------
# csindex.com.cn - official CSI index performance feed.
#
# One daily row carries both the index close and a valuation figure the
# upstream names `peg`.  It is NOT the PEG ratio: verified against CSI300's
# well-known PE-TTM levels and against danjuan's PE on 513 overlapping days
# (ratio 0.88..1.05, drifting with the weighting difference), and its whole
# 2011-2026 range is 8.55..20.38 - a PEG ratio would sit near 0.5-2 and index
# points near 3000.  So `peg` is a daily PE-TTM and is published as such.
#
# PE depth starts later than close depth: e.g. 000300 has closes from
# 2004-01-01 but PE only from 2011-06-28.  Callers get both facts.
# --------------------------------------------------------------------------
CSINDEX_PERF = "https://www.csindex.com.cn/csindex-home/perf/index-perf"
CSINDEX_HEADERS = {"Referer": "https://www.csindex.com.cn/"}


def _csindex_records(http: HttpClient, code: str, *,
                     refresh: bool = False) -> tuple[list[dict], str | None]:
    """Raw daily records for one csindex code (close + peg), plus a staleness
    note when the live fetch failed and a stored snapshot was used instead.

    The upstream trips its WAF after a burst of requests and then answers 403
    with a junk HTML page for a while - it does *not* say "rate limited", and
    from a distance it looks exactly like "this index has no history". Parsed
    results are snapshotted, so an outage degrades to the last good copy
    instead of silently dropping the series.
    """
    url = (f"{CSINDEX_PERF}?indexCode={code}"
           f"&startDate=20040101&endDate=20500101")
    try:
        obj = http.get_json(url, headers=CSINDEX_HEADERS, refresh=refresh)
    except HttpError:
        rows, stamp = load_snapshot(f"csindex_{code}")
        if rows:
            http.log.warning("      csindex %s unavailable; snapshot from %s",
                             code, stamp)
            return rows, stamp
        return [], None
    data = (obj or {}).get("data")
    rows = data if isinstance(data, list) else []
    if rows:
        save_snapshot(f"csindex_{code}", rows)
    return rows, None


def _csindex_date(raw) -> str | None:
    """'20261009' -> '2026-10-09'."""
    s = str(raw or "")
    if len(s) != 8 or not s.isdigit():
        return None
    return f"{s[:4]}-{s[4:6]}-{s[6:]}"


def csindex_pe(http: HttpClient, code: str, *, refresh: bool = False) -> list[dict]:
    """Daily PE-TTM history for one csindex code (the upstream `peg` field)."""
    recs, _stale = _csindex_records(http, code, refresh=refresh)
    out, seen = [], set()
    for r in recs:
        d = _csindex_date(r.get("tradeDate"))
        pe = r.get("peg")
        if d is None or pe is None or d in seen:
            continue
        try:
            pe = float(pe)
        except (TypeError, ValueError):
            continue
        if pe <= 0 or pe > 500:
            continue
        seen.add(d)
        out.append({"date": d, "pe": pe, "src": "csindex:pe_ttm", "freq": "D"})
    out.sort(key=lambda x: x["date"])
    return out


def csindex_kline(http: HttpClient, code: str, *, refresh: bool = False) -> list[dict]:
    """Daily closes for one csindex code (same feed, no extra request)."""
    recs, _stale = _csindex_records(http, code, refresh=refresh)
    return _tidy_price(((_csindex_date(r.get("tradeDate")), r.get("close"))
                        for r in recs), "csindex")


def danjuan_pe(http: HttpClient, code: str, *, refresh: bool = False) -> list[dict]:
    """Weekly PE (pe_history) for one danjuan index code."""
    url = DANJUAN_PE.format(code=code)
    txt = http.get_text(url, headers={"Referer": "https://danjuanfunds.com/"},
                        refresh=refresh)
    try:
        obj = json.loads(txt)
    except Exception:
        return []
    rows = ((obj.get("data") or {}).get("index_eva_pe_growths")) or []
    return _clean_pe_rows(rows, "danjuan:pe_history")


def danjuan_pb(http: HttpClient, code: str, *, refresh: bool = False) -> list[dict]:
    url = DANJUAN_PB.format(code=code)
    txt = http.get_text(url, headers={"Referer": "https://danjuanfunds.com/"},
                        refresh=refresh)
    try:
        obj = json.loads(txt)
    except Exception:
        return []
    rows = ((obj.get("data") or {}).get("index_eva_pb_growths")) or []
    clean = _clean_pe_rows(rows, "danjuan:pb_history")
    for r in clean:
        r["kind"] = "pb"
    return clean


def danjuan_detail(http: HttpClient, code: str, *, refresh: bool = False) -> dict | None:
    url = DANJUAN_DETAIL.format(code=code)
    try:
        obj = json.loads(http.get_text(url, refresh=refresh))
    except Exception:
        return None
    return obj.get("data") or None


def danjuan_list(http: HttpClient, *, refresh: bool = False) -> list[dict]:
    try:
        obj = json.loads(http.get_text(DANJUAN_LIST, refresh=refresh))
    except Exception:
        return []
    d = obj.get("data")
    if isinstance(d, dict):
        return d.get("items") or []
    return d or []


# --------------------------------------------------------------------------
# Index price - several interchangeable upstreams.
#
# Which one is used depends on how deep the history needs to be:
#   sina_cn  daily,  6000 bars, A-share indices from ~2002  (deepest for A 股)
#   tencent  daily/weekly, week bars reach 1989 for HK        (deepest for HK)
#   sina_us  daily,  from 2004 for US indices
#   sina_gi  daily,  ~1000 bars only - the sole source for non-US developed
#   em       daily,  very deep, but the host blocks sustained polling
#
# price_best() tries the configured chain in order and keeps the longest series
# that still reaches the requested as-of date, so a source that silently stops
# updating (observed: sina_cn for 中证红利 ends 2019-01) is passed over.
# --------------------------------------------------------------------------
SINA_CN = ("https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/"
           "CN_MarketData.getKLineData")
TENCENT_KLINE = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
SINA_GI = "https://gi.finance.sina.com.cn/hq/daily"
SINA_US = ("https://stock.finance.sina.com.cn/usstock/api/jsonp.php/var%20a=/"
           "US_MinKService.getDailyK")
EM_KLINE = (
    "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    "?secid={secid}&fields1=f1,f2,f3,f4,f5"
    "&fields2=f51,f52,f53,f54,f55,f56,f57,f58&klt=101&fqt=1&beg=0&end=20500101"
)

SINA_HEADERS = {"Referer": "https://finance.sina.com.cn/"}


def _tidy_price(rows, src: str) -> list[dict]:
    out, seen = [], set()
    for d, c in rows:
        if not d or c is None:
            continue
        ds = str(d)[:10]
        try:
            val = float(c)
        except (TypeError, ValueError):
            continue
        if val <= 0 or ds in seen:
            continue
        seen.add(ds)
        out.append({"date": ds, "close": val, "src": src})
    out.sort(key=lambda x: x["date"])
    return out


def sina_cn_kline(http: HttpClient, code: str, *, datalen: int = 6000,
                  refresh: bool = False) -> list[dict]:
    """Daily closes for one A-share index code, e.g. 'sh000300'."""
    url = (f"{SINA_CN}?symbol={code}&scale=240&ma=no&datalen={datalen}")
    txt = http.get_text(url, headers=SINA_HEADERS, refresh=refresh)
    try:
        arr = json.loads(txt)
    except Exception:
        return []
    if not isinstance(arr, list):
        return []
    return _tidy_price(((r.get("day"), r.get("close")) for r in arr
                        if isinstance(r, dict)), "sina:cn")


def tencent_kline(http: HttpClient, code: str, *, period: str = "day",
                  count: int = 2000, refresh: bool = False) -> list[dict]:
    """Daily/weekly closes from Tencent, e.g. code='hkHSI', period='week'."""
    url = f"{TENCENT_KLINE}?param={code},{period},,,{count},qfq"
    txt = http.get_text(url, refresh=refresh)
    try:
        obj = json.loads(txt)
    except Exception:
        return []
    if obj.get("code") != 0:
        return []
    d = (obj.get("data") or {}).get(code) or {}
    kl = d.get(period) or d.get("qfq" + period) or d.get("day") or []
    return _tidy_price(((r[0], r[2]) for r in kl if len(r) >= 3), "tencent")


def sina_us_kline(http: HttpClient, symbol: str, *, refresh: bool = False) -> list[dict]:
    """Daily closes for a US index, e.g. symbol='.INX'."""
    url = f"{SINA_US}?symbol={symbol}&___qn=3"
    txt = http.get_text(url, headers={"Referer": "https://stock.finance.sina.com.cn/"},
                        refresh=refresh)
    i, j = txt.find("["), txt.rfind("]")
    if i < 0 or j <= i:
        return []
    try:
        arr = json.loads(txt[i:j + 1])
    except Exception:
        return []
    return _tidy_price(((r.get("d"), r.get("c")) for r in arr
                        if isinstance(r, dict)), "sina:us")


def sina_gi_kline(http: HttpClient, symbol: str, *, refresh: bool = False) -> list[dict]:
    """Daily closes for a global index from Sina's global market feed."""
    url = f"{SINA_GI}?symbol={symbol}&num=1000"
    txt = http.get_text(url, refresh=refresh)
    try:
        obj = json.loads(txt)
    except Exception:
        return []
    data = ((obj.get("result") or {}).get("data")) or []
    return _tidy_price(((r.get("d"), r.get("c")) for r in data
                        if isinstance(r, dict)), "sina:gi")


def eastmoney_kline(http: HttpClient, secid: str, *, refresh: bool = False) -> list[dict]:
    """Daily closes for one eastmoney secid (e.g. '100.SPX', '1.000300')."""
    url = EM_KLINE.format(secid=secid)
    txt = http.get_text(url, headers={"Referer": "https://quote.eastmoney.com/"},
                        refresh=refresh)
    try:
        obj = json.loads(txt)
    except Exception:
        return []
    kl = ((obj.get("data") or {}).get("klines")) or []
    rows = []
    for line in kl:
        parts = line.split(",")
        if len(parts) >= 3:
            rows.append((parts[0], parts[2]))
    return _tidy_price(rows, "eastmoney")


# Each entry: (schedule, kwargs). The schedule name maps to the adapter above.
PRICE_FETCHERS = {
    "sina_cn": lambda http, spec, refresh: sina_cn_kline(
        http, spec, refresh=refresh),
    "tencent": lambda http, spec, refresh: tencent_kline(
        http, spec[0], period=spec[1], count=spec[2], refresh=refresh),
    "sina_us": lambda http, spec, refresh: sina_us_kline(
        http, spec, refresh=refresh),
    "sina_gi": lambda http, spec, refresh: sina_gi_kline(
        http, spec, refresh=refresh),
    "csindex": lambda http, spec, refresh: csindex_kline(
        http, spec, refresh=refresh),
    "em": lambda http, spec, refresh: eastmoney_kline(
        http, spec, refresh=refresh),
}


def price_best(http: HttpClient, chain: list, *, as_of: str | None = None,
               stale_days: int = 21, refresh: bool = False,
               logger=None) -> tuple[list[dict], list[str]]:
    """Walk a price source chain and return (rows, attempted_source_names).

    A candidate is accepted only if it reaches within `stale_days` of as_of
    (or of today when as_of is None); among the acceptable ones the longest
    wins. This is what keeps a dead-but-200 source from being used.
    """
    from datetime import date as _date  # noqa: PLC0415
    cutoff = as_of or _date.today().isoformat()
    try:
        y, m, d = (int(x) for x in cutoff.split("-"))
        cutoff = _date(y, m, d)
    except Exception:
        cutoff = _date.today()
    # last bar must be no older than this
    stale_limit = cutoff.fromordinal(cutoff.toordinal() - stale_days)

    best, attempts, best_src = [], [], None
    for item in chain or []:
        kind, spec = item[0], item[1]
        fn = PRICE_FETCHERS.get(kind)
        if fn is None:
            continue
        name = kind if isinstance(spec, str) else f"{kind}:{spec}"
        try:
            rows = fn(http, spec, refresh)
        except HttpError as e:
            attempts.append(f"{name}(失败:{type(e).__name__})")
            if logger:
                logger.debug("  price %s failed: %s", name, str(e)[:80])
            continue
        if not rows:
            attempts.append(f"{name}(空)")
            continue
        last = rows[-1]["date"]
        if last < stale_limit.isoformat():
            attempts.append(f"{name}(止于{last},过旧)")
            if logger:
                logger.debug("  price %s stops at %s, skipped", name, last)
            continue
        attempts.append(f"{name}(n={len(rows)},{rows[0]['date']}→{last})")
        # Deepest history wins. Ranking by bar count alone is misleading: a
        # weekly feed from 1989 and a daily feed from 2018 both return 2000
        # bars, yet only the former reaches back far enough to sit beside a
        # long monthly PE series.
        if not best or (rows[0]["date"], -len(rows)) < (best[0]["date"], -len(best)):
            best, best_src = rows, name
    if logger and best:
        logger.debug("  price chose %s n=%d %s→%s", best_src, len(best),
                     best[0]["date"], best[-1]["date"])
    return best, attempts


# --------------------------------------------------------------------------
# multpl.com - monthly S&P 500 trailing PE, deepest available series
# --------------------------------------------------------------------------
MULTPL = "https://www.multpl.com/{slug}/table/by-month"
# Rows carry a class (<tr class="odd">), the date cell is plain text and the value
# cell mixes an <abbr> marker with the number, so strip tags then unescape entities.
_ROW_RE = re.compile(
    r"<tr[^>]*>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>\s*</tr>", re.S | re.I)


def multpl_table(http: HttpClient, slug: str, *, refresh: bool = False) -> list[dict]:
    txt = http.get_text(MULTPL.format(slug=slug), refresh=refresh)
    out, seen = [], set()
    for m in _ROW_RE.finditer(txt):
        raw_d = _strip_cell(m.group(1))
        raw_v = _strip_cell(m.group(2))
        # the value cell may carry a dagger marker and a comma thousands separator
        num = re.search(r"-?\d[\d,]*\.?\d*", raw_v)
        try:
            dt = datetime.strptime(raw_d, "%b %d, %Y").strftime("%Y-%m-%d")
            val = float(num.group(0).replace(",", ""))
        except Exception:
            continue
        if val <= 0 or val > 500 or dt in seen:
            continue
        seen.add(dt)
        out.append({"date": dt, "pe": val, "src": f"multpl:{slug}", "freq": "M"})
    out.sort(key=lambda x: x["date"])
    return out


# --------------------------------------------------------------------------
# akshare / legulegu - monthly index PE back to 2005 for major A-share indices
# --------------------------------------------------------------------------
LEGULEGU_COL = "滚动市盈率"


def legulegu_pe(symbol: str, *, as_of: str | None = None) -> list[dict]:
    """Monthly trailing PE from legulegu via akshare. Imported lazily: akshare is
    heavy and pulls in py_mini_racer for its request signing."""
    import akshare as ak  # noqa: PLC0415
    df = ak.stock_index_pe_lg(symbol=symbol)
    if df is None or len(df) == 0:
        return []
    cols = {str(c): c for c in df.columns}
    dcol = cols.get("日期")
    pcol = cols.get(LEGULEGU_COL) or cols.get("静态市盈率")
    if dcol is None or pcol is None:
        return []
    out, seen = [], set()
    for d, pe in zip(df[dcol], df[pcol]):
        try:
            ds = str(d)[:10]
            dt = datetime.strptime(ds, "%Y-%m-%d").strftime("%Y-%m-%d")
            val = float(pe)
        except Exception:
            continue
        if val <= 0 or val > 500 or dt in seen:
            continue
        if as_of and dt > as_of:
            continue
        seen.add(dt)
        out.append({"date": dt, "pe": val, "src": f"legulegu:{symbol}", "freq": "M"})
    out.sort(key=lambda x: x["date"])
    return out


def legulegu_supported() -> list[str]:
    return ["上证50", "沪深300", "上证380", "创业板50", "中证500", "上证180",
            "深证红利", "深证100", "中证1000", "上证红利", "中证100", "中证800"]
