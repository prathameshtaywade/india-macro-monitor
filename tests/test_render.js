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
  const document = { querySelectorAll: (sel) => (sel === '[data-policy-flag]' ? flags : []), getElementById: () => null };
  class TestDate extends Date {
    constructor(...args) { super(...(args.length ? args : [now])); }
  }
  const ctx = { window: {}, dash, d3, document, console, Number, Math, String, Object, Array, Map, Set,
    Date: TestDate, isNaN, encodeURIComponent };
  ctx.window.addEventListener = () => {};
  vm.runInNewContext(src, ctx);
  return { draws, flags, window: ctx.window };
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

if (failures) { console.log(`${failures} failed`); process.exit(1); }
console.log('all render checks passed');
