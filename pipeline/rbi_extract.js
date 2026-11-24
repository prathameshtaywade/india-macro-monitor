/*
 * RBI extract — run in a normal browser on https://rbidocs.rbi.org.in/ (open DevTools > Console, paste, run).
 *
 * Why a browser: rbidocs.rbi.org.in serves XLSX tables behind a JavaScript challenge, so plain curl/requests
 * get an HTML page instead of the file. A real browser passes it normally; this script then reads the
 * public XLSX files with fetch() and parses them with built-in APIs (DecompressionStream + DOMParser).
 * No third-party code. Output: a JSON blob copied to the clipboard -> save as data/raw/rbi_extract.json.
 *
 * Inputs to update on each refresh:
 *   HB_IDS  - file ids of the latest "Handbook of Statistics on Indian Economy" tables (annual, ~Jul/Sep).
 *             Find them on https://www.rbi.org.in/Scripts/AnnualPublications.aspx?head=Handbook%20of%20Statistics%20on%20Indian%20Economy
 *   WSS     - file ids for Weekly Statistical Supplement tables 2 (forex), 4 (SCB business), 5 (ratios & rates):
 *             https://rbi.org.in/Scripts/WSSViewDetail.aspx?TYPE=Section&PARAM1=2   (forex reserves)
 *             https://rbi.org.in/Scripts/WSSViewDetail.aspx?TYPE=Section&PARAM1=3   (SCB business, file 4T_)
 *             https://rbi.org.in/Scripts/WSSViewDetail.aspx?TYPE=Section&PARAM1=4   (ratios & rates, file 5T_)
 *             pipeline/list_wss.py prints these lists ready to paste.
 *   POLICY_EXTRA - policy-rate changes after the Handbook cut-off. Use the EFFECTIVE date stated in the MPC
 *             resolution (normally the announcement date, "with immediate effect"), and cite the press release.
 *
 * Weekly values are emitted as [date, value, issueDate]. The same week or fortnight appears in several WSS
 * issues and can be revised; pipeline/merge_rbi.py keeps the value from the newest issue.
 */
const HB_IDS = {
  40: '40T_HBIE31072026FF3E894445944DA8A3C011F1653F999A',   // policy rates, CRR, SLR (effective dates)
  167: '167T_HBIE31072026B5325D726F404EB3953FBF87255287C1', // SCB select aggregates, monthly
  178: '178T_HBIE310720260B5138FE9BE24FC0939F05E5EE409982', // month-end G-Sec yields by maturity
  205: '205T_HBIE31072026B40F14BA1C1C40C9B8FDC62949CCB66B', // exchange rates, monthly average
  210: '210T_HBIE31072026A75E2EE4E1454A57BBA434E6FCA61E93', // forex reserves, monthly
  215: '215T_HBIE310720263381697DEC8847C887856367E4BAE81A', // forex reserves, weekly
};
const WSS = { fx: [/* [issueDate, '2T_...'] */], scb: [/* '4T_...' */], rr: [/* '5T_...' */] };
// [effectiveDate, repo, sdf, msf, crr, slr, source]
const POLICY_EXTRA = [['2026-10-07', 5.5, 5.25, 5.75, null, null, 'MPC resolution 5-7 Oct 2026, RBI press release prid=63742: with immediate effect']];

