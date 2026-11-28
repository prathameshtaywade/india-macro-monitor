/* Pure transforms for the Explorer, shared with the offline checks. */
(function () {
  const labels = {
    level: 'As published',
    monthly: 'Month-on-month change',
    annual: 'Year-on-year change',
    rebased: 'Rebased to 100',
    adjusted: 'Seasonally adjusted level',
  };
  function monthNumber(day) {
    return Number(day.slice(0, 4)) * 12 + Number(day.slice(5, 7)) - 1;
  }
  function validModes(series) {
    const level = /^(Index|₹|US\$)/.test(series.unit);
    const rate = /^(%|pp|bp)/.test(series.unit) && !series.freq.startsWith('Event');
    return ['level', ...(series.freq === 'Monthly' && (level || rate) ? ['monthly'] : []),
      ...((series.freq === 'Monthly' || series.freq === 'Quarterly') && (level || rate) ? ['annual'] : []),
      ...(level ? ['rebased'] : []),
      ...(series.freq === 'Monthly' && level && series.obs >= 60 ? ['adjusted'] : [])];
  }
  function change(rows, lag, isRate) {
    const values = new Map(rows.map((p) => [monthNumber(p.date), p.value]));
    return rows.flatMap((p) => {
      const prev = values.get(monthNumber(p.date) - lag);
      if (!Number.isFinite(prev) || (!isRate && prev <= 0)) return [];
      return [{ ...p, value: isRate ? p.value - prev : (p.value / prev - 1) * 100 }];
    });
  }
  function seasonal(rows) {
    // Multiplicative classical decomposition, with centred 12-month trend and no gaps.
    if (rows.length < 60 || rows.some((p, i) => p.value <= 0 ||
      (i > 0 && monthNumber(p.date) - monthNumber(rows[i - 1].date) !== 1))) return [];
    const ratios = Array.from({ length: 12 }, () => []);
    for (let i = 6; i < rows.length - 6; i++) {
      const trend = rows.slice(i - 6, i + 7).reduce((sum, p, j) =>
        sum + p.value * (j === 0 || j === 12 ? 0.5 : 1), 0) / 12;
      ratios[monthNumber(rows[i].date) % 12].push(rows[i].value / trend);
    }
    const factors = ratios.map((months) => months.reduce((sum, v) => sum + v, 0) / months.length);
    const mean = factors.reduce((sum, v) => sum + v, 0) / 12;
    return rows.map((p) => ({ ...p, value: p.value * mean / factors[monthNumber(p.date) % 12] }));
  }
  function transform(series, rows, mode, baseline) {
    const rate = /^(%|pp|bp)/.test(series.unit);
    if (mode === 'monthly' || mode === 'annual') return {
      unit: rate ? (series.unit === 'bp' ? 'bp' : 'pp') : '%',
      rows: change(rows, mode === 'monthly' ? 1 : 12, rate),
    };
    if (mode === 'rebased') {
      const start = rows.find((p) => p.period === baseline);
      return { unit: 'Index (start = 100)', rows: start?.value > 0 ?
        rows.filter((p) => p.period >= baseline).map((p) => ({ ...p, value: p.value / start.value * 100 })) : [] };
    }
    if (mode === 'adjusted') return { unit: series.unit, rows: seasonal(rows) };
    return { unit: series.unit, rows };
  }
  function baseline(left, right) {
    const common = right ? new Set(right.filter((p) => p.value > 0).map((p) => p.period)) : null;
    return left.find((p) => p.value > 0 && (!common || common.has(p.period)))?.period;
  }
  const api = { labels, validModes, transform, baseline };
  if (typeof module !== 'undefined') module.exports = api;
  else window.MacroResearch = api;
})();
