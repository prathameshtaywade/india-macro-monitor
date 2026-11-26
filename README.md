# India Macro Monitor — data pipeline

Source-backed Indian macro dataset built only from official **MoSPI** and **RBI** sources, plus the
interactive dashboard that reads it. Data first built **24 Nov 2026**; the table below is that snapshot. Free/open tooling only: Python 3 standard library,
a browser, and d3 in the dashboard.

## Coverage at build time

| Topic | Series (id) | Freq | Unit | Coverage | Latest | Source |
|---|---|---|---|---|---|---|
| GDP | `gdp_growth_q` real GDP growth y/y (2022-23 base) | Q (fiscal) | % | Q1 2023-24 → Q1 2026-27 | 7.8 | MoSPI NAS API, indicator 22 |
| GDP | `gdp_growth_q_old` (2011-12 base, discontinued) | Q | % | Q1 2012-13 → Q2 2025-26 | 8.2 | MoSPI NAS API |
| GVA | `gva_growth_q` + 3 broad-sector and 8 industry series | Q | % | Q1 2023-24 → Q1 2026-27 | 8.2 (total), 10.0 (services) | MoSPI NAS API, indicators 1 and 21 |
| GVA | `gva_level_q` + broad-sector and industry levels | Q | ₹ lakh crore | Q1 2022-23 → Q1 2026-27 | 73.82 (total), 40.91 (services) | MoSPI NAS API, indicator 1 |
| GDP | `gdp_level_q`, `gdp_growth_a` (charted at 31 March of each FY), nominal growth | Q / FY | ₹ lakh cr / % | 2022-23 → | | MoSPI NAS API |
| CPI | `cpi_infl_combined/rural/urban`, `cpi_food`, `cpi_index` (2024=100) | M | % / index | Jan 2026 → Oct 2026 (index from Jan 2025) | 6.09 | MoSPI `getCPIData` |
| CPI | `cpi_infl_old`, `cfpi_old` (2012=100, discontinued) | M | % | Jan 2014 → Dec 2025 | 1.33 | MoSPI `getCPIIndex` |
| IIP | `iip_growth` and growth rates for all four sectors (2022-23 base) | M | % | Apr 2023 → Sep 2026 | 6.7 (General) | MoSPI `getIipData` |
| IIP | `iip_index` and four sector indices | M | 2022-23=100 | Apr 2023 → Sep 2026 | 124.3 (General) | MoSPI `getIipData` |
| IIP | `iip_growth_old` (2011-12=100) | M | % | Apr 2012 → Mar 2026 | 4.1 | MoSPI `getIipData` |
| Banks | `scb_gap`, `scb_gap_3m` credit growth minus deposit growth, latest and 3-month average | M | pp | Jan 2023 → Oct 2026 | 2.68 / 1.74 | Derived from Handbook T167 + WSS Table 4 |
| Banks | `scb_inc_cd_fytd` incremental credit–deposit ratio, financial year to date | M | % | Apr 2022 → Oct 2026 | 90.1 (72.1 a year earlier) | Derived; omitted while deposits are up <0.5% since end-March |
| Funding | `mmo_call_spread` (+`_5d`) call money rate minus repo, `mmo_net_liq` RBI net liquidity (row F), `mmo_call`, `mmo_overnight` | Daily | bp / ₹ crore / % | 31 Oct 2025 → (one year backfilled, no missing days) | | RBI "Money Market Operations" daily press release |
| Pricing | `walr_fresh`, `walr_out`, `wadtdr_fresh`, `wadtdr_out`, `mclr_1y_median`, `pricing_gap_fresh` | Monthly | % / pp | Feb 2023 → for lending/deposit rates, Mar 2023 → for MCLR | Sep 2026: 8.51 / 5.61 / 2.90 pp | RBI "Lending and Deposit Rates of SCBs" monthly press release |
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

## Page layout

Two tabs, each with its own link (`#brief`, `#macro`); a link to any chart opens the tab that holds it.
Every history chart starts in **April 2023** on one shared timeline; older data stays in the files.

