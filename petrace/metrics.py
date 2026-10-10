# -*- coding: utf-8 -*-
"""
petrace.metrics - deterministic rolling-window PE percentile engine.

Definitions (frozen; the web UI and README quote these verbatim)
----------------------------------------------------------------
PE observation
    A (date, PE) pair published by an upstream. We never compute an index PE
    from constituent data, so every PE value is traceable to a named source.

Rolling window
    A *trailing calendar* window ending at the observation date, expressed in
    years: ``[d - years*365.25 days, d]``. Using elapsed days rather than a row
    count means weekly (danjuan) and monthly (legulegu/multpl) series are treated
    identically and no index silently mixes frequencies.

Window percentile  (the "rolling percentile")
    Percentile rank of the *latest* PE inside its own trailing window, using the
    mid-rank convention:

        pct = (count(v <  x) + 0.5 * count(v == x)) / n * 100

    Mid-rank is used instead of ``count(v <= x)/n`` because PE series contain
    repeated values (rounding, unchanged weeks); the inclusive form would report
    a flat series as sitting at the 100th percentile. 0 = cheapest in window,
    100 = most expensive in window.

Expanding percentile
    The same statistic with the window starting at the first observation. Shown
    alongside the rolling percentile because most public dashboards report only
    this one; the gap between the two is itself informative.

Insufficiency rule
    A window reports ``None`` unless it holds at least ``min_frac`` (default 0.6)
    of the observations a full window would contain at the series' own median
    spacing. This prevents a 3-year window from being answered by 6 monthly
    points and presented as if it were a 3-year history.
"""
from __future__ import annotations

import math
from datetime import date, datetime, timedelta

import numpy as np

# Windows offered in the UI, in years. None = full available history.
WINDOWS = [1, 3, 5, 10, None]
WINDOW_LABELS = {1: "1年", 3: "3年", 5: "5年", 10: "10年", None: "全历史"}

# Percentile -> valuation band. Bands are descriptive labels for the observed
# statistic, NOT trading signals.
BANDS = [
    (0, 20, "低估", "#1f9d55"),
    (20, 40, "偏低", "#7cb342"),
    (40, 60, "中性", "#c9a227"),
    (60, 80, "偏高", "#e07b39"),
    (80, 100.0001, "高估", "#d64545"),
]


def band_of(pct: float | None) -> dict | None:
    if pct is None or not math.isfinite(pct):
        return None
    for lo, hi, label, color in BANDS:
        if lo <= pct < hi:
            return {"label": label, "color": color, "lo": lo, "hi": hi}
    return None


def _d(s: str) -> date:
    return datetime.strptime(s[:10], "%Y-%m-%d").date()


def _median_spacing_days(dates: list[str]) -> float:
    if len(dates) < 3:
        return 7.0
    gaps = []
    for i in range(1, len(dates)):
        gaps.append((_d(dates[i]) - _d(dates[i - 1])).days)
    gaps = [g for g in gaps if g > 0]
    if not gaps:
        return 7.0
    return float(np.median(gaps))


def _freq_label(spacing_days: float) -> str:
    """Name the sampling cadence from its median calendar gap.

    Thresholds are set by trading calendars, not by round numbers: an A-share
    trading week is 5 calendar days, a month about 30, so daily (1) and weekly
    (7) must not collapse into one bucket - they differ by 5x in window sample
    size, which is exactly what the sufficiency rule depends on.
    """
    s = spacing_days
    if s <= 3:
        return "日"
    if s <= 10:
        return "周"
    if s <= 45:
        return "月"
    if s <= 120:
        return "季"
    return "不定期"


# ---------------------------------------------------------------------------
# percentile primitives
# ---------------------------------------------------------------------------
def pct_rank_mid(window: np.ndarray, x: float) -> float:
    """Mid-rank percentile of ``x`` within ``window`` (0..100)."""
    n = window.size
    if n == 0:
        return float("nan")
    less = int(np.count_nonzero(window < x))
    equal = int(np.count_nonzero(window == x))
    return (less + 0.5 * equal) / n * 100.0


