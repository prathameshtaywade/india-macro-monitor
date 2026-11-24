// Offline render checks for dashboard/page/app.js, with tiny stand-ins for d3, dash and the DOM.
// Run: node tests/test_render.js
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const assert = require('assert');

const src = fs.readFileSync(path.join(__dirname, '..', 'dashboard', 'page', 'app.js'), 'utf8');

function cell() { return { textContent: '', className: '', dataset: {} }; }
function tbody() {
  const rows = [];
  return {
    rows,
    replaceChildren() { rows.length = 0; },
    insertRow() { const r = { cells: [], dataset: {}, insertCell() { const c = cell(); this.cells.push(c); return c; } }; rows.push(r); return r; },
  };
}

function load(datasets, now = '2026-11-24T12:00:00Z') {
  const draws = {}, calcs = {};
  const flags = [{ hidden: true }];
  const switches = { '[data-switch="inccd-ok"]': [{ hidden: false }], '[data-switch="inccd-missing"]': [{ hidden: true }] };
  const dash = {
    colors: ['a', 'b', 'c'],
    calc(id, spec) { calcs[id] = spec; },
    draw(name, fn) { if (fn) draws[name] = fn; },
    data(id) {
      if (datasets[id]) return datasets[id];
      const c = calcs[id];
      const inputs = c.inputs.map((i) => datasets[i]);
      return { status: 'ok', data: c.fn(...inputs.map((d) => d.data)) };
    },
  };
  const d3 = { utcParse: () => (s) => new Date(s + 'T00:00:00Z'), utcFormat: () => () => '', group: () => new Map() };
  const document = { querySelectorAll: (sel) => (sel === '[data-policy-flag]' ? flags : switches[sel] || []), getElementById: () => null };
  class TestDate extends Date {
    constructor(...args) { super(...(args.length ? args : [now])); }
  }
  const ctx = { window: {}, dash, d3, document, console, Number, Math, String, Object, Array, Map, Set,
    Date: TestDate, isNaN, encodeURIComponent };
  ctx.window.addEventListener = () => {};
  vm.runInNewContext(src, ctx);
  return { draws, flags, switches, window: ctx.window };
}

const obs = (rows) => ({ status: 'ok', data: rows, meta: [] });
const policyObs = (repo) => obs([
  { series: 'repo', period: '2025-12-05', label: '5 Dec 2025', date: '2025-12-05', value: 5.25 },
  { series: 'repo', period: '2026-10-07', label: '7 Oct 2026', date: '2026-10-07', value: repo },
  { series: 'sdf', period: '2026-10-07', label: '7 Oct 2026', date: '2026-10-07', value: 5.25 },
  { series: 'msf', period: '2026-10-07', label: '7 Oct 2026', date: '2026-10-07', value: 5.75 },
]);
const snapshot = (repo, sdf) => ({ status: 'ok', meta: [], data: [
  { item: 'Policy Repo Rate', group: 'Policy rates', value: repo, unit: '%', as_of: '2026-11-24' },
  { item: 'Standing Deposit Facility Rate', group: 'Policy rates', value: sdf, unit: '%', as_of: '2026-11-24' },
  { item: 'INR / 1 USD', group: 'FBIL reference rate', value: 92.7968, unit: '₹', as_of: 'today' },
] });

let failures = 0;
function test(name, fn) {
  try { fn(); console.log('ok  -', name); }
  catch (e) { failures++; console.log('FAIL-', name, '\n   ', e.message); }
}

test('missing snapshot value renders as a dash, not 0.00%', () => {
  const { draws } = load({ observations: policyObs(5.5), catalog: obs([]), snapshot: snapshot(5.5, null) });
  const tb = tbody();
  draws.snap(tb);
  const sdf = tb.rows.find((r) => r.cells[1].textContent === 'Standing Deposit Facility Rate');
  assert.strictEqual(sdf.cells[2].textContent, '—');
  const repo = tb.rows.find((r) => r.cells[1].textContent === 'Policy Repo Rate');
  assert.strictEqual(repo.cells[2].textContent, '5.50%');
  const usd = tb.rows.find((r) => r.cells[1].textContent === 'INR / 1 USD');
  assert.strictEqual(usd.cells[2].textContent, '92.7968');
});