async function readXlsx(url) {
  const buf = new Uint8Array(await (await fetch(url)).arrayBuffer());
  const dv = new DataView(buf.buffer);
  let eocd = buf.length - 22; while (dv.getUint32(eocd, true) !== 0x06054b50) eocd--;
  const n = dv.getUint16(eocd + 10, true); let p = dv.getUint32(eocd + 16, true);
  const files = {};
  for (let i = 0; i < n; i++) {
    const method = dv.getUint16(p + 10, true), csize = dv.getUint32(p + 20, true), nl = dv.getUint16(p + 28, true),
      el = dv.getUint16(p + 30, true), cl = dv.getUint16(p + 32, true), off = dv.getUint32(p + 42, true);
    files[new TextDecoder().decode(buf.slice(p + 46, p + 46 + nl))] = { method, csize, off }; p += 46 + nl + el + cl;
  }
  async function get(name) {
    const f = files[name]; if (!f) return null;
    const lnl = dv.getUint16(f.off + 26, true), lel = dv.getUint16(f.off + 28, true);
    const data = buf.slice(f.off + 30 + lnl + lel, f.off + 30 + lnl + lel + f.csize);
    if (f.method === 0) return new TextDecoder().decode(data);
    return await new Response(new Blob([data]).stream().pipeThrough(new DecompressionStream('deflate-raw'))).text();
  }
  const dp = new DOMParser(), ss = [], sst = await get('xl/sharedStrings.xml');
  if (sst) for (const si of dp.parseFromString(sst, 'application/xml').getElementsByTagName('si'))
    ss.push(Array.from(si.getElementsByTagName('t')).map(t => t.textContent).join(''));
  const out = {};
  for (const sn of Object.keys(files).filter(k => /^xl\/worksheets\/sheet\d+\.xml$/.test(k)).sort()) {
    const rows = [];
    for (const r of dp.parseFromString(await get(sn), 'application/xml').getElementsByTagName('row')) {
      const row = [];
      for (const c of r.getElementsByTagName('c')) {
        let col = 0; for (const ch of c.getAttribute('r').replace(/\d+/, '')) col = col * 26 + ch.charCodeAt(0) - 64;
        const v = c.getElementsByTagName('v')[0]; let val = v ? v.textContent : null;
        if (c.getAttribute('t') === 's' && val !== null) val = ss[+val];
        if (c.getAttribute('t') === 'inlineStr') val = c.textContent;
        if (val !== null && val !== '') row[col - 1] = val;
      }
      rows.push(row);
    }
    out[sn] = rows;
  }
  return out;
}