def rolling_percentile(dates: list[str], values: np.ndarray, years: float,
                       *, min_frac: float = 0.6) -> tuple[np.ndarray, list[bool]]:
    """Percentile of each point within its own trailing ``years`` window.

    Returns ``(pct_array, valid_list)``; invalid entries are NaN.
    """
    n = len(dates)
    dt = np.array([_d(s).toordinal() for s in dates], dtype=np.int64)
    lookback = int(round(years * 365.25))
    spacing = _median_spacing_days(dates)
    min_obs = max(3, int(math.floor(lookback / max(spacing, 1.0) * min_frac)))

    out = np.full(n, np.nan, dtype=float)
    valid = [False] * n
    lo = 0
    for i in range(n):
        cut = dt[i] - lookback
        while lo < i and dt[lo] < cut:
            lo += 1
        # window is [lo, i] inclusive
        win = values[lo:i + 1]
        if win.size >= min_obs:
            out[i] = pct_rank_mid(win, values[i])
            valid[i] = True
    return out, valid


def expanding_percentile(values: np.ndarray) -> np.ndarray:
    """Percentile of each point within all observations up to and including it."""
    n = values.size
    out = np.full(n, np.nan, dtype=float)
    for i in range(n):
        out[i] = pct_rank_mid(values[:i + 1], values[i])
    return out


# ---------------------------------------------------------------------------
# series assembly
# ---------------------------------------------------------------------------
def dedupe_series(rows: list[dict], key: str = "pe") -> tuple[list[str], np.ndarray]:
    """Sort by date, keep the last value per date, drop non-finite/non-positive."""
    best: dict[str, float] = {}
    for r in rows:
        d, v = r.get("date"), r.get(key)
        if d is None or v is None:
            continue
        try:
            v = float(v)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(v) or v <= 0:
            continue
        best[str(d)[:10]] = v
    dates = sorted(best)
    if not dates:
        return [], np.array([], dtype=float)
    return dates, np.array([best[d] for d in dates], dtype=float)


def _window_slice(dates: list[str], i: int, years: float | None) -> tuple[int, int]:
    if years is None:
        return 0, i
    dt = np.array([_d(s).toordinal() for s in dates], dtype=np.int64)
    cut = dt[i] - int(round(years * 365.25))
    j = i
    while j > 0 and dt[j - 1] >= cut:
        j -= 1
    return j, i


def summarize_window(dates: list[str], values: np.ndarray, i: int,
                     years: float | None, *, min_frac: float = 0.6) -> dict:
    """Window stats for the observation at index ``i``."""
    j, _ = _window_slice(dates, i, years)
    win = values[j:i + 1]
    n = win.size

    if years is None:
        need = 3
    else:
        spacing = _median_spacing_days(dates)
        need = max(3, int(math.floor(years * 365.25 / max(spacing, 1.0) * min_frac)))

    rec = {
        "window": WINDOW_LABELS.get(years, str(years)),
        "n": int(n),
        "need": int(need),
        "sufficient": bool(n >= need),
        "start": dates[j],
        "end": dates[i],
    }
    if n == 0:
        rec.update({"min": None, "max": None, "median": None, "mean": None,
                    "pct": None, "z": None, "span_years": None})
        return rec

    cur = float(values[i])
    mean = float(np.mean(win))
    std = float(np.std(win, ddof=0))
    rec.update({
        "min": float(np.min(win)),
        "max": float(np.max(win)),
        "median": float(np.median(win)),
        "mean": mean,
        "cur": cur,
        "pct": pct_rank_mid(win, cur) if rec["sufficient"] else None,
        "z": (cur - mean) / std if std > 1e-12 else None,
        "span_years": round((_d(dates[i]) - _d(dates[j])).days / 365.25, 2),
        "drawdown_from_max": (cur / float(np.max(win)) - 1.0) * 100.0,
    })
    return rec