test('policy warning stays hidden when the feeds agree', () => {
  const { draws, flags } = load({ observations: policyObs(5.5), catalog: obs([]), snapshot: snapshot(5.5, 5.25) });
  draws['policy-check']();
  assert.strictEqual(flags[0].hidden, true);
});

test('policy warning shows when rbi.org.in has a new repo rate', () => {
  const { draws, flags } = load({ observations: policyObs(5.5), catalog: obs([]), snapshot: snapshot(5.75, 5.25) });
  draws['policy-check']();
  assert.strictEqual(flags[0].hidden, false);
  const el = { textContent: '' };
  draws['policy-diff'](el);
  assert.match(el.textContent, /Policy Repo Rate 5\.75% on rbi\.org\.in vs 5\.50% in the history/);
});

test('a missing live rate is not treated as a disagreement', () => {
  const { draws, flags } = load({ observations: policyObs(5.5), catalog: obs([]), snapshot: snapshot(null, 5.25) });
  draws['policy-check']();
  assert.strictEqual(flags[0].hidden, true);
});

test('a scheduled repo rate stays out of the current headline and chart until its effective India date', () => {
  const observations = policyObs(5.5);
  observations.data.push({ series: 'repo', period: '2026-12-01', date: '2026-12-01', label: '1 Dec 2026', value: 5.75 });
  const datasets = { observations, catalog: obs([]), snapshot: snapshot(5.5, 5.25) };
  const headline = { dataset: { k: 'repo', part: 'value' }, classList: { remove() {} } };
  const note = {};

  const before = load(datasets, '2026-11-30T18:29:59Z');
  before.draws.kpi(headline);
  before.draws['policy-check']();
  before.draws['scheduled-policy'](note);
  assert.strictEqual(headline.textContent, '5.50%');
  assert.strictEqual(before.flags[0].hidden, true);
  assert.strictEqual(before.window.MM._idx.m.get('repo').at(-1).v, 5.5);
  assert.match(note.textContent, /Scheduled policy changes: Policy Repo Rate 5\.75% from 1 Dec 2026/);

  const after = load(datasets, '2026-11-30T18:30:00Z');
  after.draws.kpi(headline);
  after.draws['policy-check']();
  after.draws['scheduled-policy'](note);
  assert.strictEqual(headline.textContent, '5.75%');
  assert.strictEqual(after.flags[0].hidden, true, 'the earlier snapshot still agrees with the earlier in-force rate');
  assert.strictEqual(after.window.MM._idx.m.get('repo').at(-1).v, 5.75);
  assert.strictEqual(note.textContent, '');
});

// ---------- banking brief and neutral tiles ----------
function el(dataset = {}) {
  const classes = new Set();
  return { textContent: '', dataset, classList: { add: (c) => classes.add(c), remove: (...c) => c.forEach((x) => classes.delete(x)), has: (c) => classes.has(c) }, classes };
}
const monthRow = (series, period, value) => {
  const M = 'Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec'.split(' ');
  return { series, period, label: `${M[+period.slice(5, 7) - 1]} ${period.slice(0, 4)}`, date: `${period}-15`, value };
};
const bankObs = (withRatio = true) => obs([
  ['2026-07', 3.95], ['2026-08', 1.48], ['2026-09', 1.05], ['2026-10', 2.68]].map(([p, v]) => monthRow('scb_gap', p, v))
  .concat([['2026-07', 4.91], ['2026-08', 3.59], ['2026-09', 2.16], ['2026-10', 1.74]].map(([p, v]) => monthRow('scb_gap_3m', p, v)))
  .concat([['2025-10', 72.07], ...(withRatio ? [['2026-10', 90.13]] : [])].map(([p, v]) => monthRow('scb_inc_cd_fytd', p, v)))
  .concat([['2026-09', 229.9], ['2026-10', 231.8]].map(([p, v]) => monthRow('scb_credit', p, v)))
  .concat([['2026-09', 5.54], ['2026-10', 6.09]].map(([p, v]) => monthRow('cpi_infl_combined', p, v))));

