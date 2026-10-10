/* PE-Trace front end.
 *
 * Reads the static data layer produced by `python -m petrace.build`:
 *   data/manifest.json   run metadata, source registry, method text
 *   data/summary.json    one compact row per index
 *   data/index/<ID>.json full series for one index
 *
 * All numbers shown come from that layer - nothing is computed here. The UI
 * only chooses which series/window to draw and how to label it.
 */
'use strict';

const COLOR_PRICE = '#6f7f92';
const COLOR_PE = '#d4a017';
const COLOR_PCT = '#4a9eda';
const SERIES_COLORS = [
  '#d4a017', '#4a9eda', '#5cbf7a', '#e07b39', '#b07ad6',
  '#48b8b8', '#d64545', '#c9a227', '#7c9fd6', '#9aa64a',
];

const state = {
  manifest: null,
  summary: [],
  rowsById: {},
  selected: new Set(),
  activeId: null,
  detailWindow: '5年',
  detailMode: 'dual',
  compareMetric: 'pct',
  compareWindow: '5年',
  compareIds: [],
  overviewWindow: '5年',
  overviewScope: 'all',
  search: '',
  region: null,
  cache: {},          // id -> full payload
  charts: {},
  chartSizes: {},     // key -> {w,h} the chart was initialised against
};