def analyze_price_only(price_rows: list[dict]) -> dict:
    """Chartable payload for an index that has price but no PE source at all.

    Several developed markets (日经225, 英国富时100, 道琼斯…) have no free
    public PE history, but their price trend is still worth showing next to the
    ones that do. The payload carries ``has_pe=False`` so the UI can label the
    missing PE series instead of appearing broken.
    """
    dates, closes = [], []
    for r in price_rows or []:
        d, c = r.get("date"), r.get("close")
        if d is None or c is None:
            continue
        try:
            c = float(c)
        except (TypeError, ValueError):
            continue
        if c > 0:
            dates.append(str(d)[:10])
            closes.append(c)
    if not dates:
        return {"ok": False, "reason": "no_price_data"}

    order = sorted(range(len(dates)), key=lambda i: dates[i])
    dates = [dates[i] for i in order]
    closes = [closes[i] for i in order]
    # collapse duplicate dates, keeping the last
    uniq_d, uniq_c = [], []
    for d, c in zip(dates, closes):
        if uniq_d and uniq_d[-1] == d:
            uniq_c[-1] = c
        else:
            uniq_d.append(d)
            uniq_c.append(c)

    base = uniq_c[0]
    spacings = _median_spacing_days(uniq_d)
    freq = _freq_label(spacings)
    return {
        "ok": True,
        "has_pe": False,
        "n": len(uniq_d),
        "freq": freq,
        "spacing_days": round(spacings, 1),
        "first": uniq_d[0],
        "last": uniq_d[-1],
        "sources": sorted({r.get("src", "?") for r in price_rows if r.get("src")}),
        "current_pe": None,
        "current_price": round(uniq_c[-1], 3),
        "price_start": round(base, 3),
        "date": uniq_d,
        "pe": [None] * len(uniq_d),
        "price": [round(c, 3) for c in uniq_c],
        "norm_pe": [None] * len(uniq_d),
        "norm_price": [round(c / base * 100, 2) for c in uniq_c],
        "percentile": {},
        "windows": {},
        "primary_window": None,
        "primary_pct": None,
        "primary_band": None,
    }


# ---------------------------------------------------------------------------
# full index analysis
# ---------------------------------------------------------------------------
def analyze(pe_rows: list[dict], price_rows: list[dict], *,
            min_frac: float = 0.6) -> dict:
    """Build the complete chartable payload for one index."""
    dates, pes = dedupe_series(pe_rows, "pe")
    if len(dates) == 0:
        return {"ok": False, "reason": "no_pe_data"}

    price_map = {}
    for r in price_rows or []:
        d, c = r.get("date"), r.get("close")
        if d is None or c is None:
            continue
        try:
            c = float(c)
        except (TypeError, ValueError):
            continue
        if c > 0:
            price_map[str(d)[:10]] = c

    # forward-fill price onto PE observation dates (as-of join)
    pdates = sorted(price_map)
    series_price, j = [], 0
    last = None
    for d in dates:
        while j < len(pdates) and pdates[j] <= d:
            last = price_map[pdates[j]]
            j += 1
        series_price.append(last)

    # normalized PE percentile series per window
    pct_series: dict[str, list] = {}
    for w in WINDOWS:
        if w is None:
            arr = expanding_percentile(pes)
        else:
            arr, _ = rolling_percentile(dates, pes, w, min_frac=min_frac)
        pct_series[WINDOW_LABELS[w]] = [
            None if (v is None or not math.isfinite(v)) else round(float(v), 2)
            for v in arr
        ]

    last_i = len(dates) - 1
    windows_out = {WINDOW_LABELS[w]: summarize_window(dates, pes, last_i, w,
                                                      min_frac=min_frac)
                   for w in WINDOWS}

    primary = windows_out.get("5年") or {}
    if primary.get("pct") is None:
        for lbl in ("3年", "10年", "全历史", "1年"):
            if windows_out.get(lbl, {}).get("pct") is not None:
                primary = windows_out[lbl]
                break

    # rebase price and PE to 100 at the first shared observation, for shape compare
    base_pe = pes[0]
    base_px = next((p for p in series_price if p), None)
    norm_pe = [None if not v else round(v / base_pe * 100, 2) for v in pes]
    norm_px = [None if (not p or not base_px) else round(p / base_px * 100, 2)
               for p in series_price]

    spacings = _median_spacing_days(dates)
    freq = _freq_label(spacings)

    return {
        "ok": True,
        "n": len(dates),
        "freq": freq,
        "spacing_days": round(spacings, 1),
        "first": dates[0],
        "last": dates[-1],
        "sources": sorted({r.get("src", "?") for r in pe_rows if r.get("src")}),
        "current_pe": round(float(pes[-1]), 3),
        "current_price": series_price[-1],
        "price_start": next((p for p in series_price if p), None),
        "date": dates,
        "pe": [round(float(v), 3) for v in pes],
        "price": [None if p is None else round(float(p), 3) for p in series_price],
        "norm_pe": norm_pe,
        "norm_price": norm_px,
        "percentile": pct_series,
        "windows": windows_out,
        "primary_window": primary.get("window"),
        "primary_pct": primary.get("pct"),
        "primary_band": band_of(primary.get("pct")),
    }