1. **Banking brief** (opens by default)
   - **Bank credit and deposit growth:** the latest credit-minus-deposit gap and its 3-month average with equal
     prominence, a sentence generated from the data, a 12-month chart (Dec 2025–Nov 2026 shaded: those months compare
     a month-end with the reporting Friday a year earlier), and the incremental credit–deposit ratio, financial year
     to date, beside the same point last year. The panel says the gap is not a cash shortfall.
   - **Funding conditions** (daily): call money rate minus the repo rate in force, its 5-trading-day average, and RBI
     net liquidity (row F), shown as an amount plus "net absorption/injection".
   - **Pricing of new business** (monthly): fresh-loan WALR, fresh term-deposit WADTDR, their difference labelled a
     market pricing indicator, the 1-year median MCLR dated by its own month, and outstanding-book rates.
   - **History:** bank credit and deposit growth, call spread, net liquidity, lending and deposit rates.
2. **Macro summary** (starts with the tiles)
   - Eight tiles with neutral changes (no good/bad colour), then a sentence on repo, CPI against the 2–6% band, and GDP.
   - The main GDP and GVA chart shows real levels in ₹ lakh crore. The GVA breakdown uses one quarter for the total,
     the three broad sectors, and the eight industries. Industry levels reconcile to total GVA within source rounding.
   - The IIP headline and charts show index levels, with General IIP and all four sectors. The Series Explorer
     retains growth rates and discontinued GDP and IIP series.
   - The CPI tolerance band applies to the headline chart. Food inflation has its own chart. Old-base CPI is opt-in.
   - Weekly benchmark yields and historical traded yields have separate charts, as do USD/INR and EUR/INR.
     Period labels and expected update windows distinguish live feeds from historical Handbook series.
   - Series explorer for any series, including those without a chart of their own.
3. **Footer:** when published series last changed and a link to this README for sources, methods and known gaps (the page itself no
   longer carries the catalogue table or the methods section).

Fixed page text may not mention a month or year unless it is a listed permanent fact (`tests/test_page_text.py`);
anything that describes the current situation is drawn from the data.

## Website and automation

The same page runs in two places: the Claude dashboard and a static website built into `site/` from
`web/template.html` + `dashboard/page/` (the small `web/dash-shim.js` stands in for the Claude dashboard runtime).

| What | How often | Who |
|---|---|---|
| RBI money-market (daily) and lending-rate (monthly) releases | daily, 09:00 IST | GitHub Action `update.yml` (`pipeline/fetch_rbi_releases.py`) |
| MoSPI series (GDP/GVA, CPI, IIP, RBI forex/FX history) | daily, 09:00 IST | GitHub Action `update.yml` |
| rbi.org.in Current Rates (repo, FBIL rates, G-Sec yields) | daily | GitHub Action `update.yml` |
| Validate, commit data, publish to GitHub Pages | daily, and on every push | GitHub Action `update.yml` |
| RBI Handbook + Weekly Statistical Supplement tables | weekly (WSS is out on Fridays) | **a person**, prompted by an issue from `rbi-reminder.yml` |
| MPC rate decisions | every two months | **a person** adds them to `POLICY_EXTRA` in `pipeline/rbi_extract.js` |
| New Handbook file ids | once a year (Jul–Sep) | **a person** updates `HB_IDS` in `pipeline/rbi_extract.js` |

### Safeguards

| Risk | Guard |
|---|---|
| rbi.org.in changes its layout and a rate stops parsing | `fetch_rbi_home.py` replaces the saved snapshot only if every required field parsed and is in range (`pipeline/checks.py`); `validate.py` re-checks it; the page shows a missing value as `—`, never `0.00%` |
| An RBI snapshot disagrees with the policy history | The comparison uses the rates in force on the snapshot's India date. `validate.py` warns, the daily job opens a GitHub issue, and the page displays the disagreement. |
| A policy change has been announced with a future effective date | The page lists it as scheduled and moves it into the headline and chart on its effective India date. |
| MoSPI returns an incomplete or repeated set of pages | `fetch_mospi.py` checks reported page numbers and row totals, and keeps the cached file when it detects a repeated or missing page. |
| An older WSS bulletin overwrites a revision from a newer one | `merge_rbi.py` keeps the newest known issue's value and reports conflicts with saved observations whose issue date is unknown. |
| A series disappears or is renamed | `pipeline/series_ids.txt` lists every published id; any missing or unlisted id fails validation |
| A series moves backwards or shrinks >5%, or has invalid periods, out-of-range values or duplicates | `validate.py` errors. PR checks compare against the PR base commit. |
| Stale sources (e.g. the manual RBI step not run) | `validate.py` warnings in the run summary |