/* ------------------------------------------------------------------ utils */
function fmt(v, digits = 2) {
  if (v === null || v === undefined || Number.isNaN(v)) return '—';
  return Number(v).toFixed(digits);
}
function fmtPct(v, digits = 1) {
  if (v === null || v === undefined || Number.isNaN(v)) return '—';
  return Number(v).toFixed(digits) + '%';
}
function fmtInt(v) {
  if (v === null || v === undefined || Number.isNaN(v)) return '—';
  return Number(v).toLocaleString('en-US');
}
function el(id) { return document.getElementById(id); }
function esc(s) {
  return String(s === null || s === undefined ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
function bandChip(band, pct) {
  if (!band || pct === null || pct === undefined) {
    return '<span class="ixpct nope">无PE</span>';
  }
  return `<span class="ixpct" style="background:${band.color};color:#0d1117">`
       + `${escape(band.label)} ${fmtPct(pct, 0)}</span>`;
}
function bandChipSmall(band, pct) {
  if (!band || pct === null || pct === undefined) return '<span class="muted">—</span>';
  return `<span class="pctchip" style="background:${band.color}">${fmtPct(pct, 0)}</span>`;
}
function escape(s) { return esc(s); }

/* --------------------------------------------------------------- data i/o */
async function loadJSON(url) {
  const r = await fetch(url, { cache: 'no-store' });
  if (!r.ok) throw new Error(url + ' → HTTP ' + r.status);
  return r.json();
}

async function getIndexPayload(id) {
  if (!state.cache[id]) {
    state.cache[id] = await loadJSON(`data/index/${id}.json`);
  }
  return state.cache[id];
}

/* Returns the series object for the primary series of a payload. */
function primarySeries(payload) {
  if (!payload || !payload.series || !payload.series.length) return null;
  return payload.series.find(s => s.series_id === payload.primary_series)
      || payload.series[0];
}

/* --------------------------------------------------------------- sidebar */
function visibleRows() {
  const q = state.search.trim().toLowerCase();
  return state.summary.filter(r => {
    if (state.region && r.region !== state.region) return false;
    if (!q) return true;
    return [r.id, r.name, r.country, r.region, r.note]
      .some(v => String(v || '').toLowerCase().includes(q));
  });
}

function renderChips() {
  const box = el('regionchips');
  const regions = state.manifest.regions || [];
  const counts = {};
  state.summary.forEach(r => { counts[r.region] = (counts[r.region] || 0) + 1; });
  box.innerHTML = regions.map(rg =>
    `<button class="chip${state.region === rg ? ' on' : ''}" data-region="${esc(rg)}">`
    + `${esc(rg)} ${counts[rg] || 0}</button>`).join('')
    + (state.region ? '<button class="chip" data-region="">全部</button>' : '');
  box.querySelectorAll('.chip').forEach(b => {
    b.onclick = () => { state.region = b.dataset.region || null; renderChips(); renderList(); };
  });
}

function renderList() {
  const rows = visibleRows();
  const box = el('indices');
  if (!rows.length) { box.innerHTML = '<div class="empty" style="padding:24px 8px">无匹配指数</div>'; return; }
  const byRegion = {};
  rows.forEach(r => { (byRegion[r.region] = byRegion[r.region] || []).push(r); });

  let html = '';
  (state.manifest.regions || []).forEach(rg => {
    const list = byRegion[rg];
    if (!list || !list.length) return;
    html += `<div class="grp">${esc(rg)}</div>`;
    list.forEach(r => {
      const on = state.selected.has(r.id) ? ' checked' : '';
      const act = state.activeId === r.id ? ' active' : '';
      const sub = r.has_pe
        ? `${esc(r.country)} · ${fmt(r.current_pe)}× · ${esc(r.series_label)}`
        : `${esc(r.country)} · 仅点位（无PE源）`;
      html += `<div class="ixrow${act}" data-id="${esc(r.id)}">`
        + `<input type="checkbox" data-check="${esc(r.id)}"${on}/>`
        + `<div class="ixmain"><div class="ixname">${esc(r.name)}</div>`
        + `<div class="ixsub">${sub}</div></div>`
        + bandChip(r.primary_band, r.primary_pct)
        + `</div>`;
    });
  });
  box.innerHTML = html;

  box.querySelectorAll('.ixrow').forEach(row => {
    row.onclick = (e) => {
      const id = row.dataset.id;
      if (e.target.tagName === 'INPUT') return;
      state.activeId = id;
      state.selected.add(id);            // clicking the row selects it too
      syncSelection();
      renderList();
      showTab('detail');
      renderDetailFor(id);
    };
  });
  box.querySelectorAll('input[data-check]').forEach(cb => {
    cb.onclick = (e) => {
      e.stopPropagation();
      const id = cb.dataset.check;
      if (cb.checked) state.selected.add(id); else state.selected.delete(id);
      syncSelection();
      renderList();
    };
  });
}

function syncSelection() {
  el('selcount').textContent = `已勾选 ${state.selected.size} 项`;
  const ids = [...state.selected];
  if (ids.length >= 2) renderCompare();
  renderOverview();
}

/* ----------------------------------------------------------------- detail */
function setSeg(containerId, attr, value) {
  const box = el(containerId);
  if (!box) return;
  box.querySelectorAll('button').forEach(b => {
    b.classList.toggle('active', b.dataset[attr] === String(value));
  });
}

/* Async entry point: make sure the payload for the active index is loaded
   before rendering, so a click does not race the fetch. */
async function renderDetailFor(id) {
  if (!id) { renderDetail(); return; }
  try {
    await getIndexPayload(id);
  } catch (err) {
    const e = el('detail-empty');
    e.hidden = false; el('detail-body').hidden = true;
    e.textContent = `无法加载 ${id} 的数据：${err.message}`;
    return;
  }
  if (state.activeId !== id) return;   // a newer click won
  renderDetail();
}

function renderDetail() {
  const p = state.cache[state.activeId];
  if (!state.activeId) {
    el('detail-empty').hidden = false;
    el('detail-body').hidden = true;
    el('detail-empty').textContent = '从左侧选择一个指数，查看其滚动 PE 与指数点位的趋势关系。';
    return;
  }
  if (!p) {
    el('detail-empty').hidden = false;
    el('detail-body').hidden = true;
    el('detail-empty').textContent = '正在加载该指数数据…';
    return;
  }
  const row = state.rowsById[state.activeId] || {};
  const s = primarySeries(p);
  if (!s) {
    el('detail-empty').hidden = false;
    el('detail-body').hidden = true;
    el('detail-empty').textContent = '该指数暂无可用序列。';
    return;
  }
  el('detail-empty').hidden = true;
  el('detail-body').hidden = false;

  el('d-name').textContent = p.name;
  el('d-id').textContent = p.id;
  el('d-region').textContent = `${p.region} · ${p.country}`;
  el('d-note').textContent = p.note || '';

  const w = s.windows && s.windows[state.detailWindow];
  const band = w && w.pct !== null && row.primary_band
    ? bandOf(w.pct) : null;

  const badges = [];
  if (p.has_pe) {
    badges.push(`<span class="badge">数据源 ${esc(s.label)}</span>`);
    badges.push(`<span class="badge">${s.n} 个观测点 · ${esc(s.freq)}频</span>`);
    if (w && w.pct !== null) {
      const b = bandOf(w.pct);
      badges.push(`<span class="badge band" style="background:${b.color}">`
        + `${esc(b.label)} · ${state.detailWindow}分位 ${fmtPct(w.pct)}</span>`);
    }
  } else {
    badges.push('<span class="badge">仅指数点位 · 无公开PE源</span>');
  }
  if (p.price_source) {
    badges.push(`<span class="badge">价格源 ${esc(p.price_source)} (${fmtInt(p.price_n)})</span>`);
  }
  if (p.price_note) {
    badges.push(`<span class="badge proxy">${esc(p.price_note)}</span>`);
  }
  el('d-badges').innerHTML = badges.join('');

  // ---- KPI cards
  const kpis = [];
  if (p.has_pe) {
    kpis.push(kpi('最新 PE', s.current_pe === null ? '—' : fmt(s.current_pe, 2) + '×',
      `截至 ${s.last}`));
    kpis.push(kpi(`${state.detailWindow}分位`,
      w && w.pct !== null ? fmtPct(w.pct) : '数据不足',
      w ? `窗口 ${w.start} → ${w.end} · ${w.n} 点` : ''));
    if (w && w.median !== null) {
      kpis.push(kpi('窗口 PE 中位', fmt(w.median, 2) + '×',
        `最低 ${fmt(w.min, 2)} · 最高 ${fmt(w.max, 2)}`));
    }
    if (w && w.drawdown_from_max !== null) {
      kpis.push(kpi('距窗口PE高点', fmtPct(w.drawdown_from_max), 'PE 相对窗口峰值的偏离'));
    }
  }
  kpis.push(kpi('最新指数点位', fmt(s.current_price),
    s.price_start ? `PE序列起点时 ${fmt(s.price_start)}` : ''));
  kpis.push(kpi('观测区间', `${s.first.slice(0, 4)}–${s.last.slice(0, 4)}`,
    `${s.n} 个 PE 观测点`));
  el('d-kpis').innerHTML = kpis.join('');

  // ---- window selector
  const winBox = el('d-windows');
  const labels = Object.keys(s.windows || {});
  winBox.innerHTML = labels.map(l =>
    `<button data-win="${esc(l)}"${l === state.detailWindow ? ' class="active"' : ''}>`
    + `${esc(l)}</button>`).join('');
  winBox.querySelectorAll('button').forEach(b => {
    b.onclick = () => { state.detailWindow = b.dataset.win; renderDetail(); };
  });

  renderDetailChart(p, s);

  // ---- gaps + 口径说明
  // Two different things, deliberately kept apart: a gap is missing data, a
  // note is present data that needs a caveat. Rendering both as "数据缺口"
  // would tell the reader an ETF proxy is absent when it is right there.
  const gaps = (p.gaps || []).slice();
  if (p.has_pe && p.price_n && p.price_n < s.n) {
    gaps.push(`价格序列仅 ${fmtInt(p.price_n)} 根，短于 PE 序列的 ${s.n} 点，`
      + '早于价格起点的 PE 观测没有对应点位。');
  }
  const notes = [];
  if (p.price_note) {
    notes.push(`${p.price_note}。PE 取自指数本身，点位取自跟踪该指数的基金，`
      + '两者口径不同，仅作趋势参考，不能据此计算指数的绝对估值。');
  }
  el('d-gaps').innerHTML =
    gaps.map(g => `<div class="gap">数据缺口：${esc(g)}</div>`).join('')
    + notes.map(n => `<div class="gap note">口径说明：${esc(n)}</div>`).join('');
}

function kpi(k, v, s) {
  return `<div class="kpi"><div class="k">${esc(k)}</div>`
       + `<div class="v">${esc(v)}</div><div class="s">${esc(s || '')}</div></div>`;
}

function bandOf(pct) {
  for (const b of (state.manifest.method.bands || [])) {
    if (pct >= b.lo && pct < b.hi) return b;
  }
  return { label: '—', color: '#63707d' };
}

function ensureChart(key, dom) {
  const w = dom.clientWidth;
  const h = dom.clientHeight;
  const inst = state.charts[key];
  if (inst && !inst.isDisposed()) {
    // A chart first initialised while its tab was hidden caches a 0/100px size
    // and ECharts will not recover from a plain resize(); rebuild it instead.
    const seen = state.chartSizes[key];
    if (seen && seen.w === w && seen.h === h) return inst;
    inst.dispose();
    delete state.charts[key];
  }
  state.charts[key] = echarts.init(dom, null, { renderer: 'canvas' });
  state.chartSizes[key] = { w, h };
  return state.charts[key];
}

const AXIS_LINE = { lineStyle: { color: '#33404f' } };
const SPLIT_LINE = { lineStyle: { color: '#222c38' } };
const AXIS_LABEL = { color: '#8b98a5', fontSize: 10 };
const TOOLTIP = {
  trigger: 'axis',
  backgroundColor: 'rgba(21,27,35,.96)',
  borderColor: '#33404f',
  textStyle: { color: '#e6edf3', fontSize: 11 },
  axisPointer: { type: 'cross', lineStyle: { color: '#4a5563' }, crossStyle: { color: '#4a5563' } },
};

function pctBandAreas(yAxisIndex) {
  return (state.manifest.method.bands || []).map(b => ([{
    yAxisIndex, silent: true,
    itemStyle: { color: b.color, opacity: 0.085 },
    label: { show: false },
  }, { yAxisIndex: yAxisIndex + 1 }]));
}

function renderDetailChart(p, s) {
  const dom = el('d-chart');
  const chart = ensureChart('detail', dom);
  const dates = s.date;
  const mode = state.detailMode;

  const series = [];
  const legend = [];

  if (mode === 'pct') {
    const arr = (s.percentile || {})[state.detailWindow] || [];
    series.push({
      name: `${state.detailWindow}滚动分位`,
      type: 'line', data: arr, showSymbol: false, smooth: false,
      lineStyle: { width: 1.8, color: COLOR_PCT },
      itemStyle: { color: COLOR_PCT },
      areaStyle: { color: 'rgba(74,158,218,.14)' },
      yAxisIndex: 0,
    });
    legend.push({ n: `${state.detailWindow}滚动分位`, c: COLOR_PCT });
  } else if (mode === 'norm') {
    series.push({
      name: 'PE 归一化 (首点=100)', type: 'line', data: s.norm_pe,
      showSymbol: false, lineStyle: { width: 1.8, color: COLOR_PE },
      itemStyle: { color: COLOR_PE }, yAxisIndex: 0,
    });
    series.push({
      name: '指数点位归一化 (首点=100)', type: 'line', data: s.norm_price,
      showSymbol: false, lineStyle: { width: 1.6, color: COLOR_PRICE, type: 'dashed' },
      itemStyle: { color: COLOR_PRICE }, yAxisIndex: 0,
    });
    legend.push({ n: 'PE 归一化', c: COLOR_PE });
    legend.push({ n: '点位归一化', c: COLOR_PRICE });
  } else {
    series.push({
      name: 'PE (倍)', type: 'line', data: s.pe, showSymbol: false,
      lineStyle: { width: 1.8, color: COLOR_PE }, itemStyle: { color: COLOR_PE },
      yAxisIndex: 0,
      markLine: s.windows && s.windows[state.detailWindow] && s.windows[state.detailWindow].median !== null
        ? {
            silent: true, symbol: 'none',
            lineStyle: { color: COLOR_PE, type: 'dotted', opacity: .6 },
            label: { formatter: '窗口中位 {c}', color: '#8b98a5', fontSize: 10 },
            data: [{ yAxis: s.windows[state.detailWindow].median }],
          } : undefined,
    });
    series.push({
      name: '指数点位', type: 'line', data: s.price, showSymbol: false,
      lineStyle: { width: 1.4, color: COLOR_PRICE }, itemStyle: { color: COLOR_PRICE },
      yAxisIndex: 1,
    });
    legend.push({ n: 'PE (倍)', c: COLOR_PE });
    legend.push({ n: '指数点位', c: COLOR_PRICE });
  }

  const yAxis = mode === 'dual' ? [
    {
      type: 'value', name: 'PE', nameTextStyle: AXIS_LABEL, scale: true,
      axisLabel: { ...AXIS_LABEL, formatter: v => Number(v).toFixed(0) + '×' },
      axisLine: AXIS_LINE, splitLine: SPLIT_LINE, nameGap: 14,
    },
    {
      type: 'value', name: '点位', nameTextStyle: AXIS_LABEL, scale: true,
      axisLabel: { ...AXIS_LABEL, formatter: v => fmtInt(v) },
      axisLine: AXIS_LINE, splitLine: { show: false }, nameGap: 14,
    },
  ] : [{
    type: 'value', scale: true,
    name: mode === 'pct' ? '分位 (%)' : '归一化',
    nameTextStyle: AXIS_LABEL,
    axisLabel: { ...AXIS_LABEL, formatter: v => mode === 'pct' ? Number(v).toFixed(0) + '%' : Number(v).toFixed(0) },
    axisLine: AXIS_LINE, splitLine: SPLIT_LINE, nameGap: 14,
    ...(mode === 'pct' ? { min: 0, max: 100, interval: 20 } : {}),
  }];

  chart.setOption({
    animation: false,
    grid: { left: 58, right: mode === 'dual' ? 70 : 26, top: 22, bottom: 46 },
    tooltip: {
      ...TOOLTIP,
      formatter: (ps) => {
        if (!ps || !ps.length) return '';
        let out = `<b>${ps[0].axisValue}</b>`;
        ps.forEach(x => {
          let v = x.value;
          if (v === null || v === undefined) return;
          let txt;
          if (mode === 'pct') txt = fmtPct(v);
          else if (mode === 'dual' && x.seriesName === '指数点位') txt = fmtInt(v);
          else txt = fmt(v, 2);
          out += `<br/><span style="color:${x.color}">●</span> ${esc(x.seriesName)}: <b>${txt}</b>`;
        });
        const w = s.windows && s.windows[state.detailWindow];
        if (w && w.pct !== null && w.pct !== undefined) {
          out += `<br/><span style="color:#63707d">${state.detailWindow}窗口 ${w.start}→${w.end} · ${w.n}点</span>`;
        }
        return out;
      },
    },
    dataZoom: [
      { type: 'inside', xAxisIndex: 0 },
      { type: 'slider', xAxisIndex: 0, height: 18, bottom: 8,
        borderColor: '#28323f', fillerColor: 'rgba(74,158,218,.12)',
        handleStyle: { color: '#4a5563' }, textStyle: { color: '#63707d', fontSize: 9 },
        dataBackground: { lineStyle: { color: '#33404f' }, areaStyle: { color: '#222c38' } } },
    ],
    xAxis: {
      type: 'category', data: dates, boundaryGap: false,
      axisLabel: { ...AXIS_LABEL, formatter: v => String(v).slice(0, 7) },
      axisLine: AXIS_LINE, splitLine: { show: false },
    },
    yAxis,
    series,
  }, true);

  el('d-legend').innerHTML = legend.map(l =>
    `<span><span class="sw" style="background:${l.c}"></span>${esc(l.n)}</span>`).join('')
    + (mode === 'pct'
      ? (state.manifest.method.bands || []).map(b =>
          `<span><span class="sw" style="background:${b.color}"></span>${esc(b.label)} `
          + `${b.lo}–${Math.min(b.hi, 100)}</span>`).join('')
      : '');
  chart.resize();
}

/* ---------------------------------------------------------------- compare */
function renderCompare() {
  const ids = [...state.selected];
  el('c-empty').hidden = ids.length >= 2;
  const dom = el('c-chart');
  if (ids.length < 2) {
    if (state.charts.compare && !state.charts.compare.isDisposed()) {
      state.charts.compare.clear();
    }
    el('c-note').textContent = '至少勾选 2 个指数才能对比。';
    return;
  }
  const rows = ids.map(id => state.rowsById[id]).filter(Boolean);
  const usePct = state.compareMetric === 'pct';
  const useNorm = state.compareMetric === 'normpe' || state.compareMetric === 'normprice';

  el('c-note').textContent = usePct
    ? `对比 ${rows.length} 个指数的滚动分位（窗口：${state.compareWindow}）；分位为各自窗口内的相对位置。`
    : `对比 ${rows.length} 个指数的${state.compareMetric === 'pe' ? '市盈率水平' : '归一化序列'}；`
      + '不同来源的 PE 水平不可直接比较高低。';

  const withData = rows.filter(r => usePct ? r.has_pe : true);
  if (!withData.length) {
    el('c-note').textContent = '所选指数均无 PE 序列，无法计算滚动分位。可改选「归一化点位」。';
    return;
  }

  const chart = ensureChart('compare', dom);
  chart.showLoading({ text: '', color: COLOR_PCT, maskColor: 'rgba(13,17,23,.7)' });

  Promise.all(rows.map(r => getIndexPayload(r.id).catch(() => null))).then(payloads => {
    chart.hideLoading();
    const series = [];
    const pairs = [];   // {name, dates, data} for the merged-axis alignment below
    state.compareIds = [];

    payloads.forEach((p, i) => {
      if (!p) return;
      const s = primarySeries(p);
      if (!s) return;
      const color = SERIES_COLORS[i % SERIES_COLORS.length];
      let data, name;
      if (usePct) {
        if (!p.has_pe) return;
        data = (s.percentile || {})[state.compareWindow] || [];
        name = `${p.name} ${state.compareWindow}分位`;
      } else if (state.compareMetric === 'pe') {
        if (!p.has_pe) return;
        data = s.pe;
        name = `${p.name} PE`;
      } else if (state.compareMetric === 'normpe') {
        if (!p.has_pe) return;
        data = s.norm_pe;
        name = `${p.name} PE归一化`;
      } else {
        data = s.norm_price;
        name = `${p.name} 点位归一化`;
      }
      state.compareIds.push(p.id);
      pairs.push({ name, dates: s.date, data });
      series.push({
        name, type: 'line', data, showSymbol: false,
        // The axis is the union of every chosen index's observation dates, so a
        // weekly series is null on ~6 of every 7 daily slots. Those nulls mean
        // "this index is not sampled that day", NOT "data is missing", so the
        // line must bridge them - otherwise with showSymbol:false a weekly
        // series collapses into invisible isolated points and only the densest
        // daily series is visible at all.
        connectNulls: true,
        lineStyle: { width: 1.7, color }, itemStyle: { color },
      });
    });

    if (!series.length) {
      el('c-note').textContent = '所选指数在该指标下没有可用数据。';
      return;
    }

    // Merge every chosen series onto one sorted date axis, then realign each
    // series onto it (a null where that index has no observation that day).
    const axisSet = new Set();
    pairs.forEach(pr => pr.dates.forEach(d => axisSet.add(d)));
    const mergedDates = [...axisSet].sort();
    const slot = new Map(mergedDates.map((d, i) => [d, i]));
    const aligned = series.map((sr, k) => {
      const pr = pairs[k];
      const out = new Array(mergedDates.length).fill(null);
      pr.dates.forEach((d, i) => {
        const j = slot.get(d);
        if (j !== undefined) out[j] = pr.data[i];
      });
      return { ...sr, data: out };
    });

    chart.setOption({
      animation: false,
      color: SERIES_COLORS,
      grid: { left: 58, right: 22, top: 20, bottom: 48 },
      tooltip: {
        ...TOOLTIP,
        formatter: (ps) => {
          if (!ps || !ps.length) return '';
          let out = `<b>${ps[0].axisValue}</b>`;
          ps.forEach(x => {
            const v = x.value;
            if (v === null || v === undefined) return;
            const txt = (usePct || state.compareMetric === 'normpe'
                         || state.compareMetric === 'normprice') ? fmtPct(v) : fmt(v, 2);
            out += `<br/><span style="color:${x.color}">●</span> ${esc(x.seriesName)}: <b>${txt}</b>`;
          });
          return out;
        },
      },
      dataZoom: [
        { type: 'inside', xAxisIndex: 0 },
        { type: 'slider', xAxisIndex: 0, height: 18, bottom: 8,
          borderColor: '#28323f', fillerColor: 'rgba(74,158,218,.12)',
          handleStyle: { color: '#4a5563' }, textStyle: { color: '#63707d', fontSize: 9 },
          dataBackground: { lineStyle: { color: '#33404f' }, areaStyle: { color: '#222c38' } } },
      ],
      legend: {
        type: 'scroll', bottom: 28, textStyle: { color: '#8b98a5', fontSize: 10 },
        itemWidth: 14, itemHeight: 8, pageTextStyle: { color: '#63707d' },
      },
      xAxis: {
        type: 'category', data: mergedDates, boundaryGap: false,
        axisLabel: { ...AXIS_LABEL, formatter: v => String(v).slice(0, 7) },
        axisLine: AXIS_LINE, splitLine: { show: false },
      },
      yAxis: {
        type: 'value', scale: true,
        name: usePct ? '滚动分位 (%)' : (state.compareMetric === 'pe' ? 'PE (倍)' : '归一化'),
        nameTextStyle: AXIS_LABEL,
        axisLabel: {
          ...AXIS_LABEL,
          formatter: v => usePct ? Number(v).toFixed(0) + '%'
            : (state.compareMetric === 'pe' ? Number(v).toFixed(0) + '×' : Number(v).toFixed(0)),
        },
        axisLine: AXIS_LINE, splitLine: SPLIT_LINE, nameGap: 14,
        ...(usePct ? { min: 0, max: 100, interval: 20 } : {}),
      },
      series: aligned,
    }, true);
    chart.resize();
  });
}

/* --------------------------------------------------------------- overview */
function overviewRows() {
  let rows = state.summary.filter(r => r.has_pe);
  if (state.overviewScope === 'developed') rows = rows.filter(r => r.developed);
  if (state.overviewScope === 'a') rows = rows.filter(r => r.region === '中国A股');
  return rows
    .filter(r => {
      const w = r.windows && r.windows[state.overviewWindow];
      return w && w.pct !== null && w.pct !== undefined;
    })
    .sort((a, b) => {
      const pa = a.windows[state.overviewWindow].pct;
      const pb = b.windows[state.overviewWindow].pct;
      return pb - pa;
    });
}

function renderOverview() {
  const dom = el('o-chart');
  if (!dom) return;
  const rows = overviewRows();
  const chart = ensureChart('overview', dom);

  if (!rows.length) {
    chart.clear();
    chart.setOption({
      animation: false,
      title: {
        text: `「${state.overviewWindow}」窗口下没有可用的分位数据\n可换用更长的窗口`,
        left: 'center', top: 'middle',
        textStyle: { color: '#63707d', fontSize: 12, lineHeight: 20 },
      },
    });
    el('o-table').innerHTML = '';
    return;
  }

  chart.setOption({
    animation: false,
    grid: { left: 132, right: 62, top: 16, bottom: 34 },
    tooltip: {
      ...TOOLTIP,
      formatter: (ps) => {
        const x = ps[0];
        const r = rows[x.dataIndex];
        const w = r.windows[state.overviewWindow];
        const b = bandOf(w.pct);
        return `<b>${esc(r.name)}</b> <span style="color:#63707d">${esc(r.id)}</span>`
          + `<br/>${esc(r.region)} · ${esc(r.country)}`
          + `<br/><span style="color:${b.color}">●</span> ${state.overviewWindow}分位: <b>${fmtPct(w.pct)}</b> (${esc(b.label)})`
          + `<br/>窗口 ${w.start} → ${w.end} · ${w.n} 点`
          + `<br/>最新 PE ${fmt(r.current_pe)}× · 数据源 ${esc(r.series_label)}`;
      },
    },
    xAxis: {
      type: 'value', min: 0, max: 100, interval: 20,
      axisLabel: { ...AXIS_LABEL, formatter: v => v + '%' },
      axisLine: AXIS_LINE, splitLine: SPLIT_LINE,
    },
    yAxis: {
      type: 'category',
      data: rows.map(r => r.name),
      axisLabel: { ...AXIS_LABEL, fontSize: 10.5, color: '#c3ccd6' },
      axisLine: { show: false }, axisTick: { show: false },
    },
    series: [{
      type: 'bar',
      data: rows.map(r => {
        const pct = r.windows[state.overviewWindow].pct;
        return { value: pct, itemStyle: { color: bandOf(pct).color, borderRadius: [0, 3, 3, 0] } };
      }),
      barMaxWidth: 15,
      label: {
        show: true, position: 'right', color: '#8b98a5', fontSize: 10,
        formatter: p => fmtPct(p.value, 1),
      },
      markLine: {
        silent: true, symbol: 'none',
        lineStyle: { color: '#33404f', type: 'dashed' },
        label: { color: '#63707d', fontSize: 9 },
        data: [
          { xAxis: 20, label: { formatter: '低估线 20%' } },
          { xAxis: 80, label: { formatter: '高估线 80%' } },
        ],
      },
    }],
  }, true);
  chart.resize();

  // ---- table
  el('o-table').innerHTML =
    '<thead><tr><th>指数</th><th>地区</th><th>最新PE</th><th>'
    + state.overviewWindow + '分位</th><th>1年</th><th>3年</th><th>5年</th><th>10年</th>'
    + '<th>全历史</th><th>数据源</th></tr></thead><tbody>'
    + state.summary.filter(r => r.has_pe)
        .filter(r => state.overviewScope === 'all' ? true
          : (state.overviewScope === 'developed' ? r.developed : r.region === '中国A股'))
        .sort((a, b) => {
          const pa = (a.windows['5年'] || {}).pct, pb = (b.windows['5年'] || {}).pct;
          return (pb === null ? -1 : pb) - (pa === null ? -1 : pa);
        })
        .map(r => {
          const cells = ['1年', '3年', '5年', '10年', '全历史'].map(w => {
            const v = r.windows[w];
            if (!v || v.pct === null || v.pct === undefined) {
              return '<td class="muted" title="窗口内观测不足">—</td>';
            }
            return `<td>${bandChipSmall(bandOf(v.pct), v.pct)}</td>`;
          }).join('');
          const cls = state.activeId === r.id ? ' class="on"' : '';
          const sel = r.windows[state.overviewWindow] || {};
          return `<tr data-id="${esc(r.id)}"${cls}><td><b>${esc(r.name)}</b>`
            + `<br/><span class="muted" style="font-size:10px">${esc(r.id)}</span></td>`
            + `<td>${esc(r.region)}</td><td>${fmt(r.current_pe)}×</td>`
            + `<td>${sel.pct === null || sel.pct === undefined
                 ? '<span class="muted">—</span>'
                 : bandChipSmall(bandOf(sel.pct), sel.pct)}</td>`
            + cells
            + `<td style="font-size:10px" class="muted">${esc(r.series_label)}</td></tr>`;
        }).join('')
    + '</tbody>';
  el('o-table').querySelectorAll('tbody tr').forEach(tr => {
    tr.onclick = () => {
      state.activeId = tr.dataset.id;
      if (!state.selected.has(tr.dataset.id)) state.selected.add(tr.dataset.id);
      syncSelection(); renderList(); showTab('detail'); renderDetailFor(tr.dataset.id);
    };
  });
}

/* ------------------------------------------------------------------- tabs */
function showTab(name) {
  document.querySelectorAll('.tab').forEach(t =>
    t.classList.toggle('active', t.dataset.view === name));
  document.querySelectorAll('.view').forEach(v =>
    v.classList.toggle('active', v.id === 'view-' + name));
  if (name === 'detail') {
    if (state.activeId && !state.cache[state.activeId]) renderDetailFor(state.activeId);
    else renderDetail();
  }
  if (name === 'compare') renderCompare();
  if (name === 'overview') renderOverview();
  Object.values(state.charts).forEach(c => { if (c && !c.isDisposed()) c.resize(); });
}

/* ---------------------------------------------------------------- method */
function renderMethod() {
  const m = state.manifest;
  const src = m.sources || {};
  const method = m.method || {};
  const bands = method.bands || [];
  el('method-body').innerHTML = `
    <h4>这个页面回答什么问题</h4>
    <p>同一张图上，看一个股指当前的 <b>滚动市盈率分位</b> 与 <b>指数点位</b> 长期是怎么走的。
       分位回答「现在的 PE 在它自己最近 N 年里算贵还是便宜」，点位回答「市场自己走到了哪」。
       两者放在一起，就是所谓「溢价情况」——PE 分位高而点位没跟上，说明涨的是盈利；
       分位和点位同步冲高，说明涨的是估值。</p>

    <h4>滚动窗口分位（本页的核心口径）</h4>
    <div class="quote">
      对每个观测日的 PE，取<b>以该日为终点、按自然日回溯 N 年</b>的窗口，
      计算该 PE 在窗口内的百分位：<br/>
      <code>pct = (count(v &lt; x) + 0.5 × count(v == x)) / n × 100</code>
    </div>
    <ul>
      <li>用<b>自然日回溯</b>而不是「最近 N 行」，所以周频（蛋卷）与月频（乐咕乐股 / multpl）可以套用同一套口径，不会偷偷混频。</li>
      <li>用<b>中位秩</b>（对相等值记 0.5）而不是 <code>count(v ≤ x)/n</code>：PE 序列存在大量重复值（四舍五入、整周未变），
          用后者会把一条走平的序列报成 100 分位。</li>
      <li>0 = 窗口内最便宜，100 = 窗口内最贵。<b>这是对历史分布的统计描述，不是买卖信号。</b></li>
      <li><b>充分性规则</b>：${esc(method.sufficiency || '')}
          所以 3 年窗口不会被 6 个月频点冒充成 3 年历史——不满足时直接显示「—」。</li>
    </ul>

    <h4>为什么同时给「全历史」分位</h4>
    <p>绝大多数公开估值表只给全历史（expanding）分位：窗口从序列第一个点开始，越往后越"钝"。
       本页把它和滚动窗口并列显示，两者的差值本身就是信息。</p>

    <h4>分位区间</h4>
    <ul>${bands.map(b =>
      `<li><b style="color:${b.color}">${esc(b.label)}</b>：${b.lo} – ${Math.min(b.hi, 100)}</li>`).join('')}</ul>
    <p class="muted" style="color:#63707d;font-size:11px">区间名称仅是对统计位置的描述性标签，不构成任何投资建议。</p>

    <h4>数据源</h4>
    ${Object.entries(src).map(([k, v]) => `
      <div class="srcrow"><b>${esc(v.name)}</b>
        <span>${esc(v.what)}${v.url ? `<br/><a href="${esc(v.url)}" target="_blank" rel="noopener">${esc(v.url)}</a>` : ''}</span>
      </div>`).join('')}

    <h4>已知缺口（如实声明）</h4>
    <ul>
      <li><b>PE 历史源非常有限</b>：只有蛋卷（周频，约 2016-10 起）与乐咕乐股（月频，2005 起，且仅 12 个 A 股宽基）。
          日经225、英国富时100、法国CAC40、欧洲斯托克50、澳洲、韩国、台湾、加拿大<b>等发达市场没有免费公开的指数 PE 历史序列</b>，
          本页对它们<b>只展示指数点位</b>，并在明细页明确标注。</li>
      <li><b>非美发达市场的价格只有约 4 年</b>（约 1000 个交易日），这是上游源的硬限制，图上起点即是数据边界。</li>
      <li><b>不同来源的 PE 不可比</b>：同一指数在蛋卷与乐咕乐股的口径下 PE 水平系统性不同
          （实测重叠区间：沪深300 差 -4.2%，中证500 差 -17.3%，中证1000 差 -27.9%）。
          因此本页<b>绝不把两个源拼成一条线</b>，而是各自作为独立序列并列呈现。</li>
      <li><b>中证官方日频 PE 有单日重算跳变</b>：全年约 3%–6% 的交易日会出现 ±3% 以上的 PE 水平跳变
          （极端日达 ±20%，如沪深300 在 2011-11-25 为 −19.7%、2012-06-08 为 +16.3%）。
          跳变前后成分股数与收盘价均无明显异动，来源是上游对盈利口径的重新校准，<b>不是行情波动</b>。
          因此日频序列的滚动分位曲线<b>天然带锯齿</b>，相邻两日分位可相差十多个百分点——
          读数应看趋势与区间，<b>不要对单日分位做精确解读</b>。</li>
      <li>指数 PE 全部来自上游发布值，本页<b>不自行用成分股加权计算</b> PE，以保证每个数字都能追溯到命名来源。</li>
    </ul>

    <h4>本次构建</h4>
    <ul>
      <li>版本 ${esc(m.version)} · 生成于 ${esc(m.generated_at)}</li>
      <li>数据截止 <b>${esc(m.as_of || '—')}</b> · 耗时 ${esc(String(m.elapsed_sec))}s</li>
      <li>覆盖 ${m.counts.total} 个指数，其中 ${m.counts.with_pe} 个有 PE 序列、${m.counts.with_price} 个有点位序列</li>
    </ul>
  `;
}

/* --------------------------------------------------------------- freshness */
function renderFreshness() {
  const f = state.manifest.freshness || {};
  const host = el('freshness');
  if (!host) return;
  const bits = [];
  if (f.advanced === true) {
    bits.push(`最近一次自动更新取得了新数据（${esc(f.previous_as_of || '—')} → ${esc(state.manifest.as_of || '—')}）`);
  } else if (f.advanced === false) {
    bits.push(`最近一次自动更新未取得更新的数据（仍为 ${esc(state.manifest.as_of || '—')}）：非交易日、开盘未结算，或上游尚未更新。这不代表本次运行失败。`);
  }
  if (f.stale_responses) {
    const n = Number(f.stale_responses);
    bits.push(`其中 ${n} 个上游请求刷新失败，已回退到上一次成功获取的副本（陈旧但可用）。`);
  }
  // A scoped --only rebuild leaves stale rows in place for the indices it did
  // not touch; say so rather than letting the page imply everything is current.
  if (state.manifest.partial || state.manifest.partial_note) {
    bits.push(esc(state.manifest.partial_note || '部分更新：本次只重建了部分指数'));
  }
  host.innerHTML = bits.map(b => `<div class="freshness-line">${b}</div>`).join('');
  host.hidden = bits.length === 0;
}

/* ------------------------------------------------------------------- init */
async function init() {
  try {
    state.manifest = await loadJSON('data/manifest.json');
  } catch (e) {
    el('detail-empty').textContent = '数据层未生成：先运行 python -m petrace.build。(' + e.message + ')';
    return;
  }
  state.summary = (await loadJSON('data/summary.json')).rows || [];
  state.summary.forEach(r => { state.rowsById[r.id] = r; });

  el('meta-asof').textContent = state.manifest.as_of || '—';
  el('meta-count').textContent = `${state.manifest.counts.with_pe} / ${state.manifest.counts.total}`;
  el('meta-built').textContent = String(state.manifest.generated_at || '').replace('T', ' ').slice(0, 16);
  el('meta-count').title = `${state.manifest.counts.with_pe} 个指数有 PE 序列，`
    + `${state.manifest.counts.with_price} 个有指数点位序列，共 ${state.manifest.counts.total} 个`;
  // Make the freshness of the last automated run visible: a reader must be able
  // to tell "job ran, upstream had nothing new" from "job has been failing".
  renderFreshness();

  renderChips();
  renderList();
  syncSelection();
  renderMethod();

  el('search').oninput = (e) => { state.search = e.target.value; renderList(); };
  el('btn-method').onclick = () => { el('modal-method').hidden = false; };
  el('btn-closemethod').onclick = () => { el('modal-method').hidden = true; };
  el('modal-method').onclick = (e) => {
    if (e.target === el('modal-method')) el('modal-method').hidden = true;
  };
  el('btn-clearsel').onclick = () => {
    state.selected.clear(); syncSelection(); renderList();
  };

  document.querySelectorAll('.tab').forEach(t => {
    t.onclick = () => showTab(t.dataset.view);
  });

  el('d-mode').querySelectorAll('button').forEach(b => {
    b.onclick = () => {
      state.detailMode = b.dataset.mode;
      setSeg('d-mode', 'mode', state.detailMode);
      renderDetail();
    };
  });

  el('c-metric').querySelectorAll('button').forEach(b => {
    b.onclick = () => {
      state.compareMetric = b.dataset.metric;
      setSeg('c-metric', 'metric', state.compareMetric);
      renderCompare();
    };
  });
  el('o-scope').querySelectorAll('button').forEach(b => {
    b.onclick = () => {
      state.overviewScope = b.dataset.scope;
      setSeg('o-scope', 'scope', state.overviewScope);
      renderOverview();
    };
  });

  // window pickers for compare + overview
  const winLabels = ['1年', '3年', '5年', '10年', '全历史'];
  el('c-windows').innerHTML = winLabels.map(w =>
    `<button data-win="${w}"${w === state.compareWindow ? ' class="active"' : ''}>${w}</button>`).join('');
  el('c-windows').querySelectorAll('button').forEach(b => {
    b.onclick = () => {
      state.compareWindow = b.dataset.win;
      setSeg('c-windows', 'win', state.compareWindow);
      renderCompare();
    };
  });
  el('o-windows').innerHTML = winLabels.map(w =>
    `<button data-win="${w}"${w === state.overviewWindow ? ' class="active"' : ''}>${w}</button>`).join('');
  el('o-windows').querySelectorAll('button').forEach(b => {
    b.onclick = () => {
      state.overviewWindow = b.dataset.win;
      setSeg('o-windows', 'win', state.overviewWindow);
      renderOverview();
    };
  });

  window.addEventListener('resize', () => {
    Object.values(state.charts).forEach(c => { if (c && !c.isDisposed()) c.resize(); });
  });

  // Deep link: #ID opens that index directly.
  const hash = decodeURIComponent(location.hash.replace('#', ''));
  if (hash && state.rowsById[hash]) {
    state.activeId = hash; state.selected.add(hash);
    syncSelection(); renderList(); showTab('detail');
  } else {
    renderOverview();
  }
  showTab('detail');
}

window.addEventListener('hashchange', () => {
  const hash = decodeURIComponent(location.hash.replace('#', ''));
  if (hash && state.rowsById[hash]) {
    state.activeId = hash;
    if (!state.selected.has(hash)) state.selected.add(hash);
    syncSelection(); renderList(); showTab('detail');
  }
});

document.addEventListener('DOMContentLoaded', init);
