# India Macro Monitor — data pipeline

Source-backed Indian macro dataset from **MoSPI**, **RBI** and other official publishers, plus an interactive
dashboard. Data first built **24 Nov 2026**; the table below is that snapshot. Built with Python, D3 and GitHub Pages.

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

- **Overview** opens with plain-language changes in GDP growth, inflation and unemployment, then six headline
  indicators. The published HTML includes the summary, headline values and their reference periods. Headline cards
  show when an update is overdue where the regular release schedule is known. Official release links and dates appear when the reading matches the period in
  `data/raw/overview_releases.json`.
- **Economy** shows GDP and GVA levels, real household consumption and fixed investment, national jobs data,
  CPI, industrial production, policy rates, bond yields and exchange rates. The RBI current-rates table is
  at the bottom. The CPI tolerance band applies to headline inflation. The monthly jobs charts use
  all-India PLFS estimates for people aged 15+ in Current Weekly Status.
- **States** compares two states or union territories on rural and urban household spending and the latest
  available month of state headline CPI. Spending is nominal monthly per-person expenditure, without
  imputation. Use the survey-round selector to switch HCES periods.
- **Banking** retains credit and deposit growth, the incremental credit–deposit ratio, funding conditions,
  lending and deposit pricing, and their histories.
- **Explorer** gives access to the underlying national series, including growth rates and discontinued series. The public site offers a full-history CSV for each series.

Fixed page text may not mention a month or year unless it is a listed permanent fact (`tests/test_page_text.py`);
anything that describes the current situation is drawn from the data.

## Data downloads

In **Explorer**, choose a series and select **Download full series (CSV)**. The CSV includes the full coverage held in
`data/macro.json`, including observations before the chart window. Files are UTF-8 with a byte-order mark for Excel.
Columns are `series_id`, `period` (source reporting period), `label` (display period), `date` (chart date), `value`,
and `unit`. For policy rates, `date` is the effective date and the file may include future scheduled changes.

