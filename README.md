# India Macro Monitor — data pipeline

Source-backed Indian macro dataset (47 series) built only from official **MoSPI** and **RBI** sources, plus the
interactive dashboard that reads it. Data first built **24 Nov 2026**; the table below is that snapshot. Free/open tooling only: Python 3 standard library,
a browser, and d3 in the dashboard.

## Coverage at build time

| Topic | Series (id) | Freq | Unit | Coverage | Latest | Source |
|---|---|---|---|---|---|---|
| GDP | `gdp_growth_q` real GDP growth y/y (2022-23 base) | Q (fiscal) | % | Q1 2023-24 → Q1 2026-27 | 7.8 | MoSPI NAS API, indicator 22 |
| GDP | `gdp_growth_q_old` (2011-12 base, discontinued) | Q | % | Q1 2012-13 → Q2 2025-26 | 8.2 | MoSPI NAS API |
| GVA | `gva_growth_q` + 8 sector series | Q | % | Q1 2023-24 → Q1 2026-27 | 8.2 (total) | MoSPI NAS API, indicator 21 |
| GDP | `gdp_level_q`, `gdp_growth_a`, nominal growth | Q / FY | ₹ lakh cr / % | 2022-23 → | | MoSPI NAS API |
| CPI | `cpi_infl_combined/rural/urban`, `cpi_food`, `cpi_index` (2024=100) | M | % / index | Jan 2026 → Oct 2026 (index from Jan 2025) | 6.09 | MoSPI `getCPIData` |
| CPI | `cpi_infl_old`, `cfpi_old` (2012=100, discontinued) | M | % | Jan 2014 → Dec 2025 | 1.33 | MoSPI `getCPIIndex` |
| IIP | `iip_growth`, `iip_index`, mining/manufacturing/electricity (2022-23=100) | M | % | Apr 2023 → Sep 2026 | 6.7 | MoSPI `getIipData` |
| IIP | `iip_growth_old` (2011-12=100) | M | % | Apr 2012 → Mar 2026 | 4.1 | MoSPI `getIipData` |
| Policy | `repo`, `sdf`, `msf`, `crr`, `slr` | event | % | Apr 2008 → 7 Oct 2026 | repo 5.50 | RBI Handbook T40 + MPC resolution 7 Oct 2026 |
| Yields | `gsec10`, `gsec5`, `gsec1` month-end | M | % | Apr 2023 → Jun 2026 | 6.74 (10Y) | RBI Handbook T178 |
| Yields | `gsec10_w` (FBIL 10Y par), `tb91_w`, `call_w` | W | % | Jan → 13 Nov 2026 | 7.34 / 5.87 / 5.55 | RBI WSS Table 5 |
| Forex | `forex_m` month-end | M | US$ bn | Mar 1990 → May 2026 | 686.3 | RBI via MoSPI API (ind. 47) + Handbook T210 |
| Forex | `forex_w` weekly | W | US$ bn | 5 Apr 2024 → 13 Nov 2026 | 705.3 | Handbook T215 + WSS Table 2 |
| FX | `usdinr_m`, `eurinr_m` monthly average | M | ₹ | Mar 1992 → Jun 2026 | 94.97 | RBI via MoSPI API (ind. 33) + Handbook T205 |
| FX | `usdinr_w` FBIL reference | W | ₹ | Jan → 13 Nov 2026 | 94.20 | RBI WSS Table 5 |
| Banks | `scb_credit`, `scb_dep` (+ y/y growth) | M | ₹ lakh cr / % | Jan 2022 → Oct 2026 | 231.8 / 282.5; credit +19.5% y/y | Handbook T167 + WSS Table 4 |
| Snapshot | RBI "Current Rates" box | daily | | 23 Nov 2026 FBIL; 19 Nov G-Sec | USD/INR 92.7968 | rbi.org.in |

`data/macro.json` holds every series with unit, frequency, base, source, query URL and notes.

## Verification done

- MoSPI-hosted RBI forex reserves match Handbook Table 210 to the rounding for all 28 overlapping months (Mar 2023–Jun 2025).
- MoSPI-hosted USD/INR monthly averages match Handbook Table 205 for Jan–Aug 2025.
- Handbook weekly reserves (Table 215) and WSS Table 2 agree on the overlap week (19 Jun 2026: US$ 672,587 mn).
- CPI Oct 2026 = 6.09% matches the RBI DBIE headline ticker; repo 5.50% matches WSS, the rbi.org.in box and the
  7 Oct 2026 MPC resolution (RBI press release prid 63742); WSS call rate 5.55% matches the DBIE WACR ticker.
- Browser-extracted RBI data was checksummed against the saved JSON (row counts and value sums per series).

## Website and automation

The same page runs in two places: the Claude dashboard and a static website built into `site/` from
`web/template.html` + `dashboard/page/` (the small `web/dash-shim.js` stands in for the Claude dashboard runtime).