Errors stop publishing; the last good site stays up. If a fetch fails, the Action keeps the last good raw files (cached).

### Tests

`tests/` holds offline checks with fixtures for each failure above (a trimmed real copy of the rbi.org.in rates box
plus altered versions, MoSPI page sequences, WSS issues). No network is used.

```
python3 -m unittest discover -s tests -v     # pipeline checks
node tests/test_render.js                    # page rendering checks
```
They run on every pull request and push (`.github/workflows/test.yml`) and before each daily publish.

### RBI press-release collectors

`pipeline/fetch_rbi_releases.py` reads the press-release archive month by month (plain HTML on rbi.org.in, no
browser step) and appends one parsed record per release to `data/raw/rbi_mmo.jsonl` and `rbi_lending.jsonl`.

- **Append-only.** Raw lines are never edited. Releases whose observation date is within 7 days are fetched again
  and appended only if their content changed; for each date or month the newest release wins.
- **Self-healing.** A release that fails to parse is reported and not stored, and the daily run rechecks the current
  and previous month, so a missed or broken day is collected on a later run.
- **No-trade days** (weekends, holidays) have no call rate and no spread, but keep the liquidity figure RBI reports.
- **Backfill:** `python3 pipeline/fetch_rbi_releases.py --since 2025-11 --only mmo` (one year of liquidity) and
  `--since 2023-01 --only lending`. Resumable: re-running skips what is stored.

### Recording an MPC decision

The refresh checks RBI's repo snapshot against the dated history. If they disagree, it looks for an official
Liquidity Adjustment Facility rate-change circular and records the effective date, rates and source URL in
`data/raw/rbi_policy_circulars.json` when the evidence agrees. While verification is pending, the dashboard
keeps the call money rate and net liquidity visible and withholds the affected daily and five-day spreads.
Historical spreads through the last verified period remain available.

If the circular needs manual review, add `[effectiveDate, repo, sdf, msf, crr, slr, 'source']` to
`POLICY_EXTRA` in `pipeline/rbi_extract.js` and to `policy` in `data/raw/rbi_extract.json`. Use the effective
date in RBI's decision and cite the source. The next build recalculates the spreads.

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

If the merge reports a conflict with a saved observation whose issue date is unknown, verify the figures and
publication dates in the source bulletins. In `data/raw/rbi_extract.json`, record the verified value and its
issue date as `[observationDate, value, issueDate]`. This lets future imports compare revisions by date.

Why a browser step: `rbidocs.rbi.org.in` (where RBI's XLSX tables live) serves its files only to a browser that
runs its JavaScript check, and RBI's DBIE portal (`data.rbi.org.in`) uses session tokens and encrypted requests
with no documented public API. The script only reads public files with `fetch()` and parses them with built-in
browser APIs. Automating this with a headless browser would mean getting past RBI's bot check, so it is left manual.

### Run everything locally

```
python3 pipeline/fetch_mospi.py          # MoSPI API, no key; NAS = 1 indicator/call, CPI-2024 max 100 rows/page
python3 pipeline/fetch_rbi_home.py       # rbi.org.in Current Rates box
python3 pipeline/build_data.py           # -> data/macro.json
python3 pipeline/validate.py             # exit 1 on errors
python3 pipeline/export_dashboard.py     # -> dashboard/observations.json, catalog.json, snapshot.json
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
.github/workflows/  update.yml (daily build + Pages)  test.yml (PR checks)  rbi-reminder.yml (weekly issue)
pipeline/   fetch_mospi.py  fetch_rbi_home.py  list_wss.py  rbi_extract.js  merge_rbi.py
            build_data.py  export_dashboard.py  validate.py  build_site.py  checks.py  series_ids.txt
tests/      test_pipeline.py  test_render.js  fixtures/
web/        template.html  dash-shim.js            (standalone-site wrapper)
dashboard/  page/index.html  page/app.js           (shared page + charts)
            observations.json  catalog.json  snapshot.json
data/       macro.json  raw/rbi_extract.json  raw/rbi_home.json   (raw/mospi/ is fetched, not committed)
site/       build output, not committed
```
