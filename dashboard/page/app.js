// India Macro Monitor — drawings for the dashboard page.
(function () {
  const MM = (window.MM = window.MM || { range: '5y', topic: 'all', ex: 'cpi_infl_combined' });
  const parse = d3.utcParse('%Y-%m-%d');
  const MINUS = '−';
  const TOPIC = { 'Growth': 'growth', 'GVA by sector': 'growth', 'Prices': 'prices', 'Industry': 'industry',
    'Monetary policy': 'policy', 'Rates & yields': 'rates', 'External': 'external', 'Banking': 'banking' };

  // ---------- latest value per series (a calc, so every tile can be traced) ----------
  dash.calc('latest', {
    inputs: ['observations'],
    title: 'Latest value per series',
    description: 'Last and previous observation of each series, rounded as shown on the page; change = last minus previous.',
    fn: (observations) => {
      const places = { gdp_growth_q: 1, gva_growth_q: 1, iip_growth: 1, forex_w: 1, forex_m: 1, scb_credit_yoy: 1, scb_dep_yoy: 1 };
      const bySeries = {};
      for (const r of observations) (bySeries[r.series] = bySeries[r.series] || []).push(r);
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
    if (unit === 'US$ bn') return sign + '$' + (+Math.abs(v)).toFixed(p ?? 1) + ' bn';
    if (unit && unit.startsWith('₹ per')) return sign + '₹' + s;
    if (unit === '₹ lakh crore') return sign + '₹' + (+Math.abs(v)).toFixed(p ?? 1) + ' lakh cr';
    return sign + s;
  }
  function fmtTick(v, unit) {
    if (unit === '%' || unit === '% p.a.') return d3.format('~r')(+v.toFixed(2)) + '%';
    if (unit === 'US$ bn') return '$' + d3.format(',~r')(v);
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
      if (!r.date) continue;
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
    growth: { unit: '%', zero: true, aria: 'Line chart of real GDP and GVA growth by quarter', series: [
      ['gdp_growth_q', 'Real GDP, 2022-23 base'], ['gva_growth_q', 'Real GVA, 2022-23 base'],
      ['gdp_growth_q_old', 'Real GDP, old 2011-12 base', { muted: true, dash: true }]] },
    cpi: { unit: '%', zero: true, band: [2, 6], ref: 4, refLabel: '4% target', aria: 'Line chart of CPI inflation with the 2 to 6 percent band', series: [
      ['cpi_infl_old', 'Headline, 2012 base', { muted: true }], ['cpi_infl_combined', 'Headline, 2024 base'],
      ['cfpi_old', 'Food (CFPI), 2012 base', { muted: true, dash: true }], ['cpi_food', 'Food & beverages, 2024 base', { dash: true }]] },
    iip: { unit: '%', zero: true, aria: 'Line chart of industrial production growth', series: [
      ['iip_growth_old', 'IIP, old 2011-12 base', { muted: true }], ['iip_growth', 'IIP general, 2022-23 base'],
      ['iip_manufacturing', 'Manufacturing, 2022-23 base', { dash: true }]] },
    policy: { unit: '%', aria: 'Step chart of repo, SDF and MSF rates with the call money rate', series: [
      ['repo', 'Repo', { step: true }], ['sdf', 'SDF', { step: true }], ['msf', 'MSF', { step: true }],
      ['call_w', 'Call money (weekly)', { dash: true }]] },
    yields: { unit: '%', aria: 'Line chart of government bond yields', series: [
      ['gsec10', '10Y month-end'], ['gsec10_w', '10Y FBIL weekly'], ['gsec5', '5Y month-end'], ['gsec1', '1Y month-end'],
      ['tb91_w', '91-day T-bill', { dash: true }]] },
    forex: { unit: 'US$ bn', aria: 'Line chart of foreign exchange reserves', series: [['forex_m', 'Month-end'], ['forex_w', 'Weekly']] },
    fx: { unit: '₹ per US$', aria: 'Line chart of rupee exchange rates', series: [
      ['usdinr_m', 'USD/INR monthly average'], ['usdinr_w', 'USD/INR weekly'], ['eurinr_m', 'EUR/INR monthly average', { muted: true }]] },
    banking: { unit: '%', zero: true, aria: 'Line chart of bank credit and deposit growth', series: [
      ['scb_credit_yoy', 'Bank credit'], ['scb_dep_yoy', 'Aggregate deposits']] },
  };

  function exploreCfg() {
    const cat = catalogRows(); if (!cat) return null;
    const c = cat.find((r) => r.id === MM.ex) || cat[0];
    return { unit: c.unit, aria: 'Line chart of ' + c.name, series: [[c.id, c.name, { step: /^Event/.test(c.freq) }]] };
  }

  function lineChart(el, cfg) {
    const I = index();
    const o = dash.data('observations');
    if (!I || !cfg) { el.replaceChildren(msg(statusText(o.status))); return; }
    const yrs = { '2y': 2, '5y': 5, '10y': 10 }[MM.range];
    const t0 = yrs ? d3.utcYear.offset(I.max, -yrs) : null;
    const colors = dash.colors; let ci = 0;
    const S = [];
    for (const [id, name, opt = {}] of cfg.series) {
      const a = I.m.get(id); if (!a || !a.length) continue;
      let pts = t0 ? a.filter((p) => p.d >= t0) : a.slice();
      if (opt.step) {
        const before = t0 ? a.filter((p) => p.d < t0).pop() : null;
        if (before) pts.unshift({ ...before, d: t0 });
        if (pts.length) pts.push({ ...pts[pts.length - 1], d: I.max });
      }
      if (!pts.length) continue;
      S.push({ id, name, pts, step: !!opt.step, dash: !!opt.dash, last: a[a.length - 1],
        color: opt.muted ? 'var(--cds-chart-muted)' : colors[ci++ % colors.length] });
    }
    el.replaceChildren();
    if (!S.length) { el.append(msg('No observations in this period. Choose a longer range.')); return; }
    const root = d3.select(el);
    const lg = root.append('div').attr('class', 'mm-legend');
    for (const s of S) {
      const it = lg.append('span').attr('class', 'mm-lg');
      it.append('i').classed('dashed', s.dash).style('background', s.color).style('border-color', s.color);
      it.append('span').text(s.name);
      it.append('b').text(fmt(s.last.v, cfg.unit, cfg.unit === 'US$ bn' ? 1 : 2));
      it.append('span').attr('class', 'mm-muted').text(s.last.label);
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
    const x = d3.scaleUtc().domain([x0, I.max]).range([m.l, W - m.r]);
    y.range([H - m.b, m.t]);
    yt.attr('x', m.l - 8).attr('y', (d) => y(d)).attr('dy', '0.32em').attr('text-anchor', 'end');
    gGrid.selectAll('line').data(ticks).join('line').attr('x1', m.l).attr('x2', W - m.r)
      .attr('y1', (d) => y(d)).attr('y2', (d) => y(d)).style('stroke', (d) => (d === 0 ? 'var(--cds-chart-axis)' : 'var(--cds-chart-grid)'));
    if (cfg.band) gBand.append('rect').attr('x', m.l).attr('width', W - m.l - m.r).attr('y', y(cfg.band[1]))
      .attr('height', y(cfg.band[0]) - y(cfg.band[1])).style('fill', 'var(--cds-chart-reference)').style('opacity', 0.1);
    if (cfg.ref != null) {
      gBand.append('line').attr('x1', m.l).attr('x2', W - m.r).attr('y1', y(cfg.ref)).attr('y2', y(cfg.ref))
        .style('stroke', 'var(--cds-chart-reference)').style('stroke-dasharray', '4 3');
      gBand.append('text').attr('x', W - m.r).attr('y', y(cfg.ref) - 4).attr('text-anchor', 'end').text(cfg.refLabel || '');
    }
    const nT = Math.max(2, Math.floor((W - m.l - m.r) / 90));
    gX.attr('transform', `translate(0,${H - m.b})`).call(d3.axisBottom(x).ticks(nT).tickSizeOuter(0));
    gX.select('.domain').style('stroke', 'var(--cds-chart-axis)');
    gX.selectAll('line').style('stroke', 'var(--cds-chart-axis)');
    for (const s of S) {
      const line = d3.line().x((p) => x(p.d)).y((p) => y(p.v)).curve(s.step ? d3.curveStepAfter : d3.curveLinear);
      gLines.append('path').attr('d', line(s.pts)).style('fill', 'none').style('stroke', s.color)
        .style('stroke-width', s.color.includes('muted') ? 1.5 : 2).style('stroke-dasharray', s.dash ? '5 3' : null)
        .style('stroke-linejoin', 'round');
      const end = s.step ? s.pts[s.pts.length - 2] || s.pts[0] : s.pts[s.pts.length - 1];
      if (end.d >= x.domain()[0]) gLines.append('circle').attr('cx', x(s.step ? I.max : end.d)).attr('cy', y(end.v)).attr('r', 3).style('fill', s.color);
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
          if (s.step) { const i = bis.right(real, dt) - 1; p = real[Math.max(0, i)]; }
          else {
            const i = bis.center(real, dt); p = real[i];
            if (!p || Math.abs(p.d - dt) > 100 * 864e5) p = null;
          }
          if (p) lines.push([s, p]);
        }
        if (!lines.length) { tip.property('hidden', true); rule.style('opacity', 0); return; }
        tip.property('hidden', false).selectAll('*').remove();
        for (const [s, p] of lines) {
          const row = tip.append('div');
          row.append('span').style('color', s.color).text('● ');
          row.append('span').text(s.name + ': ');
          row.append('b').text(fmt(p.v, cfg.unit, cfg.unit === 'US$ bn' ? 1 : 2));
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

  // ---------- GVA by sector bars ----------
  const SECT = [['gva_agriculture', 'Agriculture'], ['gva_mining', 'Mining'], ['gva_manufacturing', 'Manufacturing'],
    ['gva_utilities', 'Electricity, gas, water'], ['gva_construction', 'Construction'], ['gva_trade', 'Trade, hotels, transport'],
    ['gva_financial', 'Financial & real estate'], ['gva_public', 'Public admin & other'], ['gva_growth_q', 'Total GVA']];
  dash.draw('sectors', (el) => {
    const I = index();
    if (!I) { el.replaceChildren(msg(statusText(dash.data('observations').status))); return; }
    const rows = SECT.map(([id, name]) => { const a = I.m.get(id) || []; const p = a[a.length - 1]; return p ? { id, name, v: p.v, label: p.label } : null; })
      .filter(Boolean).sort((a, b) => b.v - a.v);
    el.replaceChildren();
    if (!rows.length) { el.append(msg('No sector data.')); return; }
    const root = d3.select(el);
    root.append('p').attr('class', 'mm-cap').text('Real GVA growth, y/y, ' + rows[0].label);
    const W = Math.max(260, el.clientWidth), bh = 22, H = rows.length * bh + 10;
    const svg = root.append('svg').attr('width', '100%').attr('height', H).attr('viewBox', `0 0 ${W} ${H}`)
      .attr('role', 'img').attr('aria-label', 'Bar chart of GVA growth by sector in the latest quarter');
    const lab = svg.append('g').selectAll('text').data(rows).join('text').text((d) => d.name);
    const lw = d3.max(lab.nodes(), (n) => n.getComputedTextLength()) || 80;
    const vlab = svg.append('g').selectAll('text').data(rows).join('text').text((d) => fmt(d.v, '%', 1));
    const vw = d3.max(vlab.nodes(), (n) => n.getComputedTextLength()) || 30;
    const ext = d3.extent([0, ...rows.map((d) => d.v)]);
    const x = d3.scaleLinear().domain(ext).range([lw + 12 + (ext[0] < 0 ? vw + 6 : 0), W - vw - 8]);
    const yy = (i) => 4 + i * bh;
    lab.attr('x', lw).attr('y', (d, i) => yy(i) + bh / 2 - 2).attr('dy', '0.32em').attr('text-anchor', 'end')
      .style('font-weight', (d) => (d.id === 'gva_growth_q' ? 600 : null));
    svg.append('g').selectAll('rect').data(rows).join('rect')
      .attr('x', (d) => x(Math.min(0, d.v))).attr('width', (d) => Math.abs(x(d.v) - x(0)))
      .attr('y', (d, i) => yy(i) + 3).attr('height', bh - 8).attr('rx', 2)
      .style('fill', (d) => (d.id === 'gva_growth_q' ? 'var(--color-fg)' : d.v < 0 ? 'var(--cds-chart-status-critical)' : dash.colors[0]));
    vlab.attr('x', (d) => (d.v < 0 ? x(d.v) - 4 : x(d.v) + 4)).attr('y', (d, i) => yy(i) + bh / 2 - 2).attr('dy', '0.32em')
      .attr('text-anchor', (d) => (d.v < 0 ? 'end' : 'start'));
    svg.append('line').attr('x1', x(0)).attr('x2', x(0)).attr('y1', 0).attr('y2', H).style('stroke', 'var(--cds-chart-axis)');
  });

  // ---------- KPI tiles and takeaway ----------
  const K = {
    gdp_growth_q: { unit: '%', p: 1, good: 'up' }, cpi_infl_combined: { unit: '%', p: 2, good: 'down' },
    iip_growth: { unit: '%', p: 1, good: 'up' }, repo: { unit: '%', p: 2, good: null },
    gsec10_w: { unit: '%', p: 2, good: 'down' }, forex_w: { unit: 'US$ bn', p: 1, good: 'up' },
    scb_credit_yoy: { unit: '%', p: 1, good: 'up' }, usdinr_w: { unit: '₹ per US$', p: 2, good: 'down' },
  };
  function latest(k) { const L = dash.data('latest'); return L.status === 'ok' ? L.data.find((r) => r.series === k) : null; }
  dash.draw('kpi', (el) => {
    const k = el.dataset.k, part = el.dataset.part, c = K[k];
    const r = latest(k);
    el.classList.remove('is-good', 'is-bad', 'is-flat');
    if (!r) { el.textContent = statusText(dash.data('latest').status); return; }
    if (part === 'value') el.textContent = c.unit === 'US$ bn' ? r.value.toFixed(c.p) : fmt(r.value, c.unit, c.p);
    else if (part === 'label') el.textContent = r.label;
    else if (part === 'change') {
      if (r.change == null) { el.textContent = '—'; return; }
      const d = r.change, sign = d > 0 ? '+' : d < 0 ? MINUS : '±';
      const a = Math.abs(d).toFixed(c.p);
      const amt = c.unit === '%' ? a + ' pp' : c.unit === 'US$ bn' ? '$' + a + ' bn' : '₹' + a;
      el.textContent = (k === 'repo' ? sign + amt + ', from ' + fmt(r.prev, '%', 2) + ' on ' : sign + amt + ' vs ') + r.prev_label;
      if (d === 0 || !c.good) el.classList.add('is-flat');
      else el.classList.add((d > 0) === (c.good === 'up') ? 'is-good' : 'is-bad');
    }
  });
  dash.draw('repo-move', (el) => {
    const r = latest('repo');
    if (!r || r.change == null) { el.textContent = '—'; return; }
    const bp = Math.round(Math.abs(r.change) * 100);
    el.textContent = bp + ' bp ' + (r.change > 0 ? 'increase' : 'cut');
  });
  dash.draw('vs-target', (el) => {
    const r = latest('cpi_infl_combined');
    const TARGET = 4;
    if (!r) { el.textContent = '—'; return; }
    el.textContent = r.value > TARGET ? 'above' : r.value < TARGET ? 'below' : 'at';
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
  const POLICY_PAIRS = [['repo', 'Policy Repo Rate'], ['sdf', 'Standing Deposit Facility Rate'], ['msf', 'Marginal Standing Facility Rate']];
  function policyMismatches() {
    const s = dash.data('snapshot'), L = dash.data('latest');
    if (s.status !== 'ok' || L.status !== 'ok') return null;
    const out = [];
    for (const [sid, item] of POLICY_PAIRS) {
      const row = s.data.find((r) => r.group === 'Policy rates' && r.item === item);
      const live = row && row.value != null && row.value !== '' ? Number(row.value) : NaN;
      const hist = L.data.find((r) => r.series === sid);
      if (!Number.isFinite(live) || !hist || hist.value == null) continue;
      if (Math.abs(live - hist.value) > 1e-9) out.push({ item, live, hist: hist.value, date: hist.label });
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

  // ---------- snapshot ----------
  dash.draw('snap', (tb) => {
    const s = dash.data('snapshot');
    tb.replaceChildren();
    if (s.status !== 'ok') { const tr = tb.insertRow(); const td = tr.insertCell(); td.colSpan = 4; td.textContent = statusText(s.status); return; }
    for (const r of s.data) {
      const tr = tb.insertRow(); tr.dataset.key = encodeURIComponent(r.item);
      tr.insertCell().textContent = r.group; tr.insertCell().textContent = r.item;
      // A missing value must show as a dash, never as 0 (+null === 0 in JavaScript).
      const num = r.value == null || r.value === '' ? NaN : Number(r.value);
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
    if (part === 'coverage') el.textContent = `${c.first} to ${c.last} · ${c.obs} observations`;
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
      tr.insertCell().textContent = r.label;
      const v = tr.insertCell(); v.className = 'r'; v.textContent = String(+r.value);
    }
  });

  // ---------- catalog ----------
  dash.draw('catalog', (tb) => {
    const cat = catalogRows();
    tb.replaceChildren();
    if (!cat) { const tr = tb.insertRow(); const td = tr.insertCell(); td.colSpan = 8; td.textContent = statusText(dash.data('catalog').status); return; }
    for (const r of cat) {
      if (MM.topic !== 'all' && TOPIC[r.group] !== MM.topic) continue;
      const tr = tb.insertRow(); tr.dataset.key = encodeURIComponent(r.id);
      const b = document.createElement('button'); b.type = 'button'; b.className = 'mm-row-btn'; b.textContent = r.name;
      b.onclick = () => {
        MM.ex = r.id; dash.draw('picker'); dash.draw('chart'); dash.draw('ex'); dash.draw('ex-rows');
        document.getElementById('explore')?.scrollIntoView({ behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' });
      };
      tr.insertCell().append(b);
      tr.insertCell().textContent = r.group; tr.insertCell().textContent = r.freq; tr.insertCell().textContent = r.unit;
      tr.insertCell().textContent = r.first; tr.insertCell().textContent = r.last;
      const v = tr.insertCell(); v.className = 'r'; v.textContent = String(+r.latest);
      tr.insertCell().textContent = r.source;
    }
  });

  // ---------- controls (listen; set aria-pressed / hidden only) ----------
  for (const b of document.querySelectorAll('[data-topic-btn]')) {
    b.addEventListener('click', () => {
      MM.topic = b.dataset.topicBtn;
      for (const o of document.querySelectorAll('[data-topic-btn]')) o.setAttribute('aria-pressed', String(o === b));
      for (const s of document.querySelectorAll('.mm-sec[data-topic]')) s.hidden = MM.topic !== 'all' && s.dataset.topic !== MM.topic;
      dash.draw('catalog');
    });
  }
  for (const b of document.querySelectorAll('[data-range-btn]')) {
    b.addEventListener('click', () => {
      MM.range = b.dataset.rangeBtn;
      for (const o of document.querySelectorAll('[data-range-btn]')) o.setAttribute('aria-pressed', String(o === b));
      dash.draw('chart');
    });
  }
  window.addEventListener('beforeprint', () => { for (const s of document.querySelectorAll('.mm-sec[data-topic]')) s.hidden = false; });
})();