| What | How often | Who |
|---|---|---|
| MoSPI series (GDP/GVA, CPI, IIP, RBI forex/FX history) | daily, 09:00 IST | GitHub Action `update.yml` |
| rbi.org.in Current Rates (repo, FBIL rates, G-Sec yields) | daily | GitHub Action `update.yml` |
| Validate, commit data, publish to GitHub Pages | daily, and on every push | GitHub Action `update.yml` |
| RBI Handbook + Weekly Statistical Supplement tables | weekly (WSS is out on Fridays) | **a person**, prompted by an issue from `rbi-reminder.yml` |
| MPC rate decisions | every two months | **a person** adds them to `POLICY_EXTRA` in `pipeline/rbi_extract.js` |
| New Handbook file ids | once a year (Jul–Sep) | **a person** updates `HB_IDS` in `pipeline/rbi_extract.js` |

`pipeline/validate.py` blocks publishing if a core series is missing, a value is out of range, a series' latest
period moves backwards, or its history shrinks by more than 5% versus the last commit. Stale sources only warn.
If a fetch fails, the Action keeps the last good raw files (cached) and the last good site stays up.

### One-time GitHub setup

1. Create an empty repository on GitHub, then `git remote add origin <url>` and `git push -u origin main`.
2. Settings → Pages → Build and deployment → Source: **GitHub Actions**.
3. Settings → Actions → General → Workflow permissions: **Read and write** (so the daily job can commit data).
4. Actions tab → "Update data and site" → **Run workflow** for the first deploy.

### Weekly manual RBI step (about 2 minutes)

1. Copy the `WSS` snippet from the reminder issue into `pipeline/rbi_extract.js` (or run `python3 pipeline/list_wss.py <since-date>`).
2. Open https://rbidocs.rbi.org.in/ in your browser, paste the whole script into the DevTools console, press Enter.
   It copies JSON to the clipboard.
3. `pbpaste | python3 pipeline/merge_rbi.py -` (macOS), then commit and push `data/raw/rbi_extract.json`.
   The push triggers a rebuild and republish.

Why a browser step: `rbidocs.rbi.org.in` (where RBI's XLSX tables live) serves its files only to a browser that
runs its JavaScript check, and RBI's DBIE portal (`data.rbi.org.in`) uses session tokens and encrypted requests
with no documented public API. The script only reads public files with `fetch()` and parses them with built-in
browser APIs. Automating this with a headless browser would mean getting past RBI's bot check, so it is left manual.

### Run everything locally

```
python3 pipeline/fetch_mospi.py          # MoSPI API, no key; NAS = 1 indicator/call, CPI-2024 max 100 rows/page
python3 pipeline/fetch_rbi_home.py       # rbi.org.in Current Rates box
python3 pipeline/build_data.py           # -> data/macro.json
python3 pipeline/export_dashboard.py     # -> dashboard/observations.json, catalog.json, snapshot.json
python3 pipeline/validate.py             # exit 1 on errors
python3 pipeline/build_site.py           # -> site/
python3 -m http.server -d site 8000      # preview at http://localhost:8000
```
The Claude dashboard's three data files are replaced from its Sources panel (or ask Claude).

Release rhythm: CPI ~12th of the month; IIP near month-end; quarterly GDP at the end of the second month after the
quarter; WSS every Friday; MPC every two months; Handbook yearly (Jul–Sep).

## Known gaps

1. **Base-year breaks.** GDP (2022-23 base) growth starts Q1 2023-24 and differs sharply from the old series
   (Q1 2023-24: 6.6% vs 9.6%). CPI (2024 base) inflation starts Jan 2026. IIP new base from Apr 2023. Not chained.
2. **Handbook cut-offs.** Monthly RBI tables end Mar 2026 (banks) or Jun 2026 (yields, FX, weekly reserves).
   WSS fills weekly 10Y, USD/INR, reserves and bank totals after that, but not 1Y/5Y month-end yields or monthly averages.
3. **Two 10Y yields**: Handbook = SGL trades at 10-year residual maturity; WSS = FBIL 10-year par yield.
4. **Bank aggregates** only from Jan 2022 here; reporting date changed (last reporting Friday → month-end) from Dec 2025;
   HDFC merger (1 Jul 2023) inflates y/y growth Jul 2023–Jun 2024.
5. **Policy-rate history** starts Apr 2008 (Handbook Table 40); SDF only from 8 Apr 2022.
6. **DBIE** not used directly (see above); it is the route to longer bank, money and yield histories.
7. Not yet released at build time: Q2 2026-27 GDP, Nov 2026 CPI, Oct 2026 IIP.

## Layout

```
.github/workflows/  update.yml (daily build + Pages)  rbi-reminder.yml (weekly issue)
pipeline/   fetch_mospi.py  fetch_rbi_home.py  list_wss.py  rbi_extract.js  merge_rbi.py
            build_data.py  export_dashboard.py  validate.py  build_site.py
web/        template.html  dash-shim.js            (standalone-site wrapper)
dashboard/  page/index.html  page/app.js           (shared page + charts)
            observations.json  catalog.json  snapshot.json
data/       macro.json  raw/rbi_extract.json  raw/rbi_home.json   (raw/mospi/ is fetched, not committed)
site/       build output, not committed
```
