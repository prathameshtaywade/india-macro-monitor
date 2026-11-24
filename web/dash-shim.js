// Minimal stand-in for the Claude dashboard runtime (`dash`), so dashboard/page/app.js runs on a plain website.
// Implements only what app.js uses: data, calc, draw, colors.
(function () {
  const FILES = { observations: 'data/observations.json', catalog: 'data/catalog.json', snapshot: 'data/snapshot.json' };
  const state = {};
  const calcs = {};
  const calcCache = {};
  const draws = new Map();

  for (const id of Object.keys(FILES)) state[id] = { status: 'loading', data: [], meta: [] };

  function data(id) {
    if (state[id]) return state[id];
    const c = calcs[id];
    if (!c) return { status: 'missing', data: [], meta: [] };
    const inputs = c.inputs.map(data);
    const bad = inputs.find((d) => d.status !== 'ok');
    if (bad) return { status: bad.status, data: null, meta: [] };
    const key = inputs.map((d) => d.data);
    const hit = calcCache[id];
    if (hit && hit.key.every((k, i) => k === key[i])) return hit.result;
    let result;
    try { result = { status: 'ok', data: c.fn(...inputs.map((d) => d.data)), meta: [] }; }
    catch (e) { console.error(e); result = { status: 'error', data: null, message: String(e), meta: [] }; }
    calcCache[id] = { key, result };
    return result;
  }

  function runDraw(name) {
    const fn = draws.get(name);
    if (!fn) return;
    for (const el of document.querySelectorAll(`[data-draw="${name}"]`)) {
      if (el.closest('[hidden]')) continue;
      try { fn(el); } catch (e) { console.error(`draw ${name}:`, e); }
    }
  }
  function runAll() { for (const name of draws.keys()) runDraw(name); }

  let queued = false;
  function schedule() {
    if (queued) return;
    queued = true;
    requestAnimationFrame(() => { queued = false; runAll(); });
  }

  window.dash = {
    colors: ['var(--c1)', 'var(--c2)', 'var(--c3)', 'var(--c4)', 'var(--c5)'],
    data,
    calc(id, spec) { calcs[id] = spec; },
    loader() {},
    onData(fn) { fn(); },
    draw(name, fn) {
      if (typeof fn === 'function') { draws.set(name, fn); schedule(); }
      else runDraw(name);
    },
    params: () => ({}), setParams() {}, resetParams() {}, setLink() {}, refresh() {},
  };

  for (const [id, url] of Object.entries(FILES)) {
    fetch(url, { cache: 'no-cache' })
      .then((r) => { if (!r.ok) throw new Error(r.status + ' ' + url); return r.json(); })
      .then((j) => { state[id] = { status: 'ok', data: Array.isArray(j) ? j : j.rows || [], meta: j.meta || [] }; })
      .catch((e) => { console.error(e); state[id] = { status: 'error', data: [], meta: [], message: String(e) }; })
      .finally(schedule);
  }

  // Redraw when the width changes or a section is shown again.
  let lastW = 0;
  new ResizeObserver(() => { const w = document.body.clientWidth; if (Math.abs(w - lastW) > 4) { lastW = w; schedule(); } })
    .observe(document.body);
  // (only sections: chart tooltips also toggle `hidden` and must not trigger a redraw)
  new MutationObserver((recs) => { if (recs.some((r) => r.target.matches('.mm-sec, details, [data-policy-flag], [data-switch]'))) schedule(); }).observe(document.body, { subtree: true, attributes: true, attributeFilter: ['hidden'] });
})();