test('tiles show changes neutrally, with no good or bad colour', () => {
  const { draws } = load({ observations: bankObs(), catalog: obs([]), snapshot: snapshot(5.5, 5.25) });
  for (const k of ['cpi_infl_combined', 'scb_gap']) {
    const e = el({ k, part: 'change' });
    draws.kpi(e);
    assert.ok(e.classList.has('is-flat'), k);
    assert.ok(!e.classList.has('is-good') && !e.classList.has('is-bad'), k);
  }
  const g = el({ k: 'scb_gap', part: 'change' });
  draws.kpi(g);
  assert.strictEqual(g.textContent, '+1.63 pp vs Sep 2026');
});

test('CPI is described against the 2-6% tolerance band', () => {
  const cases = [[6.09, 'above the 6% upper tolerance level'], [4.5, 'within the 2–6% tolerance band around the 4% target'],
    [1.5, 'below the 2% lower tolerance level']];
  for (const [v, want] of cases) {
    const { draws } = load({ observations: obs([monthRow('cpi_infl_combined', '2026-10', v)]), catalog: obs([]), snapshot: snapshot(5.5, 5.25) });
    const e = el();
    draws['vs-band'](e);
    assert.strictEqual(e.textContent, want);
  }
});

test('brief says the gap widened while its 3-month average narrowed for the 3rd month in a row', () => {
  const { draws } = load({ observations: bankObs(), catalog: obs([]), snapshot: snapshot(5.5, 5.25) });
  const a = el({ k: 'scb_gap' }), b = el({ k: 'scb_gap_3m' });
  draws.direction(a); draws.direction(b);
  assert.strictEqual(a.textContent, 'widened');
  assert.strictEqual(b.textContent, 'narrowed for the 3rd month in a row');
});

test('incremental credit-deposit ratio shows the latest month beside the same month last year', () => {
  const { draws, switches } = load({ observations: bankObs(true), catalog: obs([]), snapshot: snapshot(5.5, 5.25) });
  draws['inccd-state']();
  assert.strictEqual(switches['[data-switch="inccd-ok"]'][0].hidden, false);
  assert.strictEqual(switches['[data-switch="inccd-missing"]'][0].hidden, true);
  const parts = Object.fromEntries(['value', 'label', 'year_ago', 'year_ago_label'].map((part) => { const e = el({ part }); draws.inccd(e); return [part, e.textContent]; }));
  assert.deepStrictEqual(parts, { value: '90.1%', label: 'end-October 2026', year_ago: '72.1%', year_ago_label: 'end-March to end-October 2025' });
});

test('incremental ratio explains itself instead of showing a number when deposits barely grew', () => {
  const { draws, switches } = load({ observations: bankObs(false), catalog: obs([]), snapshot: snapshot(5.5, 5.25) });
  draws['inccd-state']();
  assert.strictEqual(switches['[data-switch="inccd-ok"]'][0].hidden, true);
  assert.strictEqual(switches['[data-switch="inccd-missing"]'][0].hidden, false);
  const v = el({ part: 'value' }); draws.inccd(v);
  assert.strictEqual(v.textContent, '—');
  const p = el({ part: 'pending_label' }); draws.inccd(p);
  assert.strictEqual(p.textContent, 'Oct 2026');
});

if (failures) { console.log(`${failures} failed`); process.exit(1); }
console.log('all render checks passed');