The [published dashboard](https://prathameshtaywade.github.io/india-macro-monitor/) refreshes these relative URLs with each successful build:

| File | Fields and coverage |
|---|---|
| [Series catalogue](https://prathameshtaywade.github.io/india-macro-monitor/data/catalog.json) | `rows` with `id`, `name`, `unit`, `freq`, `base`, source fields, and full coverage. Use `id` to join files. |
| [Chart observations](https://prathameshtaywade.github.io/india-macro-monitor/data/observations.json) | `rows` with `series`, `period`, `label`, `date`, `value`, plus `meta` for build and release details. Covers the chart window starting April 2023, with the prior policy reading carried in. |
| [RBI rate snapshot](https://prathameshtaywade.github.io/india-macro-monitor/data/snapshot.json) | `rows` with `item`, `group`, `value`, `unit`, and the source's `as_of` date or label. |
| [State comparisons](https://prathameshtaywade.github.io/india-macro-monitor/data/regions.json) | `rows` with state and union territory CPI and household spending, plus `meta` for reporting periods and sources. |
| `data/csv/<series_id>.csv` | Full stored history for one catalogue ID, such as `data/csv/cpi_infl_combined.csv`. |
| `data/series/<series_id>.json` | Full stored history for one series, with `period`, `date`, `label`, and `value`. |
| `data/research.json` | Upcoming calendar events, displayed revision comparisons, and source-linked forecast comparisons. |

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

The public RBI weekly HTML extract now supplies reserves, bank credit, deposits and M3 automatically. The
weekly browser import remains the fallback for those series and supplies rates from Table 5, which the HTML
press release omits. The same collector reads RBI's monthly balance-of-payments and sectoral-credit releases,
DPIIT's WPI workbook, CGA fiscal accounts, Commerce SDDS trade and GST reports. Core CPI and housing loan
benchmarks are sourced observations from RBI publications with limited coverage. Collector failures leave the
last successful readings available and appear in the GitHub warnings. The schedule describes the planned
refresh; agency release times and source availability vary.

## Research and reader tools

- **Comparison.** Explorer fetches full series only when opened. It supports overlays at matching frequencies,
  relative changes and rebasing to the first shared positive reporting period. Rate changes are shown in points.
  The seasonal view is an experimental multiplicative decomposition with centred 12-month averages. It requires
  at least five years of positive, consecutive monthly levels and can revise as new data arrive.
- **Long histories.** `cpi_linked`, `iip_linked` and `gdp_linked` extend the current series using overlap ratios.
  Earlier observations are dashboard estimates, with documented overlap periods and a break in measurement.
  The current-base official series stay available separately.
- **Releases.** `calendar.html` and `calendar.ics` use only published dates; update `data/raw/research_evidence.json`
  when an agency changes its schedule. `feed.xml` provides RSS alerts without subscriber accounts. The revision
  ledger records new and changed GDP, CPI and IIP values. Older rows use the first reading held in the repository
  unless a dated official first print has been verified. Forecasts require a public pre-release source and a
  matching official first print. The current comparison includes a documented CPI poll; there is no live consensus feed.
- **Rates.** The headline 10-year rate is the traded government benchmark. Explorer retains the weekly FBIL par
  benchmark. The maturity view draws the bonds quoted by RBI, and repo less trailing inflation is a backward-looking
  real-rate proxy. Obtain written reuse permission before adding a commercial CCIL yield curve.
- **Readers.** Overview has FD purchasing power, USD conversion, and home-loan payment calculators. States compares
  reported values with the all-India figures and ranks available states and territories in the same reporting period.
  The About page provides a corrections contact and explains reuse and limitations. WhatsApp links use section pages
  with separately generated previews.
- **Hosting.** GitHub Pages is the default. After a domain is registered and its DNS and Pages settings are configured,
  set the repository Action variable `SITE_URL` to its HTTPS address for canonical links, alerts, and share previews.

Install the pinned build dependencies once with `python3 -m pip install -r web/requirements.txt`. The code retains
its copyright. For reuse, contact the maintainer through GitHub. Source data follows the original publishers’ terms.

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
| Charts end on stale weekly figures while the daily table is current | Every valid rbi.org.in snapshot is appended to `data/raw/rbi_home_history.jsonl`; daily `usdinr_d` and `gsec10_bench_d` (10-year benchmark bond, named per point) and the daily call rate (`mmo_call`) are charted beside the weekly series |
| The manual weekly RBI step is missed | From day 8 the page marks weekly series "Awaiting weekly RBI update" and `validate.py` warns |
| A collector fails quietly (fetch steps may fail without stopping the run) | `pipeline/fetch_status.py` writes each source's outcome to the run summary and `data/raw/fetch_status.json`; two failures in a row open an issue |
| A hand-entered reading outlives its purpose | `merge_backfill` adds the PDF-sourced March 2026 jobs values only while the API lacks that month |

Errors stop publishing; the last good site stays up. If a fetch fails, the Action keeps the last good raw files (cached).

### Tests

`tests/` holds offline checks with fixtures for each failure above (a trimmed real copy of the rbi.org.in rates box
plus altered versions, MoSPI page sequences, WSS issues). No network is used.

```
python3 -m unittest discover -s tests -v     # pipeline checks
node tests/test_render.js                    # page rendering checks
```
They run on every pull request and push (`.github/workflows/test.yml`) and before each daily publish.

### Dates shown for readings

- **"Released <date>"**: the official release date, from `data/raw/overview_releases.json` (hand-maintained; shown only
  when its series and period match the reading exactly).
- **"First published here <date>"**: recorded automatically (`first_seen` in `data/macro.json`) the first time a new
  latest reading appears in a build. Readings already present before tracking began show no date.

### What readers download

`dashboard/observations.json` holds rows from April 2023 only (the charts' start), plus the last policy-rate step
before it. Full history stays in `data/macro.json`; the explorer's coverage line and the catalogue show full dates.

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