(async () => {
  const MO = { jan: 1, feb: 2, mar: 3, apr: 4, may: 5, jun: 6, jul: 7, aug: 8, sep: 9, oct: 10, nov: 11, dec: 12 };
  const M = { Jan: 1, Feb: 2, Mar: 3, Apr: 4, May: 5, Jun: 6, Jul: 7, Aug: 8, Sep: 9, Oct: 10, Nov: 11, Dec: 12 };
  const ser = s => new Date(Date.UTC(1899, 11, 30) + (+s) * 864e5).toISOString().slice(0, 10);
  const num = v => (v == null || v === '-' || v === '' || v === '..') ? null : Math.round(parseFloat(String(v).replace(/[(),]/g, '')) * 1e4) / 1e4;
  const ym = (y, m) => y + '-' + String(m).padStart(2, '0');
  const pd = s => { const m = String(s).match(/([A-Za-z]{3})[a-z]*\.?\s+(\d{1,2}),\s*(\d{4})/); return m ? `${m[3]}-${String(MO[m[1].toLowerCase()]).padStart(2, '0')}-${m[2].padStart(2, '0')}` : null; };
  const HB = {}; for (const [k, v] of Object.entries(HB_IDS)) HB[k] = await readXlsx('/rdocs/Publications/DOCs/' + v + '.XLSX');
  const out = { provenance: { extracted_utc: new Date().toISOString(), handbook_ids: HB_IDS } };

  const pol = []; for (const s of Object.values(HB[40])) for (const r of s)
    if (r && /^\d{5}$/.test(r[1] || '')) pol.push([ser(r[1]), num(r[3]), num(r[5]), num(r[6]), num(r[7]), num(r[8])]);
  out.policy = pol.concat(POLICY_EXTRA).sort((a, b) => a[0] < b[0] ? -1 : 1);

  let y = null; out.scb_dep = []; out.scb_credit = [];
  for (const r of Object.values(HB[167])[0]) { if (!r) continue; if (/^\d{4}$/.test(r[1] || '')) { y = +r[1]; continue; }
    if (y && M[r[1]]) { out.scb_dep.push([ym(y, M[r[1]]), num(r[4])]); out.scb_credit.push([ym(y, M[r[1]]), num(r[13])]); } }

  const G = { '1': [], '5': [], '10': [] };
  for (const s of Object.values(HB[178])) { let fy = null; const hdr = s[2];
    for (const r of s) { if (!r) continue; if (/^\d{4}-\d{2}$/.test(r[1] || '')) { fy = +r[1].slice(0, 4); continue; }
      if (fy && G[r[1]]) for (let i = 2; i <= 13; i++) { const m = M[(hdr[i] || '').replace('.', '')]; const v = num(r[i]);
        if (m && v != null) G[r[1]].push([ym(m >= 4 ? fy : fy + 1, m), Math.round(v * 100) / 100]); } } }
  out.gsec10 = G['10']; out.gsec5 = G['5']; out.gsec1 = G['1'];

  y = null; out.usdinr_m = []; out.eurinr_m = [];
  for (const s of Object.values(HB[205])) for (const r of s) { if (!r) continue; if (/^\d{4}$/.test(r[1] || '')) { y = +r[1]; continue; }
    if (y && M[r[1]]) { out.usdinr_m.push([ym(y, M[r[1]]), num(r[4])]); out.eurinr_m.push([ym(y, M[r[1]]), num(r[10])]); } }

  y = null; out.forex_m = [];
  for (const r of Object.values(HB[210])[0]) { if (!r) continue; if (/^\d{4}$/.test(r[1] || '')) { y = +r[1]; continue; }
    if (y && M[r[1]]) out.forex_m.push([ym(y, M[r[1]]), num(r[11])]); }
  out.forex_w = []; for (const s of Object.values(HB[215])) for (const r of s)
    if (r && /^\d{5}$/.test(r[1] || '')) out.forex_w.push([ser(r[1]), num(r[11])]);

  const sheet = async id => Object.values(await readXlsx('/rdocs/Wss/DOCs/' + id + '.XLSX'))[0];
  const keep = a => a.filter(([d, v]) => d && v != null);   // no de-duplication here: merge_rbi.py resolves revisions by issue date
  const fx = [], dep = [], cr = [], rr = {};
  for (const [issue, id] of WSS.fx) { const s = await sheet(id); let d = null, t = null;
    for (const r of s) { if (!r) continue; if (!d && /As on/i.test(r.join('|'))) d = pd(r.join('|')); if (/^1 Total Reserves/.test(r[1] || '')) t = num(r[3]); }
    fx.push([d, t, issue]); }
  for (const [issue, id] of WSS.scb) { const s = await sheet(id); let d = null, a = null, c = null;
    for (const r of s) { if (!r) continue; if (!d && /Outstanding as on/i.test(r.join('|'))) d = pd(r.join('|'));
      if (/^2\.1 Aggregate Deposits/.test(r[1] || '')) a = num(r[2]); if (/^7 Bank Credit/.test(r[1] || '')) c = num(r[2]); }
    dep.push([d, a, issue]); cr.push([d, c, issue]); }
  const want = { 'Policy Repo Rate': 'repo', '10-Year G-Sec': 'gsec10_weekly', 'INR-US$ Spot': 'usdinr_weekly', 'Call Money Rate': 'call_weekly', '91-Day Treasury': 'tb91_weekly' };
  for (const [f, id] of WSS.rr) { const s = await sheet(id); const fy = +f.slice(0, 4), fm = +f.slice(5, 7); let hdr = null;
    for (const r of s) { if (!r) continue; const lab = r[1] || '';
      if (/Item\/Week Ended/.test(lab)) { hdr = 'next'; continue; } if (hdr === 'next') { hdr = r; continue; }
      if (Array.isArray(hdr)) for (const [k, key] of Object.entries(want)) if (lab.startsWith(k))
        for (let i = 3; i < hdr.length; i++) { const m = String(hdr[i] || '').match(/([A-Za-z]{3})\.?\s*(\d{1,2})/); if (!m) continue;
          const mo = MO[m[1].toLowerCase()]; const v = num(r[i]); if (v == null) continue;
          (rr[key] = rr[key] || []).push([`${mo > fm ? fy - 1 : fy}-${String(mo).padStart(2, '0')}-${m[2].padStart(2, '0')}`, v, f]); } } }
  out.forex_w_wss = keep(fx); out.scb_dep_wss = keep(dep); out.scb_credit_wss = keep(cr);
  for (const k in rr) if (k !== 'repo') out[k] = keep(rr[k]);
  const json = JSON.stringify(out);
  try { await navigator.clipboard.writeText(json); console.log('Copied', json.length, 'chars to clipboard'); }
  catch { console.log(json); }
})();
