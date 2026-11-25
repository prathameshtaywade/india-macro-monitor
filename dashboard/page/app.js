// India Macro Monitor — drawings for the dashboard page.
(function () {
  const MM = (window.MM = window.MM || { topic: 'all', ex: 'cpi_infl_combined', showOld: false });
  // One shared timeline for every history chart, so dates line up across both tabs. Older data stays in the files.
  const CHART_START = '2023-04-01';
  // RBI moved the bank reporting date to month-end in Dec 2025; until Nov 2026 y/y growth compares a
  // month-end with the corresponding reporting Friday a year earlier. Shaded on the brief chart.
  const REPORTING_MIX = { from: '2025-12-01', to: '2026-11-30', label: 'Friday comparator' };
  const parse = d3.utcParse('%Y-%m-%d');
  const MINUS = '−';
  const IIP_UNIT = 'Index (2022-23=100)';
  const POLICY_NAMES = new Map([['repo', 'Policy Repo Rate'], ['sdf', 'Standing Deposit Facility Rate'],
    ['msf', 'Marginal Standing Facility Rate'], ['crr', 'Cash Reserve Ratio'], ['slr', 'Statutory Liquidity Ratio']]);
  const POLICY_CORRIDOR = ['repo', 'sdf', 'msf'];
  const indiaToday = new Intl.DateTimeFormat('en', {
    timeZone: 'Asia/Kolkata', year: 'numeric', month: '2-digit', day: '2-digit',
  }).formatToParts(new Date());
  const dashboardDay = ['year', 'month', 'day'].map((part) => indiaToday.find((p) => p.type === part).value).join('-');
  const isScheduled = (row) => !!row?.date && POLICY_NAMES.has(row.series) && row.date > dashboardDay;
  const periodLabel = (row) => row.label + (isScheduled(row) ? ' (scheduled)' : '');
  const rateNumber = (v) => v == null || v === '' ? NaN : Number(v);

  // ---------- latest value per series (a calc, so every tile can be traced) ----------
  dash.calc('latest', {
    inputs: ['observations'],
    title: 'Latest value per series',
    description: 'Last and previous observation of each series, rounded as shown on the page; change = last minus previous.',
    fn: (observations) => {
      const places = { gdp_growth_q: 1, iip_index: 1, forex_w: 1, forex_m: 1, scb_credit_yoy: 1, scb_dep_yoy: 1,
        scb_gap: 2, scb_gap_3m: 2, scb_inc_cd_fytd: 1, mmo_call_spread: 0, mmo_call_spread_5d: 0, mmo_net_liq: 2,
        pricing_gap_fresh: 2 };
      const bySeries = {};
      for (const r of observations) {
        if (!isScheduled(r)) (bySeries[r.series] = bySeries[r.series] || []).push(r);
      }
      return Object.entries(bySeries).map(([series, rows]) => {
        rows.sort((a, b) => ((a.date || a.period) < (b.date || b.period) ? -1 : 1));
        const p = places[series] ?? 2;
        const round = (v) => (v == null ? null : +(+v).toFixed(p));
        const last = rows[rows.length - 1], prev = rows[rows.length - 2];
        return {
          series, label: last.label, value: round(last.value),
          prev_label: prev ? prev.label : null, prev: prev ? round(prev.value) : null,
          change: prev ? +(round(last.value) - round(prev.value)).toFixed(p) : null,
        };
      });
    },
  });

  // ---------- formatting ----------
  const UNIT = {}; // filled from catalog
  function fmt(v, unit, p) {
    if (v == null || isNaN(v)) return '—';
    const s = (Math.abs(v)).toFixed(p ?? 2), sign = v < 0 ? MINUS : '';
    if (unit === '%' || unit === '% p.a.') return sign + s + '%';
    if (unit === 'pp') return sign + s + ' pp';
    if (unit === 'bp') return sign + Math.abs(v).toFixed(p ?? 0) + ' bp';
    if (unit === '₹ crore') return sign + '₹' + Math.abs(v).toLocaleString('en-IN', { maximumFractionDigits: p ?? 0 }) + ' crore';
    if (unit === 'US$ bn') return sign + '$' + (+Math.abs(v)).toFixed(p ?? 1) + ' bn';
    if (unit && unit.startsWith('₹ per')) return sign + '₹' + s;
    if (unit === '₹ lakh crore') return sign + '₹' + (+Math.abs(v)).toFixed(p ?? 1) + ' lakh cr';
    return sign + s;
  }
  function fmtTick(v, unit) {
    if (unit === '%' || unit === '% p.a.') return d3.format('~r')(+v.toFixed(2)) + '%';
    if (unit === 'US$ bn') return '$' + d3.format(',~r')(v);
    if (unit === 'pp') return d3.format('~r')(+v.toFixed(2)) + ' pp';
    if (unit === 'bp') return d3.format('~r')(+v.toFixed(1)) + ' bp';
    if (unit === '₹ crore') return d3.format('~r')(+(v / 1e5).toFixed(2)) + ' L cr';
    return d3.format(',~r')(+v.toFixed(2));
  }
  function msg(text) { const p = document.createElement('p'); p.className = 'mm-muted'; p.textContent = text; return p; }
  function statusText(st) { return st === 'error' ? "Couldn't load this data." : st === 'loading' ? '—' : '—'; }

  // ---------- index observations by series ----------
  function index() {
    const o = dash.data('observations');
    if (o.status !== 'ok') return null;
    if (MM._src === o.data) return MM._idx;
    const m = new Map(), raw = new Map(); let max = null;
    for (const r of o.data) {
      (raw.get(r.series) || raw.set(r.series, []).get(r.series)).push(r);
      if (!r.date || isScheduled(r)) continue;
      const d = parse(r.date);
      (m.get(r.series) || m.set(r.series, []).get(r.series)).push({ d, v: +r.value, label: r.label });
      if (!max || d > max) max = d;
    }
    for (const a of m.values()) a.sort((a, b) => a.d - b.d);
    MM._src = o.data; MM._idx = { m, raw, max };
    return MM._idx;
  }
  function catalogRows() { const c = dash.data('catalog'); return c.status === 'ok' ? c.data : null; }

  // ---------- chart configs ----------
  const CH = {
    output: { unit: '₹ lakh crore', aria: 'Line chart of real GDP and GVA in lakh crore rupees by quarter', series: [
      ['gdp_level_q', 'Real GDP'], ['gva_level_q', 'Real GVA']] },
    cpi: { unit: '%', zero: true, band: [2, 6], ref: 4, refLabel: '4% target', aria: 'Line chart of CPI inflation with the 2 to 6 percent band', series: [
      ['cpi_infl_old', 'Headline, 2012 base', { muted: true, old: true }], ['cpi_infl_combined', 'Headline, 2024 base']] },
    food: { unit: '%', zero: true, aria: 'Line chart of food inflation', series: [
      ['cpi_food', 'Food & beverages, 2024 base'],
      ['cfpi_old', 'Consumer Food Price Index, 2012 base', { muted: true, dash: true, old: true }]] },
    iip: { unit: IIP_UNIT, digits: 1, aria: 'Line chart of industrial production index levels', series: [
      ['iip_index', 'General IIP'], ['iip_manufacturing_index', 'Manufacturing', { dash: true }]] },
    policy: { unit: '%', aria: 'Step chart of repo, SDF and MSF rates with the call money rate', series: [
      ['repo', 'Repo', { step: true }], ['sdf', 'SDF', { step: true }], ['msf', 'MSF', { step: true }],
      ['call_w', 'Call money (weekly)', { dash: true }]] },
    yields: { unit: '%', aria: 'Line chart of weekly government yields', series: [
      ['gsec10_w', '10-year FBIL par yield'], ['tb91_w', '91-day T-bill auction cut-off', { dash: true }]] },
    'yields-history': { unit: '%', aria: 'Line chart of historical month-end traded yields', series: [
      ['gsec10', '10-year'], ['gsec5', '5-year'], ['gsec1', '1-year']] },
    forex: { unit: 'US$ bn', aria: 'Line chart of foreign exchange reserves', series: [
      ['forex_w', 'Weekly'], ['forex_m', 'Month-end history', { muted: true, dash: true }]] },
    fx: { unit: '₹ per US$', aria: 'Line chart of rupees per US dollar', series: [
      ['usdinr_w', 'USD/INR, week-end reference rate'], ['usdinr_m', 'USD/INR, monthly average', { muted: true, dash: true }]] },
    'fx-eur': { unit: '₹ per €', aria: 'Line chart of rupees per euro', series: [
      ['eurinr_m', 'EUR/INR, monthly average']] },
    brief: { unit: 'pp', zero: true, months: 12, dots: true, shade: REPORTING_MIX,
      aria: 'Line chart of credit growth minus deposit growth over the last 12 months, latest month and 3-month average', series: [
      ['scb_gap', 'Latest month'], ['scb_gap_3m', '3-month average']] },
    spread: { unit: 'bp', zero: true, aria: 'Line chart of the call money rate minus the repo rate, daily and 5-trading-day average', series: [
      ['mmo_call_spread', 'Daily'], ['mmo_call_spread_5d', '5-trading-day average']] },
    liquidity: { unit: '₹ crore', zero: true, aria: 'Line chart of RBI net liquidity injection or absorption', series: [
      ['mmo_net_liq', 'Net liquidity (+ injection, − absorption)']] },
    pricing: { unit: '%', aria: 'Line chart of lending and deposit rates on fresh business and the outstanding book', series: [
      ['walr_fresh', 'Lending rate, fresh loans'], ['wadtdr_fresh', 'Term-deposit rate, fresh'], ['walr_out', 'Lending rate, outstanding', { dash: true }],
      ['wadtdr_out', 'Term-deposit rate, outstanding', { dash: true }], ['mclr_1y_median', '1-year MCLR, median', { muted: true }]] },
    banking: { unit: '%', zero: true, aria: 'Line chart of bank credit and deposit growth', series: [
      ['scb_credit_yoy', 'Bank credit'], ['scb_dep_yoy', 'Aggregate deposits']] },
  };

  function exploreCfg() {
    const cat = catalogRows(); if (!cat) return null;
    const c = cat.find((r) => r.id === MM.ex) || cat[0];
    return { unit: c.unit, aria: 'Line chart of ' + c.name, series: [[c.id, c.name, { step: /^Event/.test(c.freq) }]] };
  }

  const ARCHIVE_SERIES = new Set(['gsec10', 'gsec5', 'gsec1', 'forex_m', 'usdinr_m', 'eurinr_m']);
  const WSS_SERIES = new Set(['forex_w', 'gsec10_w', 'usdinr_w', 'call_w', 'tb91_w']);
  const PRICING_SERIES = new Set(['walr_fresh', 'walr_out', 'wadtdr_fresh', 'wadtdr_out', 'pricing_gap_fresh', 'mclr_1y_median']);
  const BANK_SERIES = new Set(['scb_credit', 'scb_dep', 'scb_credit_yoy', 'scb_dep_yoy', 'scb_gap', 'scb_gap_3m']);
  const CADENCE_DAYS = { Daily: 4, Weekly: 10, Monthly: 45, Quarterly: 110, 'Annual (FY)': 410 };
  const DAY_MS = 864e5;

  function sourceDueDate(id, point) {
    const year = point.d.getUTCFullYear(), month = point.d.getUTCMonth();
    const dayOfMonth = (offset, day) => new Date(Date.UTC(year, month + offset, day));
    // Allow the next expected release plus a few days for holidays and ingestion.
    if (['gdp_growth_q', 'gdp_level_q', 'gva_level_q'].includes(id)) return dayOfMonth(7, 8);
    if (id.startsWith('cpi_') && id !== 'cpi_infl_old') return dayOfMonth(2, 16);
    if (id.startsWith('iip_') && id !== 'iip_growth_old') return dayOfMonth(3, 5);
    if (id === 'mclr_1y_median') return dayOfMonth(2, 6);
    if (PRICING_SERIES.has(id) || BANK_SERIES.has(id)) return dayOfMonth(3, 6);
    if (WSS_SERIES.has(id)) return new Date(+point.d + 17 * DAY_MS);
    if (id === 'mmo_net_liq' || id === 'mmo_call' || id === 'mmo_overnight') return new Date(+point.d + 7 * DAY_MS);
    return null;
  }

  function sourceStatus(id, point) {
    if (ARCHIVE_SERIES.has(id)) return 'Historical series';
    const due = point && sourceDueDate(id, point);
    return due && parse(dashboardDay) >= due ? 'Past expected update window' : '';
  }

  const SOURCE_LABELS = {
    gdp_growth_q: 'GDP', gva_level_q: 'GVA', cpi_infl_combined: 'headline CPI', iip_index: 'IIP',
    scb_gap: 'bank credit and deposits', mmo_net_liq: 'RBI liquidity', mmo_call: 'daily call money',
    walr_fresh: 'fresh lending rates', wadtdr_fresh: 'fresh deposit rates', gsec10_w: 'FBIL 10-year yield',
    forex_w: 'weekly reserves', usdinr_w: 'weekly USD/INR',
  };
  dash.draw('freshness', (el) => {
    const I = index();
    const labels = (el.dataset.series || '').split(' ').filter((id) =>
      sourceStatus(id, I?.m.get(id)?.at(-1)) === 'Past expected update window').map((id) => SOURCE_LABELS[id]);
    el.textContent = labels.length ? 'Past expected update window: ' + labels.join(', ') + '.' : '';
  });

  function lineChart(el, cfg) {
    const I = index();
    const o = dash.data('observations');
    if (!I || !cfg) { el.replaceChildren(msg(statusText(o.status))); return; }
    // A chart with `months` shows a fixed window ending at its own latest point; others follow the range filter.
    const end = cfg.months
      ? d3.max(cfg.series, ([id]) => { const a = I.m.get(id); return a && a.length ? a[a.length - 1].d : null; }) || I.max
      : I.max;
    const t0 = cfg.months ? d3.utcDay.offset(d3.utcMonth.offset(end, -(cfg.months - 1)), -5)
      : parse(CHART_START);
    const colors = dash.colors; let ci = 0;
    const catalog = new Map((catalogRows() || []).map((series) => [series.id, series]));
    const S = [];
    for (const [id, name, opt = {}] of cfg.series) {
      if (opt.old && !MM.showOld) continue;            // discontinued series are opt-in
      const a = I.m.get(id); if (!a || !a.length) continue;
      let pts = (t0 ? a.filter((p) => p.d >= t0) : a.slice()).filter((p) => p.d <= end);
      if (opt.step) {
        const before = t0 ? a.filter((p) => p.d < t0).pop() : null;
        if (before) pts.unshift({ ...before, d: t0 });
        if (pts.length) pts.push({ ...pts[pts.length - 1], d: end });
      }
      if (!pts.length) continue;
      S.push({ id, name, pts, step: !!opt.step, dash: !!opt.dash, last: a[a.length - 1],
        cadence: CADENCE_DAYS[catalog.get(id)?.freq], status: sourceStatus(id, a.at(-1)),
        color: opt.muted ? 'var(--cds-chart-muted)' : colors[ci++ % colors.length] });
    }
    el.replaceChildren();
    if (!S.length) { el.append(msg('No observations since April 2023.')); return; }
    const root = d3.select(el);
    const lg = root.append('div').attr('class', 'mm-legend');
    const digits = cfg.digits ?? (cfg.unit === 'US$ bn' ? 1 : /^(bp|₹ crore)$/.test(cfg.unit) ? 0 : 2);
    for (const s of S) {
      const it = lg.append('span').attr('class', 'mm-lg');
      it.append('i').classed('dashed', s.dash).style('background', s.color).style('border-color', s.color);
      it.append('span').text(s.name);
      it.append('b').text(fmt(s.last.v, cfg.unit, digits));
      it.append('span').attr('class', 'mm-muted').text(s.last.label + (s.status ? ' · ' + s.status : ''));
    }
    const first = d3.min(S, (s) => s.pts[0].d);
    if (!cfg.months && first - t0 > 60 * 864e5) {
      const firstSeries = S.find((s) => s.pts[0].d.getTime() === first.getTime());
      root.append('p').attr('class', 'mm-cap').text('First reading shown: ' + firstSeries.pts[0].label + '.');
    }
    const W = Math.max(260, el.clientWidth), H = 240;
    const svg = root.append('svg').attr('width', '100%').attr('height', H).attr('viewBox', `0 0 ${W} ${H}`)
      .attr('role', 'img').attr('aria-label', cfg.aria);
    const vals = S.flatMap((s) => s.pts.map((p) => p.v));
    if (cfg.band) vals.push(...cfg.band);
    if (cfg.ref != null) vals.push(cfg.ref);
    if (cfg.zero && d3.min(vals) < 0) vals.push(0);
    const y = d3.scaleLinear().domain(d3.extent(vals)).nice();
    const ticks = y.ticks(5);
    const gGrid = svg.append('g'), gBand = svg.append('g'), gX = svg.append('g').attr('class', 'mm-axis'),
      gLines = svg.append('g'), gY = svg.append('g').attr('class', 'mm-axis'), gHover = svg.append('g');
    const yt = gY.selectAll('text').data(ticks).join('text').text((d) => fmtTick(d, cfg.unit));
    const lw = d3.max(yt.nodes(), (n) => n.getComputedTextLength()) || 28;
    const m = { l: Math.ceil(lw) + 10, r: 14, t: 8, b: 22 };
    const x0 = t0 || d3.min(S, (s) => s.pts[0].d);
    const x = d3.scaleUtc().domain([x0, cfg.months ? d3.utcDay.offset(end, 5) : end]).range([m.l, W - m.r]);
    y.range([H - m.b, m.t]);
    yt.attr('x', m.l - 8).attr('y', (d) => y(d)).attr('dy', '0.32em').attr('text-anchor', 'end');
    gGrid.selectAll('line').data(ticks).join('line').attr('x1', m.l).attr('x2', W - m.r)
      .attr('y1', (d) => y(d)).attr('y2', (d) => y(d)).style('stroke', (d) => (d === 0 ? 'var(--cds-chart-axis)' : 'var(--cds-chart-grid)'));
    if (cfg.shade) {
      const [a, b] = x.domain();
      const s0 = new Date(Math.max(a, parse(cfg.shade.from))), s1 = new Date(Math.min(b, parse(cfg.shade.to)));
      if (s1 > s0) {
        gBand.append('rect').attr('x', x(s0)).attr('width', x(s1) - x(s0)).attr('y', m.t).attr('height', H - m.t - m.b)
          .style('fill', 'var(--cds-chart-reference)').style('opacity', 0.08);
        gBand.append('text').attr('x', x(s0) + 4).attr('y', m.t + 10).text(cfg.shade.label || '');
      }
    }
    if (cfg.band) gBand.append('rect').attr('x', m.l).attr('width', W - m.l - m.r).attr('y', y(cfg.band[1]))
      .attr('height', y(cfg.band[0]) - y(cfg.band[1])).style('fill', 'var(--cds-chart-reference)').style('opacity', 0.1);
    if (cfg.ref != null) {
      gBand.append('line').attr('x1', m.l).attr('x2', W - m.r).attr('y1', y(cfg.ref)).attr('y2', y(cfg.ref))
        .style('stroke', 'var(--cds-chart-reference)').style('stroke-dasharray', '4 3');
      gBand.append('text').attr('x', W - m.r).attr('y', y(cfg.ref) - 4).attr('text-anchor', 'end').text(cfg.refLabel || '');
    }
    const nT = Math.max(2, Math.floor((W - m.l - m.r) / 90));
    const xAxis = d3.axisBottom(x).tickSizeOuter(0);
    if (cfg.months) xAxis.ticks(nT);
    else {
      // Label the shared start date so every chart visibly begins at the same point.
      const auto = x.ticks(nT).filter((d) => d - t0 > 150 * 864e5);
      const fmtAuto = x.tickFormat(nT);
      xAxis.tickValues([t0, ...auto]).tickFormat((d) => (+d === +t0 ? d3.utcFormat('%b %Y')(d) : fmtAuto(d)));
    }
    gX.attr('transform', `translate(0,${H - m.b})`).call(xAxis);
    gX.select('.domain').style('stroke', 'var(--cds-chart-axis)');
    gX.selectAll('line').style('stroke', 'var(--cds-chart-axis)');
    for (const s of S) {
      // Break the line where observations are missing for much longer than the series' usual spacing,
      // so a gap in the source is not drawn as if values moved in a straight line across it.
      let drawn = s.pts;
      if (!s.step && s.cadence) {
        drawn = [];
        s.pts.forEach((p, i) => {
          if (i && p.d - s.pts[i - 1].d > s.cadence * DAY_MS) drawn.push({ d: p.d, v: null });
          drawn.push(p);
        });
      }
      const line = d3.line().defined((p) => p.v != null).x((p) => x(p.d)).y((p) => y(p.v))
        .curve(s.step ? d3.curveStepAfter : d3.curveLinear);
      gLines.append('path').attr('d', line(drawn)).style('fill', 'none').style('stroke', s.color)
        .style('stroke-width', s.color.includes('muted') ? 1.5 : 2).style('stroke-dasharray', s.dash ? '5 3' : null)
        .style('stroke-linejoin', 'round');
      if (cfg.dots) {
        gLines.append('g').selectAll('circle').data(s.pts).join('circle').attr('cx', (p) => x(p.d)).attr('cy', (p) => y(p.v))
          .attr('r', 2.5).style('fill', s.color);
      }
      const lastPt = s.step ? s.pts[s.pts.length - 2] || s.pts[0] : s.pts[s.pts.length - 1];
      if (lastPt.d >= x.domain()[0]) gLines.append('circle').attr('cx', x(s.step ? end : lastPt.d)).attr('cy', y(lastPt.v)).attr('r', 3.5).style('fill', s.color);
    }
    // tooltip
    const tip = root.append('div').attr('class', 'mm-tip').property('hidden', true);
    const rule = gHover.append('line').attr('y1', m.t).attr('y2', H - m.b).style('stroke', 'var(--cds-chart-axis)').style('opacity', 0);
    const bis = d3.bisector((p) => p.d);
    svg.append('rect').attr('x', m.l).attr('y', m.t).attr('width', W - m.l - m.r).attr('height', H - m.t - m.b)
      .style('fill', 'transparent').style('touch-action', 'pan-y')
      .on('pointermove', (ev) => {
        const [mx] = d3.pointer(ev, svg.node());
        const dt = x.invert(mx);
        const lines = [];
        for (const s of S) {
          const real = s.step ? s.pts.slice(0, -1) : s.pts;
          let p;
          if (s.step) { const i = bis.right(real, dt) - 1; p = real[i]; }
          else {
            const day = new Date(Math.round(+dt / DAY_MS) * DAY_MS);
            p = real[bis.center(real, day)];
            const tolerance = (s.cadence || 2) * DAY_MS / 2;
            if (!p || day < real[0].d || day > real.at(-1).d || Math.abs(p.d - day) > tolerance) p = null;
          }
          if (p) lines.push([s, p]);
        }
        if (!lines.length) { tip.property('hidden', true); rule.style('opacity', 0); return; }
        tip.property('hidden', false).selectAll('*').remove();
        for (const [s, p] of lines) {
          const row = tip.append('div');
          row.append('span').style('color', s.color).text('● ');
          row.append('span').text(s.name + ': ');
          row.append('b').text(fmt(p.v, cfg.unit, digits));
          row.append('span').attr('class', 'mm-muted').text(' ' + (s.step ? 'from ' : '') + p.label);
        }
        rule.attr('x1', mx).attr('x2', mx).style('opacity', 1);
        const tw = tip.node().offsetWidth, top = svg.node().offsetTop + 6;
        tip.style('left', (mx + 14 + tw > W ? Math.max(0, mx - tw - 14) : mx + 14) + 'px').style('top', top + 'px');
      })
      .on('pointerleave', () => { tip.property('hidden', true); rule.style('opacity', 0); });
  }

  dash.draw('chart', (el) => {
    const key = el.dataset.chart;
    lineChart(el, key === 'explore' ? exploreCfg() : CH[key]);
  });

  // ---------- aligned sector breakdowns ----------
  const GVA_GROUPS = [
    ['gva_primary_level', 'Primary', ['gva_agriculture_level', 'gva_mining_level']],
    ['gva_secondary_level', 'Secondary', ['gva_manufacturing_level', 'gva_utilities_level', 'gva_construction_level']],
    ['gva_services_level', 'Services (tertiary)', ['gva_trade_level', 'gva_financial_level', 'gva_public_level']],
  ];
  const IIP_SECTORS = ['iip_mining_index', 'iip_manufacturing_index', 'iip_electricity_index', 'iip_water_index'];

  function sectorBreakdown(el, { benchmark, benchmarkLabel, unit, digits, groups, details = [] }) {
    const I = index(), catalog = catalogRows();
    if (!I || !catalog) { el.replaceChildren(msg('Loading sector data…')); return; }
    const anchor = I.m.get(benchmark)?.at(-1);
    if (!anchor) { el.replaceChildren(msg('No sector data.')); return; }
    const names = new Map(catalog.map(({ id, name }) => [id, name.replace(/^(Real GVA|IIP index) – /, '')]));
    const rowData = (id, label = names.get(id)) => ({
      label, value: I.m.get(id)?.find((point) => +point.d === +anchor.d)?.v,
    });
    const overview = groups.map(([id, title]) => rowData(id, title));
    const industries = details.map(([title, ids]) => [title, ids.map((id) => rowData(id))]);
    const rows = overview.concat(industries.flatMap(([, rows]) => rows));
    const values = [0, ...rows.flatMap(({ value }) => value == null ? [] : [value])];
    const x = d3.scaleLinear().domain(d3.extent(values)).range([0, 100]);
    // Keep the disclosure state when a resize redraws the charts.
    const open = el.querySelector('details')?.open;
    el.replaceChildren();
    const root = d3.select(el);
    root.append('p').attr('class', 'mm-cap').text(anchor.label + ' · ' + unit);
    root.append('p').attr('class', 'mm-benchmark').text(benchmarkLabel + ' ' + anchor.v.toFixed(digits));
    const status = sourceStatus(benchmark, anchor);
    if (status) root.append('p').attr('class', 'mm-cap').text(status);
    if (rows.some(({ value }) => value == null)) {
      root.append('p').attr('class', 'mm-cap').text('Some sectors have no reading for this period.');
    }
    function drawRows(parent, data) {
      for (const { label, value } of data) {
        const row = parent.append('div').attr('class', 'mm-sector-row');
        row.append('span').text(label);
        const track = row.append('span').attr('class', 'mm-sector-track').attr('aria-hidden', 'true');
        track.append('i').attr('class', 'mm-sector-zero').style('left', x(0) + '%');
        if (value != null) {
          track.append('i').attr('class', value < 0 ? 'mm-sector-bar mm-sector-negative' : 'mm-sector-bar')
            .style('left', x(Math.min(value, 0)) + '%').style('width', Math.abs(x(value) - x(0)) + '%');
        }
        row.append('b').text(value == null ? '—' : value.toFixed(digits));
      }
    }
    drawRows(root, overview);
    if (industries.length) {
      const disclosure = root.append('details').attr('class', 'mm-sector-details').property('open', !!open);
      disclosure.append('summary').text('Industry breakdown');
      for (const [title, data] of industries) {
        disclosure.append('h4').text(title);
        drawRows(disclosure, data);
      }
    }
  }

  dash.draw('sectors', (el) => sectorBreakdown(el, {
    benchmark: 'gva_level_q', benchmarkLabel: 'Total real GVA', unit: '₹ lakh crore', digits: 2, groups: GVA_GROUPS,
    details: GVA_GROUPS.map(([, title, ids]) => [title, ids]),
  }));
  dash.draw('iip-sectors', (el) => sectorBreakdown(el, {
    benchmark: 'iip_index', benchmarkLabel: 'General IIP', unit: 'Index (2022-23 = 100)', digits: 1,
    groups: IIP_SECTORS.map((id) => [id]),
  }));

  // ---------- KPI tiles and takeaway ----------
  // Changes are shown neutrally: a macro move is not good or bad for every bank, so tiles carry no colour judgement.
  const K = {
    gdp_growth_q: { unit: '%', p: 1 }, cpi_infl_combined: { unit: '%', p: 2 }, iip_index: { unit: IIP_UNIT, p: 1 },
    repo: { unit: '%', p: 2 }, gsec10_w: { unit: '%', p: 2 }, forex_w: { unit: 'US$ bn', p: 1 },
    scb_credit_yoy: { unit: '%', p: 1 }, scb_dep_yoy: { unit: '%', p: 1 }, usdinr_w: { unit: '₹ per US$', p: 2 },
    scb_gap: { unit: 'pp', p: 2 }, scb_gap_3m: { unit: 'pp', p: 2 },
    mmo_call: { unit: '%', p: 2 }, mmo_call_spread: { unit: 'bp', p: 0 },
    mmo_call_spread_5d: { unit: 'bp', p: 0 }, mmo_net_liq: { unit: '₹ crore', p: 0, abs: true },
    walr_fresh: { unit: '%', p: 2 }, wadtdr_fresh: { unit: '%', p: 2 }, walr_out: { unit: '%', p: 2 }, wadtdr_out: { unit: '%', p: 2 },
    mclr_1y_median: { unit: '%', p: 2 }, pricing_gap_fresh: { unit: 'pp', p: 2 },
  };
  function pendingSpread() {
    return (dash.data('observations').meta || []).find((item) => item.label === 'Repo spread pending from')?.value;
  }
  dash.draw('funding-status', (el) => {
    el.textContent = pendingSpread() ? 'Call–repo spreads are pending RBI rate verification.' : '';
  });
  function latest(k) { const L = dash.data('latest'); return L.status === 'ok' ? L.data.find((r) => r.series === k) : null; }
  dash.draw('kpi', (el) => {
    const k = el.dataset.k, part = el.dataset.part, c = K[k];
    const r = latest(k);
    el.classList.remove('is-flat');
    if ((k === 'mmo_call_spread' || k === 'mmo_call_spread_5d') && pendingSpread()) {
      el.textContent = '—';
      return;
    }
    if (!r) { el.textContent = statusText(dash.data('latest').status); return; }
    if (part === 'value') el.textContent = c.unit === 'US$ bn' ? r.value.toFixed(c.p) : fmt(c.abs ? Math.abs(r.value) : r.value, c.unit, c.p);
    else if (part === 'label') el.textContent = r.label;
    else if (part === 'change') {
      if (r.change == null) { el.textContent = '—'; return; }
      const d = r.change, sign = d > 0 ? '+' : d < 0 ? MINUS : '±';
      const a = Math.abs(d).toFixed(c.p);
      const amt = c.unit === '%' || c.unit === 'pp' ? a + ' pp' : c.unit === 'bp' ? a + ' bp' : c.unit === IIP_UNIT ? a + ' index points' : c.unit === '₹ crore'
        ? '₹' + Math.abs(d).toLocaleString('en-IN', { maximumFractionDigits: c.p }) + ' crore' : c.unit === 'US$ bn' ? '$' + a + ' bn' : '₹' + a;
      el.textContent = (k === 'repo' ? sign + amt + ', from ' + fmt(r.prev, '%', 2) + ' on ' : sign + amt + ' vs ') + r.prev_label;
      el.classList.add('is-flat');
    }
  });
  dash.draw('repo-move', (el) => {
    const r = latest('repo');
    if (!r || r.change == null) { el.textContent = '—'; return; }
    const bp = Math.round(Math.abs(r.change) * 100);
    el.textContent = bp + ' bp ' + (r.change > 0 ? 'increase' : 'cut');
  });
  // CPI is described against the 2–6% tolerance band around the 4% target, which is the actual limit in law.
  dash.draw('vs-band', (el) => {
    const r = latest('cpi_infl_combined');
    const LOWER = 2, UPPER = 6, TARGET = 4;
    if (!r || r.value == null) { el.textContent = '—'; return; }
    el.textContent = r.value > UPPER ? `above the ${UPPER}% upper tolerance level`
      : r.value < LOWER ? `below the ${LOWER}% lower tolerance level`
      : `within the ${LOWER}–${UPPER}% tolerance band around the ${TARGET}% target`;
  });

  // ---------- banking brief ----------
  const ORD = (n) => n + (n % 100 >= 11 && n % 100 <= 13 ? 'th' : ['th', 'st', 'nd', 'rd'][n % 10] || 'th');
  // "widened" / "narrowed" for the latest month, with the run length when the move continues a streak.
  dash.draw('direction', (el) => {
    const I = index();
    const rows = I ? (I.raw.get(el.dataset.k) || []).slice().sort((a, b) => (a.period < b.period ? -1 : 1)) : [];
    if (rows.length < 2) { el.textContent = '—'; return; }
    const step = (i) => Math.sign(+rows[i].value - +rows[i - 1].value);
    const dir = step(rows.length - 1);
    if (dir === 0) { el.textContent = 'was unchanged'; return; }
    let run = 1;
    for (let i = rows.length - 2; i >= 1 && step(i) === dir; i--) run++;
    el.textContent = (dir > 0 ? 'widened' : 'narrowed') + (run > 1 ? ` for the ${ORD(run)} month in a row` : '');
  });

  // Net liquidity is shown as an amount plus a word, so a negative number is never misread.
  dash.draw('liq-dir', (el) => {
    const r = latest('mmo_net_liq');
    el.textContent = !r || r.value == null ? '—' : r.value < 0 ? 'Net absorption by RBI' : r.value > 0 ? 'Net injection by RBI' : 'Neutral';
  });

  dash.calc('inccd', {
    inputs: ['observations'],
    title: 'Incremental credit–deposit ratio: latest and same month last year',
    description: 'Latest month of the financial-year-to-date ratio, the same month a year earlier, and whether the ratio is available for the latest month of bank data.',
    fn: (observations) => {
      const ratio = observations.filter((r) => r.series === 'scb_inc_cd_fytd');
      const credit = observations.filter((r) => r.series === 'scb_credit').sort((a, b) => (a.period < b.period ? -1 : 1));
      const latestBank = credit[credit.length - 1];
      if (!latestBank) return [];
      const at = (period) => ratio.find((r) => r.period === period);
      const cur = at(latestBank.period);
      const yearAgo = at(`${+latestBank.period.slice(0, 4) - 1}${latestBank.period.slice(4)}`);
      const one = (v) => (v == null ? null : Math.round(+v * 10) / 10);
      return [{
        series: 'scb_inc_cd_fytd', period: latestBank.period, label: latestBank.label, available: !!cur,
        value: cur ? one(cur.value) : null,
        year_ago: yearAgo ? one(yearAgo.value) : null, year_ago_label: yearAgo ? yearAgo.label : null,
      }];
    },
  });
  const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
  function inccd() { const d = dash.data('inccd'); return d.status === 'ok' && d.data && d.data[0] ? d.data[0] : null; }
  dash.draw('inccd-state', () => {
    const r = inccd();
    const ok = !!(r && r.available);
    for (const el of document.querySelectorAll('[data-switch="inccd-ok"]')) if (el.hidden === ok) el.hidden = !ok;
    for (const el of document.querySelectorAll('[data-switch="inccd-missing"]')) { const hide = !r || ok; if (el.hidden !== hide) el.hidden = hide; }
  });
  dash.draw('inccd', (el) => {
    const r = inccd(), part = el.dataset.part;
    if (!r) { el.textContent = '—'; return; }
    const monthEnd = `end-${MONTHS[+r.period.slice(5, 7) - 1]} ${r.period.slice(0, 4)}`;
    if (part === 'value') el.textContent = r.value == null ? '—' : r.value.toFixed(1) + '%';
    else if (part === 'per100') el.textContent = r.value == null ? '—' : r.value.toFixed(1);
    else if (part === 'label') el.textContent = monthEnd;
    else if (part === 'pending_label') el.textContent = r.label;
    else if (part === 'year_ago') el.textContent = r.year_ago == null ? '—' : r.year_ago.toFixed(1) + '%';
    else if (part === 'year_ago_label') el.textContent = r.year_ago_label ? 'end-March to end-' + MONTHS[+r.period.slice(5, 7) - 1] + ' ' + (+r.period.slice(0, 4) - 1) : '—';
  });

  // ---------- build / fetch dates (from the data files' meta) ----------
  dash.draw('built', (el) => {
    const id = el.dataset.part === 'snap' ? 'snapshot' : 'observations';
    const label = id === 'snapshot' ? 'Fetched (UTC)' : 'Built (UTC)';
    const d = dash.data(id);
    const m = (d.meta || []).find((x) => x.label === label);
    const t = m && m.value ? new Date(m.value) : null;
    el.textContent = t && !isNaN(t) ? d3.utcFormat('%-d %b %Y')(t) : '—';
  });

  // ---------- policy history vs rbi.org.in (flag a pending history update) ----------
  function policyMismatches() {
    const s = dash.data('snapshot'), I = index();
    if (s.status !== 'ok' || !I) return null;
    const out = [];
    for (const sid of POLICY_CORRIDOR) {
      const item = POLICY_NAMES.get(sid);
      const row = s.data.find((r) => r.group === 'Policy rates' && r.item === item);
      const live = rateNumber(row?.value);
      if (!row?.as_of || !Number.isFinite(live)) continue;
      const hist = I.raw.get(sid)?.findLast((r) => r.date && r.date <= row.as_of);
      const effective = rateNumber(hist?.value);
      if (Number.isFinite(effective) && Math.abs(live - effective) > 1e-9) {
        out.push({ item, live, hist: effective, date: hist.label });
      }
    }
    return out;
  }
  // Empty drawing that shows or hides the stored warning paragraph.
  dash.draw('policy-check', () => {
    const m = policyMismatches();
    const hide = !(m && m.length);
    for (const el of document.querySelectorAll('[data-policy-flag]')) if (el.hidden !== hide) el.hidden = hide;
  });
  dash.draw('policy-diff', (el) => {
    const m = policyMismatches();
    el.textContent = m && m.length
      ? m.map((x) => `${x.item} ${x.live.toFixed(2)}% on rbi.org.in vs ${x.hist.toFixed(2)}% in the history (last change ${x.date})`).join('; ')
      : '—';
  });
  dash.draw('scheduled-policy', (el) => {
    const o = dash.data('observations');
    const pending = o.status === 'ok' ? o.data.filter(isScheduled).sort((a, b) => a.date.localeCompare(b.date)) : [];
    el.textContent = pending.length
      ? 'Scheduled policy changes: ' + pending.map((r) => `${POLICY_NAMES.get(r.series)} ${fmt(r.value, '%')} from ${r.label}`).join('; ')
      : '';
  });

  // ---------- snapshot ----------
  dash.draw('snap', (tb) => {
    const s = dash.data('snapshot');
    tb.replaceChildren();
    if (s.status !== 'ok') { const tr = tb.insertRow(); const td = tr.insertCell(); td.colSpan = 4; td.textContent = statusText(s.status); return; }
    for (const r of s.data) {
      const tr = tb.insertRow(); tr.dataset.key = encodeURIComponent(r.item);
      tr.insertCell().textContent = r.group; tr.insertCell().textContent = r.item;
      // A missing value must show as a dash, never as 0 (+null === 0 in JavaScript).
      const num = rateNumber(r.value);
      const v = tr.insertCell(); v.className = 'r';
      v.textContent = Number.isFinite(num) ? num.toFixed(r.unit === '₹' ? 4 : 2) + (String(r.unit || '').startsWith('%') ? '%' : '') : '—';
      tr.insertCell().textContent = r.as_of;
    }
  });

  // ---------- explorer ----------
  dash.draw('picker', (sel) => {
    const cat = catalogRows();
    sel.replaceChildren();
    if (!cat) { sel.append(new Option('Loading series…', '')); return; }
    const groups = d3.group(cat, (r) => r.group);
    for (const [g, rows] of groups) {
      const og = document.createElement('optgroup'); og.label = g;
      for (const r of rows) og.append(new Option(r.name, r.id));
      sel.append(og);
    }
    sel.value = MM.ex;
    sel.onchange = () => { MM.ex = sel.value; dash.draw('chart'); dash.draw('ex'); dash.draw('ex-rows'); };
  });
  dash.draw('ex', (el) => {
    const cat = catalogRows();
    if (!cat) { el.textContent = '—'; return; }
    const c = cat.find((r) => r.id === MM.ex) || cat[0];
    const part = el.dataset.part;
    if (part === 'coverage') {
      const last = index()?.raw.get(c.id)?.at(-1);
      const status = sourceStatus(c.id, index()?.m.get(c.id)?.at(-1));
      el.textContent = c.obs ? `${c.first} to ${last ? periodLabel(last) : c.last} · ${c.obs} observations` : 'No verified observations';
      if (status) el.textContent += ' · ' + status;
    }
    else if (part === 'link') {
      el.replaceChildren();
      if (/^https:\/\//.test(c.source_url || '')) { const a = document.createElement('a'); a.href = c.source_url; a.target = '_blank'; a.rel = 'noopener'; a.textContent = c.source_url; el.append(a); }
      else el.textContent = '—';
    } else el.textContent = c[part] || '—';
  });
  dash.draw('ex-rows', (tb) => {
    const I = index(), cat = catalogRows();
    tb.replaceChildren();
    if (!I || !cat) return;
    const c = cat.find((r) => r.id === MM.ex) || cat[0];
    const rows = (I.raw.get(c.id) || []).slice().sort((a, b) => ((a.date || a.period) < (b.date || b.period) ? 1 : -1)).slice(0, 12);
    for (const r of rows) {
      const tr = tb.insertRow(); tr.dataset.key = encodeURIComponent(r.series) + ',' + encodeURIComponent(r.period);
      tr.insertCell().textContent = periodLabel(r);
      const v = tr.insertCell(); v.className = 'r'; v.textContent = String(+r.value);
    }
  });


  // ---------- controls (listen; set aria-pressed / hidden only) ----------
  for (const cb of document.querySelectorAll('#show-old')) {
    cb.checked = !!MM.showOld;
    cb.addEventListener('change', () => { MM.showOld = cb.checked; dash.draw('chart'); });
  }
  // ---------- tabs: Banking brief | Macro summary ----------
  // Each tab has its own link (#brief, #macro); a link to any element inside a tab opens that tab.
  const TABS = ['brief', 'macro'];
  function showTab(name) {
    for (const p of document.querySelectorAll('[data-tab]')) { const hide = p.dataset.tab !== name; if (p.hidden !== hide) p.hidden = hide; }
    for (const b of document.querySelectorAll('[data-tab-btn]')) {
      const on = b.dataset.tabBtn === name;
      b.setAttribute('aria-selected', String(on));
      b.setAttribute('tabindex', on ? '0' : '-1');
    }
  }
  function route() {
    const hash = typeof location !== 'undefined' ? location.hash || '' : '';
    const id = decodeURIComponent(hash.slice(1));
    if (TABS.includes(id)) { showTab(id); return; }
    const target = id ? document.getElementById(id) : null;
    const panel = target && target.closest('[data-tab]');
    showTab(panel ? panel.dataset.tab : 'brief');
    if (panel) requestAnimationFrame(() => target.scrollIntoView());
  }
  const tabButtons = [...document.querySelectorAll('[data-tab-btn]')];
  tabButtons.forEach((b, i) => {
    b.addEventListener('click', () => {
      showTab(b.dataset.tabBtn);
      if (dash.setLink) dash.setLink(b.dataset.tabBtn);
      try { if (location.hash !== '#' + b.dataset.tabBtn) history.replaceState(null, '', '#' + b.dataset.tabBtn); } catch (e) { /* sandboxed */ }
    });
    b.addEventListener('keydown', (e) => {
      if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return;
      const next = tabButtons[(i + (e.key === 'ArrowRight' ? 1 : tabButtons.length - 1)) % tabButtons.length];
      next.focus(); next.click();
    });
  });
  window.addEventListener('hashchange', route);
  route();
  // Print both tabs, then restore the one in view.
  window.addEventListener('beforeprint', () => { for (const p of document.querySelectorAll('[data-tab]')) p.hidden = false; });
  window.addEventListener('afterprint', route);
})();
